"""Sequence-matched device client and deterministic no-hardware simulator."""

from __future__ import annotations

import time

from . import commands
from .commands import RuntimeConfig
from .protocol import Frame, FrameParser, encode_frame


class TimeoutError(RuntimeError):
    pass


class DeviceClient:
    def __init__(self, transport, timeout: float = 1.0) -> None:
        self.transport = transport
        self.timeout = timeout
        self.parser = FrameParser()
        self.sequence = 0

    def request(self, message_type: int, payload: bytes = b"") -> bytes:
        self.sequence = (self.sequence + 1) & 0xFFFF
        sequence = self.sequence
        self.transport.write(encode_frame(Frame(message_type, sequence, payload)))
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            for frame in self.parser.feed(self.transport.read()):
                if frame.type != commands.COMMAND_RESPONSE or frame.sequence != sequence:
                    continue
                request_type, status, detail, data = commands.unpack_response(frame.payload)
                if request_type != message_type:
                    continue
                if status:
                    name = commands.STATUS_NAMES.get(status, f"STATUS_{status}")
                    raise RuntimeError(f"device returned {name} (detail={detail})")
                return data
        raise TimeoutError(f"response timeout for sequence {sequence}")


class SimulatedDevice:
    """In-memory simulator; its responses are not real hardware measurements."""

    def __init__(self) -> None:
        self.parser = FrameParser()
        self.pending = bytearray()
        self.config = RuntimeConfig()

    def write(self, data: bytes) -> None:
        for request in self.parser.feed(data):
            status = 0
            response_data = b""
            if request.type == commands.PING and not request.payload:
                pass
            elif request.type == commands.GET_DEVICE_INFO and not request.payload:
                response_data = bytes((0, 4, 0, 1))
            elif request.type == commands.GET_STATUS and not request.payload:
                response_data = bytes((2, 1))
            elif request.type == commands.GET_CONFIG and not request.payload:
                response_data = self.config.pack()
            elif request.type == commands.SET_CONFIG and len(request.payload) == 10:
                candidate = RuntimeConfig.unpack(request.payload)
                if (
                    5 <= candidate.sensor_ms <= 100
                    and 20 <= candidate.telemetry_ms <= 5000
                    and 1 <= candidate.alpha_milli <= 1000
                    and 500 <= candidate.gyro_weight_milli <= 999
                    and 0 <= candidate.log_level <= 4
                ):
                    self.config = candidate
                else:
                    status = 3
            elif request.type == commands.START_CALIBRATION and not request.payload:
                pass
            elif request.type == commands.SET_STREAM_STATE and request.payload in (b"\0", b"\1"):
                self.config = RuntimeConfig(
                    self.config.sensor_ms,
                    self.config.telemetry_ms,
                    self.config.alpha_milli,
                    self.config.gyro_weight_milli,
                    self.config.log_level,
                    request.payload == b"\1",
                )
            elif request.type == commands.GET_LATEST_MOTION and not request.payload:
                status = 4
            elif request.type not in range(1, 9):
                status = 1
            else:
                status = 2
            payload = bytes((request.type, status, 0, 0)) + len(response_data).to_bytes(2, "little") + response_data
            self.pending.extend(encode_frame(Frame(commands.COMMAND_RESPONSE, request.sequence, payload)))

    def read(self, size: int = 256) -> bytes:
        result = bytes(self.pending[:size])
        del self.pending[:size]
        return result

    def close(self) -> None:
        self.pending.clear()
