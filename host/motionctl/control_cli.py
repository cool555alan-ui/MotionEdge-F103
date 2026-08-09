"""Phase 9B姿态驱动舵机控制命令；所有写命令均禁止自动重试。"""

from __future__ import annotations

import dataclasses
import struct
from pathlib import Path

from . import commands
from .commands import PidConfig, decode_control_status
from .models import stable_dict

AXIS = {"roll": 0, "pitch": 1}
DIRECTION = {"normal": 0, "reverse": 1}
INTEGRAL = {"disabled": 0, "bounded": 1, "leaky": 2}


def add_control_parser(subs, connection) -> None:
    control = subs.add_parser("control")
    actions = control.add_subparsers(dest="control_command", required=True)
    for name in ("status", "disable", "zero", "estop"):
        item = actions.add_parser(name); connection(item)
    enable = actions.add_parser("enable"); connection(enable)
    enable.add_argument("--axis", choices=tuple(AXIS), required=True)
    axis = actions.add_parser("axis"); connection(axis)
    axis.add_argument("axis", choices=tuple(AXIS))
    direction = actions.add_parser("direction"); connection(direction)
    direction.add_argument("direction", choices=tuple(DIRECTION))
    deadband = actions.add_parser("deadband"); connection(deadband)
    deadband.add_argument("--degrees", type=float, required=True)
    pid = actions.add_parser("pid")
    pid_actions = pid.add_subparsers(dest="pid_command", required=True)
    pid_get = pid_actions.add_parser("get"); connection(pid_get)
    pid_set = pid_actions.add_parser("set"); connection(pid_set)
    pid_set.add_argument("--kp", type=float, required=True)
    pid_set.add_argument("--ki", type=float, required=True)
    pid_set.add_argument("--kd", type=float, required=True)
    pid_set.add_argument("--output-limit-us", type=int)
    pid_set.add_argument("--derivative-alpha", type=float)
    pid_set.add_argument("--integral-mode", choices=tuple(INTEGRAL))
    pid_set.add_argument("--integral-leak", type=float)
    for name in ("experiment", "characterize"):
        item = actions.add_parser(name); connection(item)
        item.add_argument("--duration", type=float, default=60.0)
        item.add_argument("--output", type=Path, required=True)


def _owner() -> bytes:
    return bytes((commands.ACTUATOR_OWNER_SERIAL,))


def _action(client, command: int, payload: bytes = b"") -> bytes:
    return client.request(command, payload, retry=False)


def run_control(args, client):
    action = args.control_command
    if action == "status":
        return stable_dict(decode_control_status(
            client.request(commands.CONTROL_GET_STATUS)))
    if action in ("experiment", "characterize"):
        from .control_experiment import run_control_capture
        return run_control_capture(client, args, interactive=action == "experiment")
    if action == "estop":
        _action(client, commands.ACTUATOR_ESTOP, _owner())
        return stable_dict(decode_control_status(
            client.request(commands.CONTROL_GET_STATUS)))
    if action == "disable":
        _action(client, commands.CONTROL_DISABLE, _owner())
    elif action == "zero":
        _action(client, commands.CONTROL_SET_ZERO, _owner())
    elif action == "enable":
        # ARM 与 PID 接管必须位于同一串口会话内；若拆成两个 CLI 进程，
        # Windows 进程启动时间可能超过执行器看门狗，导致 enable 前已自动卸载。
        _action(client, commands.ACTUATOR_ARM, _owner())
        _action(client, commands.CONTROL_ENABLE,
                bytes((commands.ACTUATOR_OWNER_SERIAL, AXIS[args.axis])))
    elif action == "axis":
        _action(client, commands.CONTROL_SET_AXIS,
                bytes((commands.ACTUATOR_OWNER_SERIAL, AXIS[args.axis])))
    elif action == "direction":
        _action(client, commands.CONTROL_SET_DIRECTION,
                bytes((commands.ACTUATOR_OWNER_SERIAL,
                       DIRECTION[args.direction])))
    elif action == "deadband":
        if not 0.25 <= args.degrees <= 5.0:
            raise ValueError("deadband must be within 0.25..5.0 degrees")
        _action(client, commands.CONTROL_SET_DEADBAND,
                struct.pack("<BH", commands.ACTUATOR_OWNER_SERIAL,
                            round(args.degrees * 100.0)))
    elif action == "pid":
        if args.pid_command == "get":
            return stable_dict(PidConfig.unpack(
                client.request(commands.CONTROL_GET_PID)))
        current = PidConfig.unpack(client.request(commands.CONTROL_GET_PID))
        config = dataclasses.replace(
            current,
            kp=args.kp,
            ki=args.ki,
            kd=args.kd,
            output_limit_us=(args.output_limit_us
                             if args.output_limit_us is not None
                             else current.output_limit_us),
            derivative_alpha=(args.derivative_alpha
                              if args.derivative_alpha is not None
                              else current.derivative_alpha),
            integral_mode=(INTEGRAL[args.integral_mode]
                           if args.integral_mode is not None
                           else current.integral_mode),
            integral_leak_factor=(args.integral_leak
                                  if args.integral_leak is not None
                                  else current.integral_leak_factor))
        _action(client, commands.CONTROL_SET_PID, _owner() + config.pack())
        return stable_dict(PidConfig.unpack(
            client.request(commands.CONTROL_GET_PID)))
    else:
        raise ValueError(f"unsupported control action: {action}")
    return stable_dict(decode_control_status(
        client.request(commands.CONTROL_GET_STATUS)))
