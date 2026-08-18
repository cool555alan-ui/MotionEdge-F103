"""Protocol message IDs and stable little-endian payload codecs."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .models import (ActuatorStatus, ControlStatus, DeviceInfo, DeviceStatus,
                     HealthSample, MotionSample)

PING = 0x01
GET_DEVICE_INFO = 0x02
GET_STATUS = 0x03
GET_CONFIG = 0x04
SET_CONFIG = 0x05
START_CALIBRATION = 0x06
SET_STREAM_STATE = 0x07
GET_LATEST_MOTION = 0x08
ACTUATOR_GET_STATUS = 0x09
ACTUATOR_ARM = 0x0A
ACTUATOR_DISARM = 0x0B
ACTUATOR_SET_TARGET = 0x0C
ACTUATOR_CENTER = 0x0D
ACTUATOR_ESTOP = 0x0E
ACTUATOR_SET_RAW_PULSE = 0x0F
CONTROL_GET_STATUS = 0x10
CONTROL_ENABLE = 0x11
CONTROL_DISABLE = 0x12
CONTROL_SET_ZERO = 0x13
CONTROL_SET_AXIS = 0x14
CONTROL_SET_DIRECTION = 0x15
CONTROL_GET_PID = 0x16
CONTROL_SET_PID = 0x17
CONTROL_SET_DEADBAND = 0x18
CONFIG_PERSIST_STATUS = 0x19
CONFIG_PERSIST_SAVE = 0x1A
CONFIG_PERSIST_LOAD = 0x1B
CONFIG_FACTORY_RESET = 0x1C
MOTION_TELEMETRY = 0x20
HEALTH_TELEMETRY = 0x21
ACTUATOR_TELEMETRY = 0x23
CONTROL_TELEMETRY = 0x24
COMMAND_RESPONSE = 0x80

ACTUATOR_OWNER_SERIAL = 2
ACTUATOR_OWNER_MQTT = 3

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


def decode_persistence_status(payload: bytes) -> dict[str, object]:
    if len(payload) != 37:
        raise ValueError("persistence status payload must be 37 bytes")
    source, schema, valid_slots, dirty = struct.unpack_from("<BBBB", payload)
    generation = struct.unpack_from("<I", payload, 4)[0]
    last_save = payload[8]
    counters = struct.unpack_from("<7I", payload, 9)
    return {"source": {0: "DEFAULTS", 1: "SLOT_A", 2: "SLOT_B"}.get(source, f"UNKNOWN({source})"),
            "schema": schema, "valid_slot_count": valid_slots,
            "dirty": bool(dirty), "generation": generation,
            "last_save_result": last_save, "save_count": counters[0],
            "factory_reset_count": counters[1], "crc_error_count": counters[2],
            "invalid_record_count": counters[3], "unsupported_schema_count": counters[4],
            "save_rate_limited_count": counters[5], "last_save_duration_ms": counters[6]}


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
    if len(payload) != 46:
        raise ValueError("health payload must be 46 bytes")
    uptime = struct.unpack_from("<I", payload, 0)[0]
    app, sensor = payload[4], payload[5]
    values = struct.unpack_from("<10I", payload, 6)
    return HealthSample(uptime, app, sensor, *values, host_monotonic_ns)


ACTUATOR_MODE_NAMES = {0: "DISABLED", 1: "MANUAL", 2: "ATTITUDE_HOLD"}
ACTUATOR_STATE_NAMES = {0: "DISABLED", 1: "ARMING", 2: "READY",
                        3: "MOVING", 4: "HOLDING", 5: "FAULT"}
ACTUATOR_OWNER_NAMES = {0: "NONE", 1: "LOCAL", 2: "SERIAL",
                        3: "MQTT", 4: "CONTROL_LOOP"}


def decode_actuator_status(payload: bytes) -> ActuatorStatus:
    if len(payload) != 36:
        raise ValueError("actuator status payload must be 36 bytes")
    mode, state, armed, owner, target_angle, current_angle, target_pulse, current_pulse, safe_min, safe_max, age, timeout, limit, fault, estop = struct.unpack(
        "<BBBBhhHHHHIIIII", payload)
    return ActuatorStatus(
        mode, state, bool(armed), owner,
        ACTUATOR_MODE_NAMES.get(mode, f"UNKNOWN({mode})"),
        ACTUATOR_STATE_NAMES.get(state, f"UNKNOWN({state})"),
        ACTUATOR_OWNER_NAMES.get(owner, f"UNKNOWN({owner})"),
        target_angle, current_angle,
        target_angle / 100.0, current_angle / 100.0,
        target_pulse, current_pulse, safe_min, safe_max,
        age, timeout, limit, fault, estop)


CONTROL_MODE_NAMES = {0: "DISABLED", 1: "PID_ATTITUDE"}
CONTROL_AXIS_NAMES = {0: "ROLL", 1: "PITCH"}
CONTROL_DIRECTION_NAMES = {0: "NORMAL", 1: "REVERSE"}
CONTROL_INTEGRAL_NAMES = {0: "DISABLED", 1: "BOUNDED", 2: "LEAKY"}
CONTROL_FAULT_NAMES = {0: "NONE", 1: "STALE_MOTION", 2: "SENSOR_OFFLINE",
                       3: "NOT_CALIBRATED", 4: "APP_FAULT", 5: "ACTUATOR",
                       6: "NONFINITE", 7: "INVALID_DT"}


@dataclass(frozen=True)
class PidConfig:
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.05
    output_limit_us: int = 10
    derivative_alpha: float = 0.2
    integral_mode: int = 0
    integral_leak_factor: float = 0.99

    def validate(self) -> bool:
        values = (self.kp, self.ki, self.kd, self.derivative_alpha,
                  self.integral_leak_factor)
        return (all(isinstance(value, (int, float)) and not isinstance(value, bool)
                    and float("-inf") < value < float("inf") for value in values)
                and 0.0 <= self.kp <= 50.0
                and 0.0 <= self.ki <= 20.0
                and 0.0 <= self.kd <= 20.0
                and 1 <= self.output_limit_us <= 50
                and 0.0 <= self.derivative_alpha <= 1.0
                and self.integral_mode in (0, 1, 2)
                and 0.0 <= self.integral_leak_factor <= 1.0)

    def pack(self) -> bytes:
        if not self.validate():
            raise ValueError("invalid PID configuration")
        return struct.pack("<iiiHHBH", round(self.kp * 1000),
                           round(self.ki * 1000), round(self.kd * 1000),
                           self.output_limit_us,
                           round(self.derivative_alpha * 1000),
                           self.integral_mode,
                           round(self.integral_leak_factor * 1000))

    @classmethod
    def unpack(cls, payload: bytes) -> "PidConfig":
        if len(payload) != 19:
            raise ValueError("PID configuration payload must be 19 bytes")
        kp, ki, kd, limit, alpha, mode, leak = struct.unpack("<iiiHHBH", payload)
        result = cls(kp / 1000.0, ki / 1000.0, kd / 1000.0,
                     limit, alpha / 1000.0, mode, leak / 1000.0)
        if not result.validate():
            raise ValueError("device returned invalid PID configuration")
        return result


def decode_control_status(payload: bytes) -> ControlStatus:
    if len(payload) != 94:
        raise ValueError("control status payload must be 94 bytes")
    values = struct.unpack("<BBBBBB4iH6ihHH10I", payload)
    mode, axis, direction, integral, flags, fault = values[:6]
    zero, measured, relative, effective = values[6:10]
    deadband = values[10]
    kp, ki, kd, p_term, i_term, d_term = values[11:17]
    output, requested, actual = values[17:20]
    counters = values[20:]
    return ControlStatus(
        mode, axis, direction, integral,
        bool(flags & 1), bool(flags & 2), bool(flags & 4), bool(flags & 8),
        fault,
        CONTROL_MODE_NAMES.get(mode, f"UNKNOWN({mode})"),
        CONTROL_AXIS_NAMES.get(axis, f"UNKNOWN({axis})"),
        CONTROL_DIRECTION_NAMES.get(direction, f"UNKNOWN({direction})"),
        CONTROL_INTEGRAL_NAMES.get(integral, f"UNKNOWN({integral})"),
        CONTROL_FAULT_NAMES.get(fault, f"UNKNOWN({fault})"),
        zero, measured, relative, effective, deadband,
        kp / 1000.0, ki / 1000.0, kd / 1000.0,
        p_term / 1000.0, i_term / 1000.0, d_term / 1000.0,
        output, requested, actual, *counters)
