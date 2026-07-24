"""Serial and in-memory byte transports."""

from __future__ import annotations

from typing import Protocol


class Transport(Protocol):
    def write(self, data: bytes) -> None: ...
    def read(self, size: int = 256) -> bytes: ...
    def close(self) -> None: ...


class SerialTransport:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.05) -> None:
        try:
            import serial  # type: ignore
        except ImportError as exc:
            raise RuntimeError("serial commands require pyserial; install host/requirements.txt") from exc
        try:
            self._serial = serial.Serial(port, baudrate=baud, timeout=timeout)
        except serial.SerialException as exc:
            raise RuntimeError(f"unable to open serial port {port}: {exc}") from exc

    def write(self, data: bytes) -> None:
        self._serial.write(data)

    def read(self, size: int = 256) -> bytes:
        return self._serial.read(size)

    def close(self) -> None:
        self._serial.close()


def list_ports() -> list[str]:
    try:
        from serial.tools import list_ports as serial_list_ports  # type: ignore
    except ImportError as exc:
        raise RuntimeError("port discovery requires pyserial; install host/requirements.txt") from exc
    return [port.device for port in serial_list_ports.comports()]
