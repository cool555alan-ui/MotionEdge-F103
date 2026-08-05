"""确定性的无硬件协议设备与异常注入。"""

from __future__ import annotations

import struct
from dataclasses import replace

from . import commands
from .commands import RuntimeConfig
from .errors import ConnectionError
from .protocol import Frame, FrameParser, encode_frame


class SimulatedDevice:
    def __init__(self, *, noise: bytes = b"", corrupt_crc: bool = False,
                 timeout_commands: set[int] | None = None, disconnect_after: int | None = None,
                 read_chunk: int = 256) -> None:
        self.parser = FrameParser()
        self.pending = bytearray()
        self.config = RuntimeConfig(log_level=1)
        self.noise, self.corrupt_crc = noise, corrupt_crc
        self.timeout_commands = timeout_commands or set()
        self.disconnect_after, self.read_chunk = disconnect_after, read_chunk
        self.request_count = 0
        self._open = True
        self.motion_sequence = 0

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def flush_input(self) -> None:
        self.pending.clear()

    def __enter__(self) -> "SimulatedDevice":
        self.open(); return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _response(self, request: Frame, status: int, data: bytes = b"") -> bytes:
        payload = struct.pack("<BBHH", request.type, status, 0, len(data)) + data
        raw = encode_frame(Frame(commands.COMMAND_RESPONSE, request.sequence, payload))
        if self.corrupt_crc:
            raw = raw[:-1] + bytes((raw[-1] ^ 0xFF,))
        return self.noise + raw

    def write(self, data: bytes) -> int:
        if not self._open:
            raise ConnectionError("simulated device disconnected")
        for request in self.parser.feed(data):
            self.request_count += 1
            if self.disconnect_after is not None and self.request_count > self.disconnect_after:
                self._open = False
                raise ConnectionError("simulated device disconnected")
            if request.type in self.timeout_commands:
                continue
            status, response = 0, b""
            if request.type == commands.PING and not request.payload:
                pass
            elif request.type == commands.GET_DEVICE_INFO and not request.payload:
                response = bytes((0, 6, 0, 1))
            elif request.type == commands.GET_STATUS and not request.payload:
                response = bytes((2, 2))
            elif request.type == commands.GET_CONFIG and not request.payload:
                response = self.config.pack()
            elif request.type == commands.SET_CONFIG and len(request.payload) == 10:
                candidate = RuntimeConfig.unpack(request.payload)
                if candidate.validate(): self.config = candidate
                else: status = 3
            elif request.type == commands.START_CALIBRATION and not request.payload:
                pass
            elif request.type == commands.SET_STREAM_STATE and request.payload in (b"\0", b"\1"):
                self.config = replace(self.config, telemetry_enabled=request.payload == b"\1")
            elif request.type == commands.GET_LATEST_MOTION and not request.payload:
                response = self.motion_payload()
            else:
                status = 1 if request.type not in range(1, 9) else 2
            self.pending.extend(self._response(request, status, response))
        return len(data)

    def motion_payload(self) -> bytes:
        self.motion_sequence += 10
        timestamp = self.motion_sequence * 10
        return struct.pack("<IIIB8i", timestamp, self.motion_sequence, 0, 1,
                           0, 0, 1000, 0, 0, 0, 0, 0)

    def inject_motion(self, frame_sequence: int = 1) -> None:
        self.pending.extend(encode_frame(Frame(commands.MOTION_TELEMETRY,
                                              frame_sequence, self.motion_payload())))

    def read(self, size: int = 256) -> bytes:
        if not self._open:
            raise ConnectionError("simulated device disconnected")
        count = min(size, self.read_chunk, len(self.pending))
        result = bytes(self.pending[:count]); del self.pending[:count]
        return result
