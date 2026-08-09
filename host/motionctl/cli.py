"""MotionEdge设备管理、采集、报告与MQTT网关命令行。"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, commands
from .capture import capture_session, load_telemetry
from .commands import RuntimeConfig, decode_device_info, decode_motion, decode_status
from .device import DeviceClient
from .errors import (EXIT_REPORT, EXIT_RUNTIME, EXIT_SUCCESS, MotionCtlError,
                     ReportError, ValidationError)
from .gateway_cli import add_gateway_parser, run_gateway_command
from .phase08_cli import add_phase08_parsers, run_phase08
from .metrics import command_metrics, motion_metrics
from .models import CaptureMetadata, stable_dict
from .report import generate_report
from .simulator import SimulatedDevice
from .transport import SerialTransport, list_ports
from .validation import FAIL, validate_metrics


def _connection(parser, *, port_required=True):
    if port_required: parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=1.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--verbose", action="store_true")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("ports")
    for name in ("doctor", "info", "status", "calibrate", "monitor", "capture", "session", "ping"):
        item = subs.add_parser(name); _connection(item)
        if name == "ping": item.add_argument("--count", type=int, default=1)
        if name == "calibrate":
            item.add_argument("--wait", action="store_true"); item.add_argument("--wait-timeout", type=float, default=30.0)
        if name == "monitor": item.add_argument("--duration", type=float, default=30.0)
        if name in ("capture", "session"):
            item.add_argument("--duration", type=float, default=60.0); item.add_argument("--output", type=Path, required=True)
    config = subs.add_parser("config"); config_sub = config.add_subparsers(dest="config_command", required=True)
    config_get = config_sub.add_parser("get"); _connection(config_get)
    config_set = config_sub.add_parser("set"); _connection(config_set)
    config_set.add_argument("--telemetry-hz", type=float)
    config_set.add_argument("--stream", choices=("binary", "off"))
    config_set.add_argument("--filter-alpha", type=float)
    config_set.add_argument("--gyro-weight", type=float)
    config_set.add_argument("--sensor-ms", type=int); config_set.add_argument("--log-level", type=int)
    stream = subs.add_parser("stream"); stream_sub = stream.add_subparsers(dest="stream_command", required=True)
    for name in ("start", "stop"):
        item = stream_sub.add_parser(name); _connection(item)
    validate = subs.add_parser("validate"); validate.add_argument("session", type=Path)
    report = subs.add_parser("report"); report.add_argument("session", type=Path); report.add_argument("--output", type=Path, required=True)
    subs.add_parser("simulate-device"); subs.add_parser("self-test")
    add_gateway_parser(subs)
    add_phase08_parsers(subs)
    return parser


def _client(args) -> DeviceClient:
    return DeviceClient(SerialTransport(args.port, args.baud), timeout=args.timeout)


def _print(value) -> None:
    print(json.dumps(stable_dict(value), ensure_ascii=False, indent=2))


def _not_available(value):
    return "NOT_AVAILABLE" if value is None else value


def _command_summary(client: DeviceClient) -> dict[str, object]:
    """同时保留逻辑命令成功率和底层线路尝试，避免安全重试掩盖瞬态错误。"""
    logical = command_metrics(client.command_results)
    attempts = command_metrics(client.attempt_results)
    return {**logical, "wire_attempts": attempts["requests"],
            "wire_timeouts": attempts["timeouts"],
            "wire_errors": attempts["errors"],
            "retry_count": client.retry_count,
            "wire_success_rate_percent": attempts["success_rate_percent"]}


def _device_snapshot(client: DeviceClient):
    client.request(commands.PING)
    info = decode_device_info(client.request(commands.GET_DEVICE_INFO))
    config = RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
    status = decode_status(client.request(commands.GET_STATUS), stream_enabled=config.telemetry_enabled)
    return info, status, config


def _print_info(info) -> None:
    data = stable_dict(info)
    for key, value in data.items(): print(f"{key}: {_not_available(value)}")


def _print_status(status) -> None:
    data = stable_dict(status)
    for key, value in data.items(): print(f"{key}: {_not_available(value)}")


def _apply_config(args, current: RuntimeConfig) -> RuntimeConfig:
    changes = {}
    if args.telemetry_hz is not None:
        if not 0.2 <= args.telemetry_hz <= 50.0: raise ValueError("--telemetry-hz must be 0.2..50")
        changes["telemetry_ms"] = round(1000.0 / args.telemetry_hz)
    if args.stream is not None: changes["telemetry_enabled"] = args.stream == "binary"
    if args.filter_alpha is not None:
        if not 0.001 <= args.filter_alpha <= 1.0: raise ValueError("--filter-alpha must be 0.001..1.0")
        changes["alpha_milli"] = round(args.filter_alpha * 1000)
    if args.gyro_weight is not None:
        if not 0.5 <= args.gyro_weight <= 0.999: raise ValueError("--gyro-weight must be 0.5..0.999")
        changes["gyro_weight_milli"] = round(args.gyro_weight * 1000)
    if args.sensor_ms is not None: changes["sensor_ms"] = args.sensor_ms
    if args.log_level is not None: changes["log_level"] = args.log_level
    result = dataclasses.replace(current, **changes)
    if not result.validate(): raise ValueError("requested RuntimeConfig is outside firmware ranges")
    return result


def _capture_with_state(client, args, metadata, *, interactive=False):
    original = RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
    if not original.telemetry_enabled: client.request(commands.SET_STREAM_STATE, b"\1", retry=False)
    # 用户确认前可能已开启流；正式计时前清空积压，保证设备时间和主机会话一一对应。
    client.flush_input()
    prompts = {"motion": False, "stationary": False}
    def progress(elapsed, sample):
        if interactive:
            if elapsed >= 20.0 and not prompts["motion"]:
                print("\n现在缓慢向左、向右、向前、向后倾斜面包板。"); prompts["motion"] = True
            if elapsed >= 50.0 and not prompts["stationary"]:
                print("\n现在停止移动并保持静止。"); prompts["stationary"] = True
        if sample is not None:
            print(f"\r{elapsed:6.1f}s seq={sample.sample_sequence} roll={sample.roll_deg:7.2f}° pitch={sample.pitch_deg:7.2f}°", end="", flush=True)
    try:
        return capture_session(client, args.output, args.duration, metadata, progress)
    finally:
        if not original.telemetry_enabled:
            client.request(commands.SET_STREAM_STATE, b"\0", retry=False)
        print()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "gateway":
            return run_gateway_command(args)
        if args.command in ("characterize", "tune"):
            return run_phase08(args)
        if args.command == "ports":
            ports = list_ports()
            if not ports: print("No serial ports found.")
            for item in ports:
                vid_pid = "NOT_AVAILABLE" if item.vid is None else f"{item.vid:04X}:{item.pid:04X}"
                print(f"{item.device}\tdescription={_not_available(item.description)}\tVID:PID={vid_pid}\tserial={_not_available(item.serial_number)}\trole={item.likely_role}")
            return EXIT_SUCCESS
        if args.command in ("simulate-device", "self-test"):
            with DeviceClient(SimulatedDevice(), timeout=0.1) as client:
                info, status, config = _device_snapshot(client)
                _print({"warning": "SIMULATOR ONLY", "info": info, "status": status, "config": config})
            return EXIT_SUCCESS
        if args.command == "validate":
            capture = json.loads((args.session / "capture-summary.json").read_text(encoding="utf-8"))
            metadata = json.loads((args.session / "session-metadata.json").read_text(encoding="utf-8"))
            metrics = motion_metrics(load_telemetry(args.session), requested_duration_s=capture.get("requested_duration_s"))
            parser = capture.get("parser", {})
            result = validate_metrics(metrics, identity_ok=bool(metadata.get("device_info")), ping_ok=metadata.get("ping_ok"),
                                      parser_errors=parser.get("length_errors", 0)+parser.get("version_errors", 0), crc_errors=parser.get("crc_errors"),
                                      command_success_rate=metadata.get("command_success_rate"), fault_seen=metadata.get("fault_seen"),
                                      degraded_persistent=metadata.get("degraded_persistent"))
            _print(result); return EXIT_SUCCESS if result.conclusion in ("PASS", "WARN") else ValidationError.exit_code
        if args.command == "report":
            result = generate_report(args.session, args.output); print(args.output / "report.md")
            return EXIT_SUCCESS if result["validation"]["conclusion"] in ("PASS", "WARN") else EXIT_REPORT
        with _client(args) as client:
            if args.command == "ping":
                if args.count <= 0: raise ValueError("--count must be positive")
                for _ in range(args.count): client.request(commands.PING)
                _print(_command_summary(client)); return EXIT_SUCCESS
            if args.command == "doctor":
                info, status, config = _device_snapshot(client)
                checks = {"python": "PASS", "pyserial": "PASS", "serial_open": "PASS", "ping": "PASS",
                          "protocol": "PASS" if info.protocol_version == 1 else "FAIL",
                          "device_info": "PASS", "application": "PASS" if status.app_state != "FAULT" else "FAIL"}
                _print({"checks": checks, "result": "PASS" if "FAIL" not in checks.values() else "FAIL",
                        "info": info, "status": status, "config": config,
                        "errors": {"protocol": "NOT_AVAILABLE", "uart": "NOT_AVAILABLE"}})
                return EXIT_SUCCESS if "FAIL" not in checks.values() else EXIT_RUNTIME
            if args.command == "info": _print_info(decode_device_info(client.request(commands.GET_DEVICE_INFO)))
            elif args.command == "status":
                config = RuntimeConfig.unpack(client.request(commands.GET_CONFIG)); _print_status(decode_status(client.request(commands.GET_STATUS), stream_enabled=config.telemetry_enabled))
            elif args.command == "config":
                before = RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
                if args.config_command == "get": _print(before)
                else:
                    after = _apply_config(args, before); client.request(commands.SET_CONFIG, after.pack(), retry=False)
                    confirmed = RuntimeConfig.unpack(client.request(commands.GET_CONFIG)); _print({"before": before, "after": confirmed})
            elif args.command == "stream":
                enabled = args.stream_command == "start"; client.request(commands.SET_STREAM_STATE, bytes((enabled,)), retry=False)
                confirmed = RuntimeConfig.unpack(client.request(commands.GET_CONFIG)); _print({"stream_enabled": confirmed.telemetry_enabled})
                if confirmed.telemetry_enabled != enabled: raise RuntimeError("device did not confirm stream state")
            elif args.command == "calibrate":
                client.request(commands.START_CALIBRATION, retry=False); started = time.monotonic(); print("Calibration started; accepted/rejected samples: NOT_AVAILABLE")
                if args.wait:
                    while time.monotonic() - started < args.wait_timeout:
                        status = decode_status(client.request(commands.GET_STATUS))
                        try: motion = decode_motion(client.request(commands.GET_LATEST_MOTION))
                        except MotionCtlError: motion = None
                        print(f"\rstate={status.sensor_state} elapsed={time.monotonic()-started:.1f}s", end="", flush=True)
                        if status.sensor_state == "RUNNING" and motion and motion.calibrated: break
                        time.sleep(0.25)
                    else: raise RuntimeError("calibration timeout; keep the board stationary and retry")
                    print("\nCalibration PASS; biases: NOT_AVAILABLE in protocol v1")
            elif args.command == "monitor":
                original = RuntimeConfig.unpack(client.request(commands.GET_CONFIG)); client.request(commands.SET_STREAM_STATE, b"\1", retry=False)
                deadline = time.monotonic() + args.duration
                try:
                    while time.monotonic() < deadline:
                        for frame in client.poll():
                            if frame.type == commands.MOTION_TELEMETRY:
                                sample = decode_motion(frame.payload)
                                print(f"\rroll={sample.roll_deg:7.2f}° pitch={sample.pitch_deg:7.2f}° a=({sample.ax_mg},{sample.ay_mg},{sample.az_mg})mg g=({sample.gx_mdps},{sample.gy_mdps},{sample.gz_mdps})mdps seq={sample.sample_sequence} errors={client.parser.crc_errors+client.parser.length_errors}", end="", flush=True)
                finally:
                    if not original.telemetry_enabled: client.request(commands.SET_STREAM_STATE, b"\0", retry=False)
                    print()
            elif args.command in ("capture", "session"):
                info, status, config = _device_snapshot(client)
                if args.command == "session": input("前20秒保持面包板静止，准备好后按Enter开始60秒会话。")
                git_commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip() or None
                before_commands = _command_summary(client)
                metadata = CaptureMetadata(__version__, datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                                           args.duration, args.port, args.baud, git_commit, info, stable_dict(config), False,
                                           True, before_commands.get("success_rate_percent"), before_commands, False, False)
                summary = _capture_with_state(client, args, metadata, interactive=args.command == "session")
                result = generate_report(args.output, args.output / "report")
                _print(summary)
                if args.command == "session":
                    (args.output / "phase06-validation-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                return EXIT_SUCCESS if result["validation"]["conclusion"] in ("PASS", "WARN") else ValidationError.exit_code
        return EXIT_SUCCESS
    except MotionCtlError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if getattr(args, "verbose", False): raise
        return exc.exit_code
    except KeyboardInterrupt:
        print("Interrupted; partial capture was finalized when possible.", file=sys.stderr); return 1
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if getattr(args, "verbose", False): raise
        return EXIT_RUNTIME
