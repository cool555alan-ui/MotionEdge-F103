#!/usr/bin/env python3
"""Phase 9A 真实 Broker retained/duplicate 与 Node-RED 链路验收。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

from motionctl.mqtt_topics import TopicSet
from motionctl import commands
from motionctl.commands import decode_actuator_status
from motionctl.device import DeviceClient
from motionctl.transport import SerialTransport


def command_payload(request_id: str, command: str) -> bytes:
    now = datetime.now(timezone.utc)
    value = {
        "schema_version": 1,
        "request_id": request_id,
        "command": command,
        "issued_at": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "expires_at": (now + timedelta(seconds=30)).isoformat(
            timespec="milliseconds").replace("+00:00", "Z"),
        "params": {},
    }
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def node_red_metrics() -> dict:
    with urllib.request.urlopen(
            "http://127.0.0.1:1880/motionedge/api/metrics", timeout=5) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gateway-log", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    topics = TopicSet("motionedge-f103-01", "motionedge-gateway-01")
    responses: list[dict] = []
    condition = threading.Condition()

    def on_message(client, userdata, message):
        del client, userdata
        try:
            value = json.loads(bytes(message.payload))
        except Exception:
            return
        with condition:
            responses.append(value)
            condition.notify_all()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"phase9-validator-{uuid.uuid4()}")
    client.on_message = on_message
    gateway = None
    before_metrics = node_red_metrics()

    def wait_response(request_id: str, occurrence: int = 1, timeout: float = 8.0) -> dict:
        deadline = time.monotonic() + timeout
        with condition:
            while time.monotonic() < deadline:
                matches = [item for item in responses
                           if item.get("request_id") == request_id]
                if len(matches) >= occurrence:
                    return matches[occurrence - 1]
                condition.wait(deadline - time.monotonic())
        raise TimeoutError(f"MQTT response timeout: {request_id}")

    def publish(request_id: str, command: str, *, retain: bool = False) -> None:
        info = client.publish(topics.command, command_payload(request_id, command),
                              qos=1, retain=retain)
        info.wait_for_publish(timeout=5)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed: {info.rc}")

    result: dict = {"tested_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    try:
        # 先从串口读取基线，然后释放COM口给网关；不执行任何动作命令。
        direct = DeviceClient(SerialTransport("COM4", 115200), timeout=1.5, retries=2)
        try:
            initial_status = decode_actuator_status(
                direct.request(commands.ACTUATOR_GET_STATUS))
            initial_estop = initial_status.estop_count
        finally:
            direct.close()

        client.connect("127.0.0.1", 1884, 30)
        client.subscribe(topics.response, qos=1)
        client.loop_start()
        # 必须在网关订阅前写入retained消息，模拟网关/设备重启后的真实风险。
        retained_id = str(uuid.uuid4())
        publish(retained_id, "actuator_estop", retain=True)

        with args.gateway_log.open("w", encoding="utf-8") as log:
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(root / "host")
            gateway = subprocess.Popen(
                [sys.executable, "-m", "motionctl", "gateway", "run",
                 "--config", "config/motionedge-gateway.toml"],
                cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT,
                text=True)
            time.sleep(3.0)
            if gateway.poll() is not None:
                raise RuntimeError(f"gateway exited early: {gateway.returncode}")
            retained = wait_response(retained_id)
            # 清除Broker中的retained测试消息，避免下次网关启动再次收到。
            client.publish(topics.command, b"", qos=1, retain=True).wait_for_publish(5)

            after_retained_id = str(uuid.uuid4())
            publish(after_retained_id, "actuator_status")
            after_retained = wait_response(after_retained_id)
            retained_estop = int(after_retained["result"]["estop_count"])

            duplicate_id = str(uuid.uuid4())
            publish(duplicate_id, "actuator_estop")
            first = wait_response(duplicate_id, 1)
            publish(duplicate_id, "actuator_estop")
            second = wait_response(duplicate_id, 2)

            final_id = str(uuid.uuid4())
            publish(final_id, "actuator_status")
            final = wait_response(final_id)
            final_estop = int(final["result"]["estop_count"])
            time.sleep(8.0)
            after_metrics = node_red_metrics()

            checks = {
                "retained_rejected": (
                    not retained.get("ok", True)
                    and retained.get("error") == "RETAINED_COMMAND_REJECTED"),
                "retained_not_executed": retained_estop == initial_estop,
                "duplicate_first_executed": first.get("ok") is True,
                "duplicate_response_cached": first == second,
                "duplicate_not_reexecuted": final_estop == retained_estop + 1,
                "node_red_motion_link": int(after_metrics.get("motion_received", 0))
                    > int(before_metrics.get("motion_received", 0)),
                "node_red_invalid_json_zero": int(after_metrics.get("invalid_json", 0)) == 0,
                "node_red_schema_error_zero": int(after_metrics.get("schema_error", 0)) == 0,
            }
            result.update({
                "checks": {name: "PASS" if passed else "FAIL"
                           for name, passed in checks.items()},
                "initial_estop_count": initial_estop,
                "after_retained_estop_count": retained_estop,
                "final_estop_count": final_estop,
                "retained_response": retained,
                "duplicate_first_response": first,
                "duplicate_second_response": second,
                "node_red_before": before_metrics,
                "node_red_after": after_metrics,
                "passed": all(checks.values()),
            })
    finally:
        try:
            client.publish(topics.command, b"", qos=1, retain=True).wait_for_publish(2)
        except Exception:
            pass
        client.disconnect()
        client.loop_stop()
        if gateway is not None and gateway.poll() is None:
            gateway.terminate()
            try:
                gateway.wait(timeout=5)
            except subprocess.TimeoutExpired:
                gateway.kill()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
