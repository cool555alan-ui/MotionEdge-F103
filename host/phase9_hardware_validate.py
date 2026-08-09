#!/usr/bin/env python3
"""Phase 9A 真实舵机交互验收；不会自动搜索机械极限。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import struct
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import serial

from motionctl import __version__, commands
from motionctl.actuator_cli import _calibrate_range
from motionctl.commands import decode_actuator_status, decode_health, decode_motion
from motionctl.device import DeviceClient
from motionctl.errors import CommandError, RequestTimeout
from motionctl.transport import SerialTransport

PASS, WARN, FAIL, NOT_TESTED = "PASS", "WARN", "FAIL", "NOT_TESTED"


def action(client: DeviceClient, command: int, payload: bytes = b"") -> bytes:
    return client.request(command, payload, retry=False)


def owner() -> bytes:
    return bytes((commands.ACTUATOR_OWNER_SERIAL,))


def set_pulse(client: DeviceClient, pulse: int) -> None:
    action(client, commands.ACTUATOR_SET_RAW_PULSE,
           struct.pack("<BH", commands.ACTUATOR_OWNER_SERIAL, pulse))


def observe(client: DeviceClient, seconds: float, pulse: int | None = None) -> dict:
    counts: Counter[str] = Counter()
    motion_sequences: list[int] = []
    app_states: list[int] = []
    deadline_samples: list[tuple[int, int, int, int]] = []
    deadline = time.monotonic() + seconds
    next_keepalive = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if pulse is not None and now >= next_keepalive:
            try:
                set_pulse(client, pulse)
            except RequestTimeout:
                # 中心位耐久测试允许记录单次 ACK 丢失后继续；不得重发同一动作命令。
                # 非中心位仍立即中止，避免真实舵机动作与验收预期不一致。
                counts["keepalive_ack_timeouts"] += 1
                if pulse != 1500:
                    raise
            next_keepalive = time.monotonic() + 0.4
        # request()同样会接收异步遥测并放入telemetry队列；统一从队列取出，
        # 避免把命令等待期间已成功解析的帧误报为丢帧。
        client.poll()
        while client.telemetry:
            _, frame = client.telemetry.popleft()
            if frame.type == commands.MOTION_TELEMETRY:
                sample = decode_motion(frame.payload); motion_sequences.append(sample.sample_sequence)
                counts["motion"] += 1
            elif frame.type == commands.HEALTH_TELEMETRY:
                sample = decode_health(frame.payload); app_states.append(sample.app_state_raw)
                deadline_samples.append((sample.sensor_deadline_miss,
                                         sample.communication_deadline_miss,
                                         sample.telemetry_deadline_miss,
                                         sample.health_deadline_miss))
                counts["health"] += 1
            elif frame.type == commands.ACTUATOR_TELEMETRY:
                decode_actuator_status(frame.payload); counts["actuator"] += 1
        time.sleep(0.01)
    gaps = sum(max(0, (b - a) // 10 - 1) for a, b in zip(motion_sequences, motion_sequences[1:]) if b >= a)
    return {"counts": dict(counts), "motion_frames": len(motion_sequences),
            "estimated_motion_gaps": gaps, "app_fault_seen": 4 in app_states,
            "crc_errors": client.parser.crc_errors,
            "parser_errors": client.parser.length_errors + client.parser.version_errors,
            "deadline_first": deadline_samples[0] if deadline_samples else None,
            "deadline_last": deadline_samples[-1] if deadline_samples else None,
            "deadline_delta": (delta(deadline_samples[0], deadline_samples[-1])
                               if deadline_samples else None)}


def text_snapshot(port: str, baud: int, seconds: float, raw_path: Path) -> dict:
    lines: list[str] = []
    with serial.Serial(port, baud, timeout=0.1, xonxoff=False,
                       rtscts=False, dsrdtr=False) as stream, raw_path.open("a", encoding="utf-8") as raw:
        deadline = time.monotonic() + seconds
        pending = b""
        while time.monotonic() < deadline:
            pending += stream.read(512)
            while b"\n" in pending:
                value, pending = pending.split(b"\n", 1)
                line = value.decode("utf-8", errors="replace").rstrip("\r")
                lines.append(line); raw.write(line + "\n")
    text = "\n".join(lines)
    def last(pattern: str):
        rows = re.findall(pattern, text); return tuple(map(int, rows[-1])) if rows else None
    return {
        "run": last(r"\[INFO\]\[RTOS\] kernel=\d+ run=(\d+)/(\d+)/(\d+)/(\d+)"),
        "miss": last(r"\[INFO\]\[RTOS-DEADLINE\] miss=(\d+)/(\d+)/(\d+)/(\d+)"),
        "heap": last(r"\[INFO\]\[RTOS-DEADLINE\].*heap=(\d+)/(\d+)"),
        "stack": last(r"\[INFO\]\[RTOS-MEM-BYTES\] stack_bytes=(\d+)/(\d+)/(\d+)/(\d+)"),
        "comm": last(r"\[INFO\]\[RTOS-COMM\] rx=(\d+) crc=(\d+) parser=(\d+) command=(\d+) tx=(\d+)"),
        "uart": last(r"\[INFO\]\[RTOS-COMM\].*uart=(\d+) pe/ne/fe/ore=(\d+)/(\d+)/(\d+)/(\d+)"),
    }


def delta(before, after):
    return tuple(b - a for a, b in zip(before, after)) if before and after else None


def write_checkpoint(output: Path, metadata: dict, checks: dict,
                     manual: list[dict], calibration: dict,
                     soak: dict, stage: str) -> None:
    """每个实机步骤完成后立即保存，避免终端关闭导致证据丢失。"""
    payload = {
        "stage": stage,
        "saved_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "metadata": metadata,
        "checks": checks,
        "manual_results": manual,
        "calibration": calibration,
        "soak": soak,
    }
    (output / "phase09-session-checkpoint.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_outputs(output: Path, metadata: dict, checks: dict,
                  manual: list[dict], calibration: dict, soak: dict,
                  rtos: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "manual-control-results.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ["pulse_us", "target_angle_deg", "status", "observed_state",
                  "current_pulse_us", "timeout_count", "fault_count", "note"]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(manual)
    with (output / "servo-calibration.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ["measured_safe_min_us", "measured_center_us", "measured_safe_max_us",
                  "recommended_safe_min_us", "recommended_safe_max_us", "margin_us", "status"]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n"); writer.writeheader()
        writer.writerow({
            "measured_safe_min_us": calibration.get("measured_min_us"),
            "measured_center_us": calibration.get("measured_center_us"),
            "measured_safe_max_us": calibration.get("measured_max_us"),
            "recommended_safe_min_us": calibration.get("recommended_safe_min_us"),
            "recommended_safe_max_us": calibration.get("recommended_safe_max_us"),
            "margin_us": calibration.get("margin_us"), "status": checks["servo_range_calibration"]})
    with (output / "safety-validation.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n"); writer.writerow(("item", "status")); writer.writerows(checks.items())
    summary = {"metadata": metadata, "checks": checks, "manual_results": manual,
               "calibration": calibration, "soak": soak, "rtos": rtos,
               "phase9a": PASS if FAIL not in checks.values() else FAIL,
               "phase9b": NOT_TESTED, "overcurrent": "NOT_AVAILABLE",
               "pwm_electrical_jitter": NOT_TESTED}
    (output / "phase09-actuator-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# MotionEdge Phase 9 执行器验收报告", "",
             "## Phase 9A：PWM 与执行器安全控制", "",
             f"- 日期：{metadata['date']}", f"- Git：`{metadata['commit']}`",
             f"- 固件/Python：{metadata['firmware']} / {__version__}",
             f"- 串口：{metadata['port']} @ {metadata['baud']} 8N1",
             "- PWM：TIM3_CH1 / PA6 / 50 Hz / 1 µs count",
             f"- 舵机型号：{metadata['servo_model']}",
             f"- 供电：{metadata['servo_supply']}",
             f"- 标定：{calibration}", f"- 手动结果：{manual}",
             f"- 600 s 数据：{soak}", f"- RTOS 前后快照：{rtos}",
             "- 过流检测：NOT_AVAILABLE（无电流传感器）",
             "- PWM 电气抖动：NOT_TESTED（需示波器/逻辑分析仪）", "",
             "## 分级结果", ""]
    lines += [f"- `{name}`: **{value}**" for name, value in checks.items()]
    lines += ["", "## Phase 9B：真实姿态闭环", "",
              "NOT_TESTED。当前没有确认舵机能改变 MPU6500 平台的明确单轴姿态，因此未加入 PID。"]
    (output / "phase09-actuator-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True); parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase09"))
    parser.add_argument("--servo-model", default="NOT_PROVIDED")
    parser.add_argument("--servo-supply", default="external 5V, common GND")
    args = parser.parse_args()
    if args.duration < 600: parser.error("Phase 9A soak must be at least 600 seconds")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=False).stdout.strip() or "unknown"
    metadata = {"date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "commit": commit, "firmware": None, "port": args.port, "baud": args.baud,
                "servo_model": args.servo_model, "servo_supply": args.servo_supply}
    checks: dict[str, str] = {}; manual: list[dict] = []; calibration: dict = {}; soak = {}; rtos = {}
    args.output.mkdir(parents=True, exist_ok=True); raw_path = args.output / "phase09-serial-raw.log"
    raw_path.write_text("", encoding="utf-8")
    print("SAFETY: no load; external 5V; common GND; PA6 Signal; clear hands and obstacles.")
    input("Verify PWM is Disabled and the servo does not move, then press Enter: ")
    client = DeviceClient(SerialTransport(args.port, args.baud), timeout=1.5, retries=2)
    try:
        info = client.request(commands.GET_DEVICE_INFO); metadata["firmware"] = f"{info[0]}.{info[1]}.{info[2]}"
        original = commands.RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
        initial = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
        checks["power_on_disabled"] = PASS if not initial.armed and initial.mode == "DISABLED" else FAIL
        try:
            action(client, commands.ACTUATOR_SET_TARGET,
                   struct.pack("<Bh", commands.ACTUATOR_OWNER_SERIAL, 1000))
            checks["unarmed_motion_rejected"] = FAIL
        except CommandError:
            checks["unarmed_motion_rejected"] = PASS
        write_checkpoint(args.output, metadata, checks, manual, calibration, soak,
                         "initial_safety_complete")
        if not original.telemetry_enabled: action(client, commands.SET_STREAM_STATE, b"\1")
        client.flush_input(); action(client, commands.ACTUATOR_ARM, owner())
        for pulse, seconds in ((1500, 5.0), (1450, 2.0), (1550, 2.0), (1400, 2.0), (1600, 2.0)):
            input(f"Ready to output {pulse} us. Press Enter only when safe: ")
            evidence = observe(client, seconds, pulse)
            status = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
            observed = input("Enter observed result: PASS, WARN, or FAIL: ").strip().upper()
            if observed not in (PASS, WARN, FAIL): observed = WARN
            manual.append({"pulse_us": pulse, "target_angle_deg": status.target_angle_deg,
                           "status": observed, "observed_state": status.state,
                           "current_pulse_us": status.current_pulse_us,
                           "timeout_count": status.timeout_count, "fault_count": status.fault_count,
                           "note": json.dumps(evidence, ensure_ascii=False)})
            write_checkpoint(args.output, metadata, checks, manual, calibration, soak,
                             f"manual_{pulse}_complete")
            if observed == FAIL: raise RuntimeError(f"User reported failure at {pulse} us; stopped")
        before_timeout = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
        set_pulse(client, 1550); time.sleep(1.3)
        after_timeout = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
        checks["command_timeout"] = PASS if (after_timeout.timeout_count > before_timeout.timeout_count and
                                              after_timeout.target_pulse_us == 1500) else FAIL
        action(client, commands.ACTUATOR_ESTOP, owner())
        stopped = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
        checks["estop"] = PASS if not stopped.armed and stopped.owner == "NONE" else FAIL
        if input("Start manual 25 us safe-range calibration? Enter YES to start; anything else skips: ").strip().upper() == "YES":
            class Opt: step_us=25; margin_us=50; output=args.output / "servo-calibration.json"
            calibration = _calibrate_range(client, Opt())
            checks["servo_range_calibration"] = PASS
        else:
            checks["servo_range_calibration"] = NOT_TESTED
        write_checkpoint(args.output, metadata, checks, manual, calibration, soak,
                         "manual_and_safety_complete")
        # 文本 RTOS 快照要求遥测关闭；不能沿用进入验收前的流状态。
        action(client, commands.SET_STREAM_STATE, b"\0")
    finally:
        try: action(client, commands.ACTUATOR_ESTOP, owner())
        except Exception: pass
        client.close()

    print("Capturing the pre-soak RTOS snapshot for about 4 seconds...")
    before = text_snapshot(args.port, args.baud, 4.0, raw_path)
    input(f"FINAL STEP: ready for {args.duration:.0f} s centered soak. Press Enter to start: ")
    client = DeviceClient(SerialTransport(args.port, args.baud), timeout=1.5, retries=2)
    try:
        action(client, commands.SET_STREAM_STATE, b"\1"); client.flush_input()
        action(client, commands.ACTUATOR_ARM, owner())
        soak = observe(client, args.duration, 1500)
        final_status = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
        soak["final_actuator"] = vars(final_status)
        checks["ten_minute_runtime"] = PASS if args.duration >= 600 and soak["motion_frames"] > 0 else FAIL
        checks["serial_parser"] = PASS if soak["crc_errors"] == 0 and soak["parser_errors"] == 0 else FAIL
        checks["application_no_fault"] = PASS if not soak["app_fault_seen"] and final_status.fault_count == 0 else FAIL
        checks["motion_continuity"] = PASS if soak["estimated_motion_gaps"] == 0 else WARN
        write_checkpoint(args.output, metadata, checks, manual, calibration, soak,
                         "ten_minute_soak_complete")
        action(client, commands.ACTUATOR_ESTOP, owner()); action(client, commands.SET_STREAM_STATE, b"\0")
    finally:
        try: action(client, commands.ACTUATOR_ESTOP, owner())
        except Exception: pass
        client.close()
    print("Capturing the post-soak RTOS snapshot for about 4 seconds...")
    after = text_snapshot(args.port, args.baud, 4.0, raw_path)
    rtos = {"before": before, "after": after,
            "run_delta": delta(before.get("run"), after.get("run")),
            "deadline_delta": delta(before.get("miss"), after.get("miss"))}
    checks["rtos_deadline"] = (PASS if rtos["deadline_delta"] is not None and
                               sum(rtos["deadline_delta"]) == 0 else FAIL)
    checks["rtos_stack"] = PASS if after.get("stack") and min(after["stack"]) >= 128 else FAIL
    checks["rtos_heap"] = PASS if after.get("heap") and min(after["heap"]) > 0 else FAIL
    checks["mqtt_retained_and_duplicate"] = NOT_TESTED  # 由独立真实 Broker 回归写入最终报告。
    checks["pwm_electrical_jitter"] = NOT_TESTED
    checks["overcurrent"] = "NOT_AVAILABLE"
    write_outputs(args.output, metadata, checks, manual, calibration, soak, rtos)
    print(json.dumps({"checks": checks, "report": str(args.output / 'phase09-actuator-report.md')},
                     ensure_ascii=False, indent=2))
    return 1 if FAIL in checks.values() else 0


if __name__ == "__main__": raise SystemExit(main())
