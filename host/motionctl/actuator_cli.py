"""Phase 9A 安全执行器命令；所有动作命令均禁止自动重试。"""

from __future__ import annotations

import json
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import commands
from .commands import decode_actuator_status
from .models import stable_dict


def add_actuator_parser(subs, connection) -> None:
    actuator = subs.add_parser("actuator")
    actions = actuator.add_subparsers(dest="actuator_command", required=True)
    for name in ("status", "arm", "disarm", "center", "stop"):
        item = actions.add_parser(name); connection(item)
    angle = actions.add_parser("set-angle"); connection(angle)
    angle.add_argument("--angle", type=float, required=True,
                       help="目标角度，单位 deg，当前软件窗口 -45..45")
    pulse = actions.add_parser("set-pulse"); connection(pulse)
    pulse.add_argument("--pulse-us", type=int, required=True)
    calibrate = actions.add_parser("calibrate-range"); connection(calibrate)
    calibrate.add_argument("--step-us", type=int, choices=(25, 50), default=25)
    calibrate.add_argument("--margin-us", type=int, default=50)
    calibrate.add_argument("--output", type=Path)


def _owner_payload() -> bytes:
    return bytes((commands.ACTUATOR_OWNER_SERIAL,))


def _request_action(client, command: int, payload: bytes = b"") -> bytes:
    return client.request(command, payload, retry=False)


def _set_pulse(client, pulse_us: int) -> None:
    if not 1000 <= pulse_us <= 2000:
        raise ValueError("pulse must be within the 1000..2000 us software window")
    _request_action(client, commands.ACTUATOR_SET_RAW_PULSE,
                    struct.pack("<BH", commands.ACTUATOR_OWNER_SERIAL, pulse_us))


def _calibrate_range(client, args) -> dict:
    print("WARNING: diagnostic pulse control. Use no load, external 5V, common GND, and PA6 Signal.")
    input("Clear hands and obstacles, then press Enter. Ctrl+C aborts at any time.")
    _request_action(client, commands.ACTUATOR_ARM, _owner_payload())
    _set_pulse(client, 1500)
    measured_min = measured_max = 1500
    try:
        print("Explore below 1500 us. Each step lasts 0.8 s and then returns to center.")
        while measured_min - args.step_us >= 1000:
            candidate = measured_min - args.step_us
            input(f"Check noise, current, jitter and collision. Enter tests {candidate} us: ")
            _set_pulse(client, candidate); time.sleep(0.8); _set_pulse(client, 1500)
            if input("Enter y only if this step was safe; anything else stops this side: ").strip().lower() != "y": break
            measured_min = candidate
        _set_pulse(client, 1500)
        print("Returned to center. Now explore above 1500 us.")
        while measured_max + args.step_us <= 2000:
            candidate = measured_max + args.step_us
            input(f"Press Enter to test {candidate} us briefly: ")
            _set_pulse(client, candidate); time.sleep(0.8); _set_pulse(client, 1500)
            if input("Enter y only if this step was safe; anything else stops this side: ").strip().lower() != "y": break
            measured_max = candidate
        _set_pulse(client, 1500)
        result = {
            "validated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "measured_min_us": measured_min,
            "measured_center_us": 1500,
            "measured_max_us": measured_max,
            "recommended_safe_min_us": min(1500, measured_min + args.margin_us),
            "recommended_safe_max_us": max(1500, measured_max - args.margin_us),
            "margin_us": args.margin_us,
            "step_us": args.step_us,
            "user_observation_required": True,
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        return result
    finally:
        try: _set_pulse(client, 1500)
        finally: _request_action(client, commands.ACTUATOR_DISARM, _owner_payload())


def run_actuator(args, client) -> dict:
    action = args.actuator_command
    if action == "status":
        return stable_dict(decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS)))
    if action == "calibrate-range":
        return _calibrate_range(client, args)
    command = {
        "arm": commands.ACTUATOR_ARM,
        "disarm": commands.ACTUATOR_DISARM,
        "center": commands.ACTUATOR_CENTER,
        "stop": commands.ACTUATOR_ESTOP,
    }.get(action)
    payload = _owner_payload()
    if action == "set-angle":
        if not -45.0 <= args.angle <= 45.0:
            raise ValueError("angle must be within -45..45 degrees")
        command = commands.ACTUATOR_SET_TARGET
        payload = struct.pack("<Bh", commands.ACTUATOR_OWNER_SERIAL,
                              round(args.angle * 100.0))
    elif action == "set-pulse":
        print("WARNING: set-pulse is diagnostic and remains limited to 1000..2000 us.", file=sys.stderr)
        if not 1000 <= args.pulse_us <= 2000:
            raise ValueError("pulse must be within 1000..2000 us")
        command = commands.ACTUATOR_SET_RAW_PULSE
        payload = struct.pack("<BH", commands.ACTUATOR_OWNER_SERIAL,
                              args.pulse_us)
    assert command is not None
    _request_action(client, command, payload)
    return stable_dict(decode_actuator_status(client.request(commands.ACTUATOR_GET_STATUS)))
