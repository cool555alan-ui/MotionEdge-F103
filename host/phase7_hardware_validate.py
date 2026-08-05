#!/usr/bin/env python3
"""Interactive Phase 7 acceptance using the real serial device and local MQTT stack."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import importlib.metadata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

from motionctl import commands
from motionctl.commands import RuntimeConfig
from motionctl.device import DeviceClient
from motionctl.gateway_config import load_gateway_config
from motionctl.mqtt_topics import TopicSet
from motionctl.transport import SerialTransport


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * q)]


class Capture:
    def __init__(self, path: Path, topics: TopicSet) -> None:
        self.path, self.topics = path, topics
        self.lock = threading.Lock()
        self.messages: list[dict] = []
        self.responses: dict[str, dict] = {}
        self.response_event = threading.Condition(self.lock)
        self.connected = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"phase7-validator-{uuid.uuid4().hex[:8]}")
        self.client.on_connect = self._connect
        self.client.on_message = self._message

    def _connect(self, client, userdata, flags, reason_code, properties) -> None:
        if getattr(reason_code, "value", reason_code) == 0:
            client.subscribe("motionedge/v1/#", qos=1)
            self.connected.set()

    def _message(self, client, userdata, message) -> None:
        received_ms = int(time.time() * 1000)
        raw = bytes(message.payload)
        try:
            payload = json.loads(raw) if raw[:1] in (b"{", b"[") else raw.decode("utf-8", "replace")
            parse_error = False
        except Exception:
            payload, parse_error = raw.decode("utf-8", "replace"), True
        row = {"received_unix_ms": received_ms, "topic": message.topic,
               "qos": message.qos, "retain": bool(message.retain),
               "parse_error": parse_error, "payload": payload}
        with self.response_event:
            self.messages.append(row)
            if message.topic == self.topics.response and isinstance(payload, dict):
                request_id = payload.get("request_id")
                if request_id:
                    self.responses[request_id] = payload
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.response_event.notify_all()

    def start(self, host: str, port: int) -> None:
        self.path.write_text("", encoding="utf-8")
        self.client.connect(host, port, 30)
        self.client.loop_start()
        if not self.connected.wait(5):
            raise RuntimeError("MQTT validation subscriber did not connect")

    def stop(self) -> None:
        try:
            self.client.disconnect()
        finally:
            self.client.loop_stop()

    def wait_payload(self, topic: str, predicate, timeout: float = 15.0,
                     after_unix_ms: int = 0) -> dict:
        deadline = time.monotonic() + timeout
        with self.response_event:
            while time.monotonic() < deadline:
                for row in reversed(self.messages):
                    if (row["topic"] == topic and row["received_unix_ms"] >= after_unix_ms
                            and predicate(row["payload"])):
                        return row
                self.response_event.wait(min(0.25, max(0, deadline - time.monotonic())))
        raise TimeoutError(f"timeout waiting for {topic}")

    def command(self, command: str, params: dict | None = None, *, request_id: str | None = None,
                expired: bool = False, retain: bool = False, timeout: float = 5.0) -> dict:
        request_id = request_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        body = {"schema_version": 1, "request_id": request_id, "command": command,
                "issued_at": (now - timedelta(seconds=60) if expired else now).isoformat(),
                "expires_at": (now - timedelta(seconds=30) if expired else now + timedelta(seconds=30)).isoformat(),
                "params": params or {}}
        started = time.monotonic_ns()
        info = self.client.publish(self.topics.command, json.dumps(body), qos=1, retain=retain)
        info.wait_for_publish(timeout=2)
        deadline = time.monotonic() + timeout
        with self.response_event:
            while request_id not in self.responses and time.monotonic() < deadline:
                self.response_event.wait(min(0.2, max(0, deadline - time.monotonic())))
            response = self.responses.get(request_id)
        if response is None:
            return {"request_id": request_id, "command": command, "ok": False,
                    "error": "VALIDATOR_TIMEOUT", "round_trip_ms": (time.monotonic_ns()-started)/1e6}
        return {**response, "round_trip_ms": (time.monotonic_ns()-started)/1e6}


def powershell(root: Path, script: str) -> None:
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                             str(root / "tools" / script)], cwd=root,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if result.returncode:
        raise RuntimeError(f"{script} failed with exit code {result.returncode}")


def start_gateway(root: Path, config_path: Path, log_path: Path):
    stream = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen([sys.executable, "-m", "motionctl", "gateway", "run",
                                "--config", str(config_path)], cwd=root, stdout=stream,
                               stderr=subprocess.STDOUT, text=True)
    return process, stream


def stop_gateway(process, stream, graceful: bool = True) -> None:
    if process.poll() is None:
        process.terminate()
        try: process.wait(5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(3)
    stream.close()


def mqtt_retained_probe(host: str, port: int, topics: TopicSet) -> dict[str, bool]:
    found: dict[str, bool] = {}
    event = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"phase7-retained-{uuid.uuid4().hex[:8]}")
    def on_connect(instance, userdata, flags, reason_code, properties):
        instance.subscribe("motionedge/v1/#", qos=1)
    def on_message(instance, userdata, message):
        found[message.topic] = bool(message.retain)
        if topics.meta in found and topics.state in found and topics.motion not in found:
            event.set()
    client.on_connect, client.on_message = on_connect, on_message
    client.connect(host, port, 30); client.loop_start(); event.wait(2.0)
    client.disconnect(); client.loop_stop()
    return found


def direct_stream_state(port: str, baud: int, enabled: bool | None = None) -> bool:
    with DeviceClient(SerialTransport(port, baud), timeout=1.5, retries=3) as device:
        config = RuntimeConfig.unpack(device.request(commands.GET_CONFIG))
        if enabled is not None and config.telemetry_enabled != enabled:
            device.request(commands.SET_STREAM_STATE, bytes((int(enabled),)), retry=False)
            config = RuntimeConfig.unpack(device.request(commands.GET_CONFIG))
        return config.telemetry_enabled


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/motionedge-gateway.toml"))
    parser.add_argument("--seconds", type=float, default=600.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase07/final-validation"))
    parser.add_argument("--timed-prompts", action="store_true",
                        help="use fixed operator windows instead of waiting for console input")
    args = parser.parse_args()
    if args.seconds < 600:
        parser.error("real Phase 7 validation must run for at least 600 seconds")
    root = Path(__file__).resolve().parents[1]
    config_path = (root / args.config).resolve() if not args.config.is_absolute() else args.config
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output
    output.mkdir(parents=True, exist_ok=True)
    config = load_gateway_config(config_path)
    topics = TopicSet(config.gateway.device_id, config.gateway.gateway_id)
    summary_path = output / "phase07-validation-summary.json"
    summary_path.write_text(json.dumps({"result": "RUNNING", "started_at": datetime.now().astimezone().isoformat()}, indent=2), encoding="utf-8")
    original_stream = direct_stream_state(config.serial.port, config.serial.baud)
    print("\n前30秒保持面包板静止，随后缓慢向左、向右、向前、向后倾斜，最后恢复静止。")
    if args.timed_prompts:
        print("5秒后自动开始；请立即保持面包板静止。", flush=True); time.sleep(5)
    else:
        input("确认开发板已连接并保持静止后，按 Enter 开始真实验收：")
    capture = Capture(output / "mqtt-capture.jsonl", topics)
    capture.start(config.mqtt.host, config.mqtt.port)
    gateway_log = output / "gateway.log"; gateway_log.write_text("", encoding="utf-8")
    gateway, gateway_stream = start_gateway(root, config_path, gateway_log)
    command_rows: list[dict] = []
    memory_samples: list[int] = []
    started = time.monotonic(); broker_recovery_s = None; lwt = False; stable_message_index = 0
    nodered_motion_baseline = 0
    try:
        capture.wait_payload(topics.gateway_availability, lambda value: value == "online", 20)
        capture.wait_payload(topics.device_availability, lambda value: value == "online", 20)
        capture.wait_payload(topics.meta, lambda value: isinstance(value, dict), 10)
        capture.wait_payload(topics.state, lambda value: isinstance(value, dict), 10)
        print("Node-RED 页面：http://127.0.0.1:1880/motionedge/")
        if not args.timed_prompts:
            input("请确认页面可打开且 Roll/Pitch 正在刷新，然后按 Enter：")
        time.sleep(30)
        if args.timed_prompts:
            print("现在开始30秒运动窗口：缓慢完成左、右、前、后倾斜，最后恢复静止。", flush=True)
            time.sleep(30)
        else:
            input("现在缓慢完成左、右、前、后倾斜并恢复静止；完成后按 Enter：")

        for index in range(100):
            row = capture.command("ping"); row["index"] = index + 1; command_rows.append(row)
            if gateway.poll() is not None: raise RuntimeError("gateway exited during PING series")
        for name in ("get_status", "get_config"):
            command_rows.append(capture.command(name))
        command_rows.append(capture.command("set_stream_state", {"enabled": True}))
        command_rows.append(capture.command("set_stream_state", {"enabled": False}))
        command_rows.append(capture.command("set_stream_state", {"enabled": True}))
        if args.timed_prompts:
            print("5秒后执行校准；请立即保持面包板完全静止。", flush=True); time.sleep(5)
        else:
            input("请再次保持面包板完全静止，确认后按 Enter 执行 START_CALIBRATION：")
        command_rows.append(capture.command("start_calibration", timeout=10))

        duplicate_id = str(uuid.uuid4())
        first = capture.command("get_status", request_id=duplicate_id)
        second = capture.command("get_status", request_id=duplicate_id)
        first["case"], second["case"] = "duplicate_first", "duplicate_replay"
        command_rows.extend((first, second))
        expired = capture.command("start_calibration", expired=True)
        expired["case"] = "expired_side_effect"; command_rows.append(expired)

        print("正在执行 Broker 断线 5 秒恢复测试……")
        powershell(root, "stop-phase07-broker.ps1")
        outage_started = time.monotonic(); time.sleep(5)
        broker_started_ms = int(time.time() * 1000)
        powershell(root, "start-phase07-broker.ps1")
        capture.wait_payload(topics.gateway_availability, lambda value: value == "online", 15,
                             after_unix_ms=broker_started_ms)
        broker_recovery_s = time.monotonic() - outage_started - 5

        print("正在执行网关异常终止、LWT 与 retained 副作用拒绝测试……")
        killed_ms = int(time.time() * 1000)
        gateway.terminate(); gateway.wait(5); gateway_stream.close()
        capture.wait_payload(topics.gateway_availability, lambda value: value == "offline", 10,
                             after_unix_ms=killed_ms); lwt = True
        retained_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        retained_body = {"schema_version": 1, "request_id": retained_id,
                         "command": "start_calibration", "issued_at": now.isoformat(),
                         "expires_at": (now + timedelta(seconds=30)).isoformat(), "params": {}}
        info = capture.client.publish(topics.command, json.dumps(retained_body), qos=1, retain=True)
        info.wait_for_publish(2)
        restarted_ms = int(time.time() * 1000)
        gateway, gateway_stream = start_gateway(root, config_path, gateway_log)
        capture.wait_payload(topics.gateway_availability, lambda value: value == "online", 20,
                             after_unix_ms=restarted_ms)
        deadline = time.monotonic() + 10
        while retained_id not in capture.responses and time.monotonic() < deadline: time.sleep(0.1)
        retained = capture.responses.get(retained_id, {"request_id": retained_id, "command": "start_calibration", "ok": False, "error": "VALIDATOR_TIMEOUT"})
        retained["case"] = "retained_side_effect"; command_rows.append(retained)
        capture.client.publish(topics.command, "", qos=1, retain=True).wait_for_publish(2)
        post_restart_id = str(uuid.uuid4())
        command_rows.append(capture.command("get_status", request_id=post_restart_id))
        replay = capture.command("get_status", request_id=post_restart_id)
        replay["case"] = "post_restart_duplicate_replay"; command_rows.append(replay)
        command_rows.append(capture.command("set_stream_state", {"enabled": False}))
        powershell(root, "stop-phase07-node-red.ps1")
        powershell(root, "start-phase07-node-red.ps1")
        powershell(root, "import-node-red-phase07.ps1")
        with urllib.request.urlopen("http://127.0.0.1:1880/motionedge/api/metrics", timeout=5) as response:
            nodered_motion_baseline = int(json.load(response).get("motion_received", 0))
        stable_message_index = len(capture.messages)
        command_rows.append(capture.command("set_stream_state", {"enabled": True}))

        while time.monotonic() - started < args.seconds:
            if gateway.poll() is not None: raise RuntimeError("gateway crashed during 600-second run")
            try:
                import psutil
                memory_samples.append(psutil.Process(gateway.pid).memory_info().rss)
            except Exception: pass
            time.sleep(min(5, max(0.1, args.seconds - (time.monotonic() - started))))
    finally:
        stop_gateway(gateway, gateway_stream)
        capture.stop()
        try: direct_stream_state(config.serial.port, config.serial.baud, original_stream)
        except Exception as exc: print(f"WARN: final stream restore failed: {exc}")

    elapsed = time.monotonic() - started
    all_motion = [row for row in capture.messages if row["topic"] == topics.motion and isinstance(row["payload"], dict)]
    motion = [row for row in capture.messages[stable_message_index:]
              if row["topic"] == topics.motion and isinstance(row["payload"], dict)]
    health = [row for row in capture.messages if row["topic"] == topics.health and isinstance(row["payload"], dict)]
    sequences = [int(row["payload"]["sequence"]) for row in motion]
    gaps = sum(1 for a, b in zip(sequences, sequences[1:]) if b - a != 10)
    regressions = sum(1 for a, b in zip(sequences, sequences[1:]) if b < a)
    duplicates = sum(1 for a, b in zip(sequences, sequences[1:]) if b == a)
    device_times = [int(row["payload"]["device_timestamp_ms"]) for row in motion]
    frequency = ((len(device_times)-1) * 1000 / (device_times[-1]-device_times[0])
                 if len(device_times) > 1 and device_times[-1] > device_times[0] else 0)
    local_latency = [row["received_unix_ms"] - row["payload"]["gateway_published_unix_ms"] for row in motion]
    ping = [row for row in command_rows if row.get("command") == "ping"]
    ping_rtt = [row["round_trip_ms"] for row in ping if row.get("ok")]
    retained_probe = mqtt_retained_probe(config.mqtt.host, config.mqtt.port, topics)
    with urllib.request.urlopen("http://127.0.0.1:1880/motionedge/api/metrics", timeout=5) as response:
        node_metrics = json.load(response)
    gateway_metrics = next((row["payload"] for row in reversed(capture.messages)
                            if row["topic"] == topics.gateway_metrics and isinstance(row["payload"], dict)), {})
    parse_errors = sum(bool(row["parse_error"]) for row in capture.messages)
    health_crc = [int(row["payload"].get("protocol_crc_errors", 0)) for row in health]
    health_overflow = [int(row["payload"].get("uart_rx_overflows", 0)) for row in health]
    crc_delta = health_crc[-1] - health_crc[0] if health_crc else None
    overflow_delta = health_overflow[-1] - health_overflow[0] if health_overflow else None
    rolls = [float(row["payload"]["roll_deg"]) for row in all_motion]
    pitches = [float(row["payload"]["pitch_deg"]) for row in all_motion]
    accel_norms = [math.sqrt(sum(float(value) ** 2 for value in row["payload"]["accel_mg"].values()))
                   for row in all_motion]
    nodered_motion = int(node_metrics.get("motion_received", 0)) - nodered_motion_baseline
    loss = abs(len(motion) - nodered_motion)
    checks = {
        "gateway_online": "PASS",
        "device_online": "PASS",
        "meta_state_retained": "PASS" if retained_probe.get(topics.meta) and retained_probe.get(topics.state) else "FAIL",
        "telemetry_not_retained": "PASS" if topics.motion not in retained_probe else "FAIL",
        "duration_600_seconds": "PASS" if elapsed >= 600 else "FAIL",
        "telemetry_frequency": "PASS" if 9.5 <= frequency <= 10.5 else "FAIL",
        "sequence_integrity": "PASS" if gaps == duplicates == regressions == 0 else "FAIL",
        "json_schema_errors": "PASS" if parse_errors == 0 and node_metrics.get("invalid_json", 0) == 0 and node_metrics.get("schema_error", 0) == 0 else "FAIL",
        "node_red_sequence": "PASS" if node_metrics.get("duplicate_received", 0) == 0 and node_metrics.get("sequence_regression", 0) == 0 and node_metrics.get("sequence_gap", 0) == 0 else "FAIL",
        "device_crc_no_increase": "PASS" if crc_delta == 0 else "FAIL",
        "uart_overflow_no_increase": "PASS" if overflow_delta == 0 else "FAIL",
        "motion_range": "PASS" if rolls and pitches and (max(rolls)-min(rolls) > 10 or max(pitches)-min(pitches) > 10) else "FAIL",
        "ping_100_success": "PASS" if len(ping) == 100 and all(row.get("ok") for row in ping) else "FAIL",
        "command_p95_under_500_ms": "PASS" if (percentile(ping_rtt, .95) or math.inf) < 500 else "FAIL",
        "duplicate_not_reexecuted": "PASS" if second.get("ok") and gateway_metrics.get("duplicate_commands", 0) >= 1 else "FAIL",
        "expired_rejected": "PASS" if expired.get("error") == "COMMAND_EXPIRED" else "FAIL",
        "retained_rejected": "PASS" if retained.get("error") == "RETAINED_COMMAND_REJECTED" else "FAIL",
        "broker_recovery_under_10_s": "PASS" if broker_recovery_s is not None and broker_recovery_s <= 10 else "FAIL",
        "lwt_offline": "PASS" if lwt else "FAIL",
        "node_red_message_loss": "PASS" if loss == 0 else "FAIL",
        "local_latency_p95": "PASS" if (percentile(local_latency, .95) or math.inf) <= 100 else ("WARN" if (percentile(local_latency, .95) or math.inf) <= 250 else "FAIL"),
        "stream_state_restored": "PASS" if direct_stream_state(config.serial.port, config.serial.baud) == original_stream else "FAIL",
        "gateway_memory_bounded": "PASS" if not memory_samples or max(memory_samples)-min(memory_samples) < 32*1024*1024 else "FAIL",
    }
    result = "FAIL" if "FAIL" in checks.values() else "WARN" if "WARN" in checks.values() else "PASS"
    git_hash = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                              capture_output=True, check=False).stdout.strip()
    mosquitto_version = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "$p=(Get-Command mosquitto.exe -ErrorAction SilentlyContinue).Source;if($p){& $p --help 2>&1|Select-Object -First 1}"],
        text=True, capture_output=True, check=False).stdout.strip()
    node_red_version = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "node-red.cmd --version"],
        text=True, capture_output=True, check=False).stdout.strip()
    summary = {"result": result, "validation_date": datetime.now().astimezone().isoformat(),
               "environment": {"git_commit": git_hash, "motionctl": "0.7.0", "firmware": "0.6.0",
                               "paho_mqtt": importlib.metadata.version("paho-mqtt"),
                               "mosquitto": mosquitto_version, "node_red": node_red_version},
               "duration_seconds": elapsed, "serial": {"port": config.serial.port, "baud": config.serial.baud},
               "broker": f"{config.mqtt.host}:{config.mqtt.port}", "motion_frames": len(all_motion),
               "stable_motion_frames": len(motion),
               "health_frames": len(health), "node_red_motion": nodered_motion, "message_loss": loss,
               "frequency_hz": frequency, "sequence": {"gaps": gaps, "duplicates": duplicates, "regressions": regressions},
               "attitude_deg": {"roll_min": min(rolls, default=None), "roll_max": max(rolls, default=None),
                                "pitch_min": min(pitches, default=None), "pitch_max": max(pitches, default=None)},
               "accel_norm_mg": {"mean": statistics.fmean(accel_norms) if accel_norms else None,
                                 "min": min(accel_norms, default=None), "max": max(accel_norms, default=None)},
               "device_error_delta": {"protocol_crc": crc_delta, "uart_overflow": overflow_delta},
               "topic_counts": dict(Counter(row["topic"] for row in capture.messages)),
               "local_latency_ms": {"p50": percentile(local_latency, .5), "p95": percentile(local_latency, .95), "max": max(local_latency, default=None)},
               "ping": {"logical": len(ping), "success": sum(bool(row.get("ok")) for row in ping),
                         "transport_attempts": sum(int(row.get("transport_attempts", 0)) for row in ping),
                         "safe_retries": sum(max(0, int(row.get("transport_attempts", 0))-1) for row in ping),
                         "rtt_p50_ms": percentile(ping_rtt, .5), "rtt_p95_ms": percentile(ping_rtt, .95), "rtt_max_ms": max(ping_rtt, default=None)},
               "broker_recovery_seconds": broker_recovery_s, "lwt": lwt,
               "gateway_memory_bytes": {"min": min(memory_samples, default=None), "max": max(memory_samples, default=None)},
               "gateway_metrics": gateway_metrics, "node_red_metrics": node_metrics, "checks": checks}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (output / "gateway-metrics.json").write_text(json.dumps(gateway_metrics, indent=2)+"\n", encoding="utf-8")
    (output / "node-red-metrics.json").write_text(json.dumps(node_metrics, indent=2)+"\n", encoding="utf-8")
    with (output / "command-results.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["index", "case", "request_id", "command", "ok", "error", "round_trip_ms", "device_elapsed_ms", "transport_attempts"]
        writer = csv.DictWriter(stream, fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(command_rows)
    with (output / "latency-metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream); writer.writerow(["metric", "count", "p50_ms", "p95_ms", "max_ms"])
        writer.writerow(["gateway_to_nodered", len(local_latency), percentile(local_latency,.5), percentile(local_latency,.95), max(local_latency,default=None)])
        writer.writerow(["mqtt_command_round_trip", len(ping_rtt), percentile(ping_rtt,.5), percentile(ping_rtt,.95), max(ping_rtt,default=None)])
    report = f"""# Phase 7 real-hardware validation\n\n- Result: **{result}**\n- Date: {summary['validation_date']}\n- Device: STM32F103C8T6 + MPU6500, firmware 0.6.0\n- Gateway: motionctl 0.7.0\n- Serial: {config.serial.port}, {config.serial.baud} 8N1\n- Broker: {summary['broker']} (loopback, no TLS)\n- Duration: {elapsed:.1f} s\n\n## Data\n\n- Total motion / health: {len(all_motion)} / {len(health)}\n- Stable comparison gateway / Node-RED: {len(motion)} / {nodered_motion}\n- Frequency: {frequency:.4f} Hz; loss {loss}; duplicate {duplicates}; regression {regressions}; gap {gaps}\n- Local gateway-to-Node-RED latency P50/P95/max: {percentile(local_latency,.5)} / {percentile(local_latency,.95)} / {max(local_latency,default=None)} ms\n- PING success: {sum(bool(row.get('ok')) for row in ping)}/{len(ping)}; P50/P95/max: {percentile(ping_rtt,.5)} / {percentile(ping_rtt,.95)} / {max(ping_rtt,default=None)} ms\n- Broker recovery after 5 s outage: {broker_recovery_s:.3f} s; LWT: {lwt}\n\n## Acceptance matrix\n\n""" + "\n".join(f"- {name}: {value}" for name,value in checks.items()) + "\n\nThe latency is a same-host local-broker observation, not public-internet performance.\n"
    (output / "phase07-validation-report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result in ("PASS", "WARN") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        root = Path(__file__).resolve().parents[1]
        failure = {"result": "FAIL", "error": str(exc),
                   "failed_at": datetime.now().astimezone().isoformat(),
                   "traceback": traceback.format_exc()}
        failure_dir = root / "artifacts" / "phase07" / "final-validation"
        failure_dir.mkdir(parents=True, exist_ok=True)
        (failure_dir / "phase07-validation-summary.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(failure["traceback"], file=sys.stderr, flush=True)
        raise SystemExit(2)
