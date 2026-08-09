#!/usr/bin/env python3
"""Phase 9A 无需搜索机械极限的安全状态机实机检查。"""

from __future__ import annotations

import argparse
import json
import struct
import time
from datetime import datetime
from pathlib import Path

from motionctl import commands
from motionctl.commands import decode_actuator_status
from motionctl.device import DeviceClient
from motionctl.errors import CommandError
from motionctl.transport import SerialTransport


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    client = DeviceClient(SerialTransport(args.port, 115200), timeout=1.5, retries=2)
    owner = bytes((commands.ACTUATOR_OWNER_SERIAL,))
    checks: dict[str, bool] = {}
    evidence: dict = {"tested_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    try:
        initial = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
        checks["initial_disabled"] = (
            not initial.armed and initial.mode == "DISABLED" and initial.owner == "NONE")
        try:
            client.request(commands.ACTUATOR_SET_RAW_PULSE,
                           struct.pack("<BH", commands.ACTUATOR_OWNER_SERIAL, 1500),
                           retry=False)
            checks["unarmed_command_rejected"] = False
        except CommandError:
            checks["unarmed_command_rejected"] = True

        client.request(commands.ACTUATOR_ARM, owner, retry=False)
        before = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
        client.request(commands.ACTUATOR_SET_RAW_PULSE,
                       struct.pack("<BH", commands.ACTUATOR_OWNER_SERIAL, 1550),
                       retry=False)
        time.sleep(1.7)
        after_timeout = decode_actuator_status(
            client.request(commands.ACTUATOR_GET_STATUS))
        checks["command_timeout_centers"] = (
            after_timeout.timeout_count == before.timeout_count + 1
            and after_timeout.target_pulse_us == 1500
            and after_timeout.current_pulse_us == 1500)

        client.request(commands.ACTUATOR_ESTOP, owner, retry=False)
        stopped = decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS))
        checks["estop_disables_pwm"] = (
            not stopped.armed and stopped.mode == "DISABLED"
            and stopped.owner == "NONE" and stopped.state == "DISABLED")
        evidence.update({"initial": vars(initial), "before_timeout": vars(before),
                         "after_timeout": vars(after_timeout), "final": vars(stopped)})
    finally:
        try:
            client.request(commands.ACTUATOR_ESTOP, owner, retry=False)
            client.request(commands.SET_STREAM_STATE, b"\0", retry=False)
        except Exception:
            pass
        client.close()
    evidence["checks"] = {name: "PASS" if passed else "FAIL"
                          for name, passed in checks.items()}
    evidence["passed"] = all(checks.values())
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
