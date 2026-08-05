"""不理解业务命令的可靠字节 Transport。"""

from __future__ import annotations

from collections import deque
from typing import Protocol, runtime_checkable

from .errors import ConnectionError
from .models import PortInfo


@runtime_checkable
class Transport(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def read(self, size: int = 256) -> bytes: ...
    def write(self, data: bytes) -> int: ...
    @property
    def is_open(self) -> bool: ...
    def flush_input(self) -> None: ...
    def __enter__(self) -> "Transport": ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...


class SerialTransport:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.05,
                 write_timeout: float = 1.0, serial_factory=None,
                 auto_open: bool = True) -> None:
        if not port:
            raise ValueError("serial port must not be empty")
        if baud <= 0 or timeout < 0 or write_timeout <= 0:
            raise ValueError("invalid serial timing parameters")
        self.port, self.baud = port, baud
        self.timeout, self.write_timeout = timeout, write_timeout
        self._serial_factory = serial_factory
        self._serial = None
        if auto_open:
            self.open()

    def open(self) -> None:
        if self.is_open:
            return
        try:
            if self._serial_factory is None:
                import serial  # type: ignore
                factory = serial.Serial
            else:
                factory = self._serial_factory
            self._serial = factory(self.port, baudrate=self.baud,
                                   timeout=self.timeout,
                                   write_timeout=self.write_timeout,
                                   xonxoff=False, rtscts=False, dsrdtr=False)
        except (ImportError, OSError, Exception) as exc:
            # pyserial异常类型可能由测试工厂替换，统一映射为项目异常。
            self._serial = None
            raise ConnectionError(f"unable to open serial port {self.port}: {exc}") from exc

    @property
    def is_open(self) -> bool:
        return self._serial is not None and bool(getattr(self._serial, "is_open", True))

    def _require_open(self):
        if not self.is_open:
            raise ConnectionError(f"serial port {self.port} is closed")
        return self._serial

    def write(self, data: bytes) -> int:
        if data is None:
            raise ValueError("data must not be None")
        try:
            written = int(self._require_open().write(data))
        except Exception as exc:
            raise ConnectionError(f"serial write failed: {exc}") from exc
        if written != len(data):
            raise ConnectionError(f"short serial write: {written}/{len(data)} bytes")
        return written

    def read(self, size: int = 256) -> bytes:
        if size <= 0:
            raise ValueError("read size must be positive")
        try:
            return bytes(self._require_open().read(size))
        except Exception as exc:
            raise ConnectionError(f"serial read failed: {exc}") from exc

    def flush_input(self) -> None:
        try:
            self._require_open().reset_input_buffer()
        except Exception as exc:
            raise ConnectionError(f"serial input flush failed: {exc}") from exc

    def close(self) -> None:
        serial_object, self._serial = self._serial, None
        if serial_object is not None:
            try:
                serial_object.close()
            except Exception as exc:
                raise ConnectionError(f"serial close failed: {exc}") from exc

    def __enter__(self) -> "SerialTransport":
        self.open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class MemoryTransport:
    """容量有限、支持短读/短写/断线注入的测试 Transport。"""

    def __init__(self, responder=None, *, read_chunk: int = 256,
                 short_write: int | None = None, capacity: int = 65536) -> None:
        self.responder = responder
        self.read_chunk = read_chunk
        self.short_write = short_write
        self.capacity = capacity
        self.pending = bytearray()
        self.writes: deque[bytes] = deque(maxlen=1024)
        self._open = True

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def disconnect(self) -> None:
        self._open = False

    def write(self, data: bytes) -> int:
        if not self._open:
            raise ConnectionError("memory transport disconnected")
        count = min(len(data), self.short_write) if self.short_write is not None else len(data)
        written = bytes(data[:count])
        self.writes.append(written)
        if self.responder is not None and count == len(data):
            response = self.responder(written)
            if response:
                self.inject(response)
        return count

    def inject(self, data: bytes) -> None:
        if len(self.pending) + len(data) > self.capacity:
            raise ConnectionError("memory transport receive capacity exceeded")
        self.pending.extend(data)

    def read(self, size: int = 256) -> bytes:
        if not self._open:
            raise ConnectionError("memory transport disconnected")
        count = min(size, self.read_chunk, len(self.pending))
        result = bytes(self.pending[:count])
        del self.pending[:count]
        return result

    def flush_input(self) -> None:
        self.pending.clear()

    def __enter__(self) -> "MemoryTransport":
        self.open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def list_ports() -> list[PortInfo]:
    try:
        from serial.tools import list_ports as serial_list_ports  # type: ignore
    except ImportError as exc:
        raise ConnectionError("port discovery requires pyserial") from exc
    result = []
    for port in serial_list_ports.comports():
        description = port.description or None
        text = f"{description or ''} {port.manufacturer or ''}".lower()
        role = ("st-link-vcp" if "stlink" in text or "st-link" in text else
                "usb-ttl" if any(name in text for name in ("ch340", "cp210", "ftdi", "usb-serial"))
                else "unknown")
        result.append(PortInfo(port.device, description, port.vid, port.pid,
                               port.serial_number, role))
    return result
