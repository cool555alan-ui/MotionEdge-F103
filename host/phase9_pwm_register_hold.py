"""Hold a diagnostic PWM command briefly so ST-LINK can inspect registers."""

from __future__ import annotations

import argparse
import struct
import time

from motionctl import commands
from motionctl.device import DeviceClient
from motionctl.transport import SerialTransport


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--pulse-us", type=int, default=1450)
    parser.add_argument("--duration", type=float, default=10.0)
    args = parser.parse_args()
    client = DeviceClient(SerialTransport(args.port, 115200), timeout=1.0)
    owner = bytes((commands.ACTUATOR_OWNER_SERIAL,))
    try:
        client.request(commands.ACTUATOR_ARM, owner, retry=False)
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            client.request(commands.ACTUATOR_SET_RAW_PULSE,
                           struct.pack("<BH", commands.ACTUATOR_OWNER_SERIAL,
                                       args.pulse_us), retry=False)
            time.sleep(0.2)
    finally:
        try: client.request(commands.ACTUATOR_ESTOP, owner, retry=False)
        finally: client.close()
    return 0


if __name__ == "__main__": raise SystemExit(main())
