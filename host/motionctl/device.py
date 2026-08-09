"""sequence匹配、异步遥测分流和有限安全重试。"""

from __future__ import annotations

import time
from collections import deque

from . import commands
from .errors import CommandError, ConnectionError, ProtocolError, RequestTimeout
from .models import CommandResult
from .protocol import Frame, FrameParser, encode_frame

SAFE_RETRY_COMMANDS = frozenset((commands.PING, commands.GET_DEVICE_INFO,
                                 commands.GET_STATUS, commands.GET_CONFIG,
                                 commands.GET_LATEST_MOTION,
                                 commands.ACTUATOR_GET_STATUS,
                                 commands.CONTROL_GET_STATUS,
                                 commands.CONTROL_GET_PID))


class DeviceClient:
    def __init__(self, transport, timeout: float = 1.0, retries: int = 3,
                 telemetry_capacity: int = 256) -> None:
        if timeout <= 0 or retries < 0 or telemetry_capacity <= 0:
            raise ValueError("invalid DeviceClient limits")
        self.transport = transport
        self.timeout, self.retries = timeout, retries
        self.parser = FrameParser()
        self.sequence = 0
        self.telemetry = deque(maxlen=telemetry_capacity)
        self.command_results = deque(maxlen=4096)
        self.attempt_results = deque(maxlen=8192)
        self.retry_count = 0

    def __enter__(self) -> "DeviceClient":
        if hasattr(self.transport, "open"):
            self.transport.open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        self.transport.close()

    def flush_input(self) -> None:
        """丢弃会话前积压字节，并重置流式解析状态和异步遥测缓存。"""
        self.transport.flush_input()
        self.parser = FrameParser()
        self.telemetry.clear()

    def poll(self) -> list[Frame]:
        frames = self.parser.feed(self.transport.read())
        for frame in frames:
            if frame.type in (commands.MOTION_TELEMETRY, commands.HEALTH_TELEMETRY,
                              commands.ACTUATOR_TELEMETRY,
                              commands.CONTROL_TELEMETRY):
                self.telemetry.append((time.monotonic_ns(), frame))
        return frames

    def request(self, message_type: int, payload: bytes = b"", *,
                retry: bool | None = None) -> bytes:
        allow_retry = message_type in SAFE_RETRY_COMMANDS if retry is None else retry
        attempts = self.retries + 1 if allow_retry else 1
        last_error: Exception | None = None
        logical_start_ns = time.monotonic_ns()
        for attempt in range(attempts):
            self.sequence = (self.sequence + 1) & 0xFFFF
            sequence = self.sequence
            start_ns = time.monotonic_ns()
            try:
                raw = encode_frame(Frame(message_type, sequence, payload))
                written = self.transport.write(raw)
                if written is not None and written != len(raw):
                    raise ConnectionError(f"short write: {written}/{len(raw)} bytes")
                deadline = time.monotonic() + self.timeout
                while time.monotonic() < deadline:
                    for frame in self.poll():
                        if frame.type != commands.COMMAND_RESPONSE or frame.sequence != sequence:
                            continue
                        request_type, status, detail, data = commands.unpack_response(frame.payload)
                        if request_type != message_type:
                            continue
                        rtt = (time.monotonic_ns() - start_ns) / 1_000_000.0
                        if status:
                            name = commands.STATUS_NAMES.get(status, f"STATUS_{status}")
                            error = CommandError(f"device returned {name} (detail={detail})",
                                                 status=status, detail=detail)
                            result = CommandResult(hex(message_type), False, rtt,
                                                   sequence, str(error))
                            self.attempt_results.append(result)
                            self.command_results.append(CommandResult(
                                hex(message_type), False,
                                (time.monotonic_ns() - logical_start_ns) / 1_000_000.0,
                                sequence, str(error)))
                            raise error
                        self.attempt_results.append(
                            CommandResult(hex(message_type), True, rtt, sequence))
                        self.command_results.append(CommandResult(
                            hex(message_type), True,
                            (time.monotonic_ns() - logical_start_ns) / 1_000_000.0,
                            sequence))
                        return data
                raise RequestTimeout(f"response timeout for sequence {sequence}")
            except (ConnectionError, RequestTimeout) as exc:
                last_error = exc
                rtt = (time.monotonic_ns() - start_ns) / 1_000_000.0
                self.attempt_results.append(CommandResult(hex(message_type), False, rtt,
                                                          sequence, str(exc)))
                if attempt + 1 >= attempts:
                    self.command_results.append(CommandResult(
                        hex(message_type), False,
                        (time.monotonic_ns() - logical_start_ns) / 1_000_000.0,
                        sequence, str(exc)))
                    raise
                self.retry_count += 1
            except ValueError as exc:
                raise ProtocolError(str(exc)) from exc
        assert last_error is not None
        raise last_error


# 向后兼容旧测试导入名称。
TimeoutError = RequestTimeout


from .simulator import SimulatedDevice  # noqa: E402  避免循环导入
