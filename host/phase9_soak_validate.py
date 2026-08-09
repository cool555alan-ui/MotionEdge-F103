#!/usr/bin/env python3
"""Phase 9A 中心位自动压力测试，不代替人工舵机行程确认。"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from motionctl import commands
from motionctl.commands import decode_actuator_status
from motionctl.device import DeviceClient
from motionctl.transport import SerialTransport
from phase9_hardware_validate import action, delta, observe, owner, text_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-log", type=Path, required=True)
    args = parser.parse_args()
    if args.duration < 10.0:
        parser.error("duration must be at least 10 seconds")

    started = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_log.parent.mkdir(parents=True, exist_ok=True)
    args.raw_log.write_text("", encoding="utf-8")

    # 文本快照前关闭二进制遥测，避免把协议帧误解为终端乱码。
    client = DeviceClient(SerialTransport(args.port, args.baud), timeout=1.5, retries=2)
    try:
        action(client, commands.ACTUATOR_ESTOP, owner())
        action(client, commands.SET_STREAM_STATE, b"\0")
    finally:
        client.close()
    before = text_snapshot(args.port, args.baud, 4.0, args.raw_log)

    client = DeviceClient(SerialTransport(args.port, args.baud), timeout=1.5, retries=2)
    soak: dict = {}
    try:
        action(client, commands.SET_STREAM_STATE, b"\1")
        client.flush_input()
        action(client, commands.ACTUATOR_ARM, owner())
        soak = observe(client, args.duration, 1500)
        soak["final_actuator"] = vars(
            decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS)))
    finally:
        try:
            action(client, commands.ACTUATOR_ESTOP, owner())
            action(client, commands.SET_STREAM_STATE, b"\0")
        except Exception:
            pass
        client.close()

    # 等待最后一条状态日志，再读取RTOS和通信累计计数。
    time.sleep(0.2)
    after = text_snapshot(args.port, args.baud, 4.0, args.raw_log)
    result = {
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "duration_s": args.duration,
        "soak": soak,
        "rtos_before": before,
        "rtos_after": after,
        "run_delta": delta(before.get("run"), after.get("run")),
        "deadline_delta": delta(before.get("miss"), after.get("miss")),
        "comm_delta": delta(before.get("comm"), after.get("comm")),
        "uart_delta": delta(before.get("uart"), after.get("uart")),
        "binary_deadline_delta": soak.get("deadline_delta"),
    }
    result["passed"] = bool(
        soak.get("motion_frames", 0) > 0
        and soak.get("keepalive_ack_timeouts", 0) == 0
        and soak.get("crc_errors", 1) == 0
        and soak.get("parser_errors", 1) == 0
        and not soak.get("app_fault_seen", True)
        and result["binary_deadline_delta"] is not None
        and sum(result["binary_deadline_delta"]) == 0
        and result["comm_delta"] is not None
        and sum(result["comm_delta"]) == 0
        and result["uart_delta"] is not None
        and sum(result["uart_delta"]) == 0
    )
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
