"""MotionEdge protocol v1 framing and recoverable stream parsing."""

from __future__ import annotations

from dataclasses import dataclass

SOF = b"\xA5\x5A"
VERSION = 1
MAX_PAYLOAD = 128
FIXED_SIZE = 11


def crc16_ccitt_false(data: bytes, initial: int = 0xFFFF) -> int:
    """Return CRC16-CCITT-FALSE (poly 0x1021, no reflection, xor-out zero)."""
    crc = initial
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class Frame:
    type: int
    sequence: int = 0
    payload: bytes = b""
    flags: int = 0
    version: int = VERSION


def encode_frame(frame: Frame) -> bytes:
    if frame.version != VERSION:
        raise ValueError("unsupported protocol version")
    if not 0 <= frame.type <= 0xFF or not 0 <= frame.flags <= 0xFF:
        raise ValueError("type and flags must fit in one byte")
    if not 0 <= frame.sequence <= 0xFFFF:
        raise ValueError("sequence must fit in 16 bits")
    if len(frame.payload) > MAX_PAYLOAD:
        raise ValueError(f"payload exceeds {MAX_PAYLOAD} bytes")
    body = bytes((frame.version, frame.type, frame.flags))
    body += frame.sequence.to_bytes(2, "little")
    body += len(frame.payload).to_bytes(2, "little")
    body += frame.payload
    return SOF + body + crc16_ccitt_false(body).to_bytes(2, "little")


def decode_frame(data: bytes) -> Frame:
    if len(data) < FIXED_SIZE or data[:2] != SOF:
        raise ValueError("invalid frame prefix or size")
    if data[2] != VERSION:
        raise ValueError("unsupported protocol version")
    length = int.from_bytes(data[7:9], "little")
    if length > MAX_PAYLOAD or len(data) != FIXED_SIZE + length:
        raise ValueError("invalid payload length")
    expected = int.from_bytes(data[-2:], "little")
    if crc16_ccitt_false(data[2:-2]) != expected:
        raise ValueError("CRC mismatch")
    return Frame(data[3], int.from_bytes(data[5:7], "little"), data[9:-2], data[4], data[2])


class FrameParser:
    """Incrementally parses noisy byte streams and recovers after bad frames."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.frames = 0
        self.crc_errors = 0
        self.length_errors = 0
        self.version_errors = 0
        self.discarded_bytes = 0

    def feed(self, data: bytes) -> list[Frame]:
        self.buffer.extend(data)
        output: list[Frame] = []
        while True:
            start = self.buffer.find(SOF)
            if start < 0:
                keep = 1 if self.buffer.endswith(SOF[:1]) else 0
                self.discarded_bytes += len(self.buffer) - keep
                if keep:
                    self.buffer[:] = self.buffer[-1:]
                else:
                    self.buffer.clear()
                break
            if start:
                self.discarded_bytes += start
                del self.buffer[:start]
            if len(self.buffer) < 9:
                break
            if self.buffer[2] != VERSION:
                self.version_errors += 1
                del self.buffer[0]
                continue
            length = int.from_bytes(self.buffer[7:9], "little")
            if length > MAX_PAYLOAD:
                self.length_errors += 1
                del self.buffer[0]
                continue
            frame_size = FIXED_SIZE + length
            if len(self.buffer) < frame_size:
                break
            candidate = bytes(self.buffer[:frame_size])
            try:
                output.append(decode_frame(candidate))
                self.frames += 1
                del self.buffer[:frame_size]
            except ValueError:
                self.crc_errors += 1
                del self.buffer[0]
        return output
