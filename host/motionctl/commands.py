"""Protocol message IDs and stable little-endian payload codecs."""

from __future__ import annotations

import struct
from dataclasses import dataclass

PING = 0x01
GET_DEVICE_INFO = 0x02
GET_STATUS = 0x03
GET_CONFIG = 0x04
SET_CONFIG = 0x05
START_CALIBRATION = 0x06
SET_STREAM_STATE = 0x07
GET_LATEST_MOTION = 0x08
MOTION_TELEMETRY = 0x20
HEALTH_TELEMETRY = 0x21
COMMAND_RESPONSE = 0x80

STATUS_NAMES = {
    0: "OK",
    1: "INVALID_COMMAND",
    2: "INVALID_LENGTH",
    3: "INVALID_VALUE",
    4: "NOT_READY",
    5: "BUSY",
    6: "UNSUPPORTED",
    7: "INTERNAL_ERROR",
}


@dataclass(frozen=True)
class RuntimeConfig:
    sensor_ms: int = 10
    telemetry_ms: int = 100
    alpha_milli: int = 200
    gyro_weight_milli: int = 980
    log_level: int = 2
    telemetry_enabled: bool = False

    def pack(self) -> bytes:
        return struct.pack(
            "<HHHHBB",
            self.sensor_ms,
            self.telemetry_ms,
            self.alpha_milli,
            self.gyro_weight_milli,
            self.log_level,
            int(self.telemetry_enabled),
        )

    @classmethod
    def unpack(cls, payload: bytes) -> "RuntimeConfig":
        if len(payload) != 10:
            raise ValueError("configuration payload must be 10 bytes")
        values = struct.unpack("<HHHHBB", payload)
        return cls(*values[:5], bool(values[5]))


def unpack_response(payload: bytes) -> tuple[int, int, int, bytes]:
    if len(payload) < 6:
        raise ValueError("command response is shorter than 6 bytes")
    request_type, status, detail, data_length = struct.unpack("<BBHH", payload[:6])
    data = payload[6:]
    if len(data) != data_length:
        raise ValueError("command response data length mismatch")
    return request_type, status, detail, data
