"""Phase 7集成测试用10 Hz模拟串口；报告必须明确标记SIMULATED。"""

from __future__ import annotations

import struct
import time

from . import commands
from .protocol import Frame, encode_frame
from .simulator import SimulatedDevice


class StreamingSimulatedDevice(SimulatedDevice):
    def __init__(self) -> None:
        super().__init__(); self._next_motion = time.monotonic(); self._motion_count = 0

    def _health_payload(self) -> bytes:
        return struct.pack("<IBB6I", int(time.monotonic() * 1000) & 0xFFFFFFFF,
                           2, 2, self.motion_sequence, 0, 0,
                           self.request_count, 0, 0)

    def read(self, size: int = 256) -> bytes:
        now = time.monotonic()
        if self.config.telemetry_enabled and now >= self._next_motion:
            self._next_motion += 0.1; self._motion_count += 1
            self.pending.extend(encode_frame(Frame(commands.MOTION_TELEMETRY,
                                                   self._motion_count, self.motion_payload())))
            if self._motion_count % 10 == 0:
                self.pending.extend(encode_frame(Frame(commands.HEALTH_TELEMETRY,
                                                       self._motion_count, self._health_payload())))
        return super().read(size)
