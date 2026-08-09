"""稳定、带单位且允许缺失字段的数据模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def stable_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: stable_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): stable_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [stable_dict(item) for item in value]
    return value


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str | None = None
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    likely_role: str = "unknown"


@dataclass(frozen=True)
class DeviceInfo:
    firmware_version: str
    protocol_version: int
    device_name: str | None = None
    mcu_model: str | None = None
    imu_model: str | None = None
    who_am_i: int | None = None
    capabilities: int | None = None
    build_type: str | None = None
    available_commands: tuple[int, ...] | None = None


@dataclass(frozen=True)
class DeviceStatus:
    app_state_raw: int
    sensor_state_raw: int
    app_state: str
    sensor_state: str
    calibrated: bool | None = None
    stream_enabled: bool | None = None
    uptime_ms: int | None = None
    task_frequency_hz: dict[str, float] | None = None
    deadline_miss: dict[str, int] | None = None
    queue: dict[str, int] | None = None
    mutex_timeouts: dict[str, int] | None = None
    heap_bytes: dict[str, int] | None = None
    stack_remaining_bytes: dict[str, int] | None = None
    protocol_errors: dict[str, int] | None = None
    uart_errors: int | None = None


@dataclass(frozen=True)
class MotionSample:
    device_timestamp_ms: int
    sample_sequence: int
    status_flags: int
    calibrated: bool
    ax_mg: int
    ay_mg: int
    az_mg: int
    gx_mdps: int
    gy_mdps: int
    gz_mdps: int
    roll_deg: float
    pitch_deg: float
    roll_cdeg_raw: int
    pitch_cdeg_raw: int
    host_monotonic_ns: int | None = None


@dataclass(frozen=True)
class HealthSample:
    uptime_ms: int
    app_state_raw: int
    sensor_state_raw: int
    loop_count: int
    i2c_errors: int
    invalid_samples: int
    protocol_rx_frames: int
    protocol_crc_errors: int
    uart_rx_overflows: int
    sensor_deadline_miss: int
    communication_deadline_miss: int
    telemetry_deadline_miss: int
    health_deadline_miss: int
    host_monotonic_ns: int | None = None


@dataclass(frozen=True)
class ActuatorStatus:
    mode_raw: int
    state_raw: int
    armed: bool
    owner_raw: int
    mode: str
    state: str
    owner: str
    target_angle_cdeg: int
    current_angle_cdeg: int
    target_angle_deg: float
    current_angle_deg: float
    target_pulse_us: int
    current_pulse_us: int
    safe_min_us: int
    safe_max_us: int
    command_age_ms: int
    timeout_count: int
    limit_count: int
    fault_count: int
    estop_count: int


@dataclass(frozen=True)
class ControlStatus:
    mode_raw: int
    axis_raw: int
    direction_raw: int
    integral_mode_raw: int
    enabled: bool
    active: bool
    saturated: bool
    in_deadband: bool
    last_fault_raw: int
    mode: str
    axis: str
    direction: str
    integral_mode: str
    last_fault: str
    zero_angle_cdeg: int
    measured_angle_cdeg: int
    relative_angle_cdeg: int
    effective_error_cdeg: int
    deadband_cdeg: int
    kp: float
    ki: float
    kd: float
    p_term_us: float
    i_term_us: float
    d_term_us: float
    output_us: int
    requested_pulse_us: int
    actual_pulse_us: int
    motion_age_ms: int
    update_count: int
    invalid_dt_count: int
    nonfinite_input_count: int
    stale_motion_count: int
    integrator_saturation_count: int
    target_limit_count: int
    fault_count: int
    deadband_entry_count: int
    deadband_exit_count: int


@dataclass(frozen=True)
class CommandResult:
    command: str
    success: bool
    rtt_ms: float
    sequence: int
    error: str | None = None


@dataclass(frozen=True)
class CaptureMetadata:
    tool_version: str
    started_at: str
    requested_duration_s: float
    port: str
    baud: int
    git_commit: str | None
    device_info: DeviceInfo | None
    initial_config: dict[str, Any] | None
    simulated: bool = False
    ping_ok: bool | None = None
    command_success_rate: float | None = None
    command_metrics: dict[str, Any] | None = None
    fault_seen: bool | None = None
    degraded_persistent: bool | None = None


@dataclass(frozen=True)
class ValidationItem:
    name: str
    status: str
    actual: Any
    threshold: str
    reason: str


@dataclass(frozen=True)
class ValidationResult:
    conclusion: str
    items: tuple[ValidationItem, ...]


@dataclass(frozen=True)
class ReportSummary:
    metrics: dict[str, Any]
    validation: ValidationResult
    charts: tuple[str, ...] = field(default_factory=tuple)
