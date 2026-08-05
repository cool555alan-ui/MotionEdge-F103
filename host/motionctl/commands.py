"""Protocol message IDs and stable little-endian payload codecs."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .models import DeviceInfo, DeviceStatus, HealthSample, MotionSample

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

    def validate(self) -> bool:
        return (5 <= self.sensor_ms <= 100 and
                20 <= self.telemetry_ms <= 5000 and
                1 <= self.alpha_milli <= 1000 and
                500 <= self.gyro_weight_milli <= 999 and
                0 <= self.log_level <= 4)

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


APP_STATE_NAMES = {0: "BOOT", 1: "INITIALIZING", 2: "RUNNING", 3: "DEGRADED", 4: "FAULT"}
MOTION_STATE_NAMES = {0: "IDLE", 1: "CALIBRATING", 2: "RUNNING", 3: "DEGRADED"}


def decode_device_info(payload: bytes) -> DeviceInfo:
    if len(payload) < 4:
        raise ValueError("device information payload must contain at least 4 bytes")
    return DeviceInfo(
        firmware_version=f"{payload[0]}.{payload[1]}.{payload[2]}",
        protocol_version=payload[3],
    )


def decode_status(payload: bytes, *, stream_enabled: bool | None = None) -> DeviceStatus:
    if len(payload) != 2:
        raise ValueError("status payload must be 2 bytes")
    app, sensor = payload
    return DeviceStatus(app, sensor, APP_STATE_NAMES.get(app, f"UNKNOWN({app})"),
                        MOTION_STATE_NAMES.get(sensor, f"UNKNOWN({sensor})"),
                        stream_enabled=stream_enabled)


def decode_motion(payload: bytes, host_monotonic_ns: int | None = None) -> MotionSample:
    if len(payload) != 45:
        raise ValueError("motion payload must be 45 bytes")
    timestamp, sequence, flags = struct.unpack_from("<III", payload, 0)
    calibrated = bool(payload[12])
    values = struct.unpack_from("<8i", payload, 13)
    return MotionSample(timestamp, sequence, flags, calibrated, *values[:6],
                        values[6] / 100.0, values[7] / 100.0,
                        values[6], values[7], host_monotonic_ns)


def decode_health(payload: bytes, host_monotonic_ns: int | None = None) -> HealthSample:
    if len(payload) != 30:
        raise ValueError("health payload must be 30 bytes")
    uptime = struct.unpack_from("<I", payload, 0)[0]
    app, sensor = payload[4], payload[5]
    values = struct.unpack_from("<6I", payload, 6)
    return HealthSample(uptime, app, sensor, *values, host_monotonic_ns)
