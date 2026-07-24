"""Command-line interface for MotionEdge protocol v1."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time

from . import commands
from .commands import RuntimeConfig
from .device import DeviceClient, SimulatedDevice
from .protocol import FrameParser
from .transport import SerialTransport, list_ports


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands_parser = parser.add_subparsers(dest="command", required=True)
    commands_parser.add_parser("ports")
    commands_parser.add_parser("simulate-device")
    commands_parser.add_parser("self-test")
    for name in ("ping", "info", "status", "config-get", "calibrate", "monitor"):
        item = commands_parser.add_parser(name)
        item.add_argument("--port", required=True)
    config = commands_parser.add_parser("config-set")
    config.add_argument("--port", required=True)
    config.add_argument("--sensor-ms", type=int)
    config.add_argument("--telemetry-ms", type=int)
    config.add_argument("--alpha-milli", type=int)
    config.add_argument("--gyro-weight-milli", type=int)
    config.add_argument("--log-level", type=int)
    stream = commands_parser.add_parser("stream")
    stream.add_argument("--port", required=True)
    state = stream.add_mutually_exclusive_group(required=True)
    state.add_argument("--enable", action="store_true")
    state.add_argument("--disable", action="store_true")
    return parser


def _client(port: str) -> DeviceClient:
    return DeviceClient(SerialTransport(port))


def _print_config(config: RuntimeConfig) -> None:
    print(json.dumps(dataclasses.asdict(config), ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "ports":
            ports = list_ports()
            print("\n".join(ports) if ports else "No serial ports found.")
            return 0
        if args.command in ("simulate-device", "self-test"):
            client = DeviceClient(SimulatedDevice(), timeout=0.1)
            client.request(commands.PING)
            info = client.request(commands.GET_DEVICE_INFO)
            config = RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
            print(f"SIMULATOR ONLY: protocol={info[3]} firmware={info[0]}.{info[1]}.{info[2]}")
            _print_config(config)
            print("SELF-TEST PASS" if args.command == "self-test" else "Simulator command exchange complete.")
            return 0
        client = _client(args.port)
        if args.command == "ping":
            client.request(commands.PING)
            print("PONG")
        elif args.command == "info":
            data = client.request(commands.GET_DEVICE_INFO)
            print(f"firmware={data[0]}.{data[1]}.{data[2]} protocol={data[3]}")
        elif args.command == "status":
            data = client.request(commands.GET_STATUS)
            print(f"app_state={data[0]} motion_state={data[1]}")
        elif args.command == "config-get":
            _print_config(RuntimeConfig.unpack(client.request(commands.GET_CONFIG)))
        elif args.command == "config-set":
            current = RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
            changes = {
                name: getattr(args, name)
                for name in ("sensor_ms", "telemetry_ms", "alpha_milli", "gyro_weight_milli", "log_level")
                if getattr(args, name) is not None
            }
            client.request(commands.SET_CONFIG, dataclasses.replace(current, **changes).pack())
            print("Configuration updated in RAM.")
        elif args.command == "calibrate":
            client.request(commands.START_CALIBRATION)
            print("Calibration started.")
        elif args.command == "stream":
            client.request(commands.SET_STREAM_STATE, bytes((int(args.enable),)))
            print("Binary stream enabled." if args.enable else "Binary stream disabled.")
        elif args.command == "monitor":
            parser = FrameParser()
            client.request(commands.SET_STREAM_STATE, b"\1")
            print("Monitoring binary telemetry; press Ctrl+C to stop.")
            while True:
                for frame in parser.feed(client.transport.read()):
                    print(f"type=0x{frame.type:02X} sequence={frame.sequence} payload={frame.payload.hex()}")
                time.sleep(0.005)
        client.transport.close()
        return 0
    except (IndexError, OSError, RuntimeError, ValueError, KeyboardInterrupt) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
