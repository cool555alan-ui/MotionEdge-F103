"""统一 PASS/WARN/FAIL/NOT_TESTED 验收规则。"""

from __future__ import annotations

import math

from .models import ValidationItem, ValidationResult
from .validation_profile import *  # noqa: F403 集中阈值

PASS, WARN, FAIL, NOT_TESTED = "PASS", "WARN", "FAIL", "NOT_TESTED"


def validate_metrics(metrics: dict[str, object], *, identity_ok: bool | None = None,
                     ping_ok: bool | None = None, parser_errors: int | None = None,
                     crc_errors: int | None = None, command_success_rate: float | None = None,
                     fault_seen: bool | None = None, degraded_persistent: bool | None = None) -> ValidationResult:
    items: list[ValidationItem] = []
    def add(name, status, actual, threshold, reason):
        items.append(ValidationItem(name, status, actual, threshold, reason))
    add("device_identity", NOT_TESTED if identity_ok is None else PASS if identity_ok else FAIL,
        identity_ok, "must respond", "设备身份响应")
    add("ping", NOT_TESTED if ping_ok is None else PASS if ping_ok else FAIL,
        ping_ok, "must respond", "PING响应")
    requested, captured = metrics.get("requested_duration_s"), metrics.get("captured_duration_s")
    ratio = captured / requested if isinstance(requested, (int, float)) and requested and isinstance(captured, (int, float)) else None
    add("capture_duration", NOT_TESTED if ratio is None else PASS if ratio >= CAPTURE_DURATION_RATIO_PASS else FAIL,
        ratio, f">={CAPTURE_DURATION_RATIO_PASS:.0%}", "采集时长比例")
    frames = int(metrics.get("frame_count", 0))
    add("valid_frames", PASS if frames > 0 else FAIL, frames, ">0", "有效帧数")
    monotonic = metrics.get("device_timestamp_monotonic")
    add("device_timestamp", NOT_TESTED if monotonic is None else PASS if monotonic else FAIL,
        monotonic, "strictly monotonic", "设备时间戳")
    sequence = metrics.get("sequence", {}) if isinstance(metrics.get("sequence"), dict) else {}
    sequence_ok = sequence.get("duplicates") == 0 and sequence.get("regressions") == 0
    add("sequence", NOT_TESTED if not sequence else PASS if sequence_ok else FAIL,
        sequence, "duplicates=0, regressions=0", "sequence连续性")
    add("parser_errors", NOT_TESTED if parser_errors is None else PASS if parser_errors == 0 else FAIL,
        parser_errors, "=0", "Parser错误")
    add("crc_errors", NOT_TESTED if crc_errors is None else PASS if crc_errors == 0 else FAIL,
        crc_errors, "=0", "CRC错误")
    frequency = (metrics.get("frequency_hz") or {}).get("average") if isinstance(metrics.get("frequency_hz"), dict) else None
    add("telemetry_frequency", NOT_TESTED if frequency is None else
        PASS if TELEMETRY_HZ_PASS_MIN <= frequency <= TELEMETRY_HZ_PASS_MAX else FAIL,
        frequency, f"{TELEMETRY_HZ_PASS_MIN}..{TELEMETRY_HZ_PASS_MAX} Hz", "平均遥测频率")
    add("application_fault", NOT_TESTED if fault_seen is None else FAIL if fault_seen else PASS,
        fault_seen, "false", "采集期间不得FAULT")
    add("persistent_degraded", NOT_TESTED if degraded_persistent is None else FAIL if degraded_persistent else PASS,
        degraded_persistent, "false", "稳定阶段不得持续DEGRADED")
    angle_values = []
    for name in ("roll_deg", "pitch_deg"):
        value = metrics.get(name)
        if isinstance(value, dict): angle_values.extend(value.values())
    finite = bool(angle_values) and all(isinstance(value, (int, float)) and math.isfinite(value) for value in angle_values)
    add("attitude_finite", NOT_TESTED if not angle_values else PASS if finite else FAIL,
        finite if angle_values else None, "finite", "姿态不得NaN/Inf")
    spans = [value.get("peak_to_peak") for name in ("roll_deg", "pitch_deg")
             if isinstance((value := metrics.get(name)), dict)]
    spans = [value for value in spans if isinstance(value, (int, float))]
    movement = max(spans) if spans else None
    add("attitude_movement", NOT_TESTED if movement is None else
        PASS if movement >= ATTITUDE_MOVEMENT_PASS_DEG else WARN,
        movement, f">={ATTITUDE_MOVEMENT_PASS_DEG} deg",
        "交互会话中Roll或Pitch应随倾斜发生明显变化；不足仅警告，不据此判定算法失败")
    accel = (metrics.get("accel_magnitude_mg") or {}).get("mean") if isinstance(metrics.get("accel_magnitude_mg"), dict) else None
    accel_status = NOT_TESTED if accel is None else PASS if ACCEL_MAGNITUDE_PASS_MIN_MG <= accel <= ACCEL_MAGNITUDE_PASS_MAX_MG else WARN if ACCEL_MAGNITUDE_WARN_MIN_MG <= accel <= ACCEL_MAGNITUDE_WARN_MAX_MG else FAIL
    add("accel_magnitude", accel_status, accel,
        f"PASS {ACCEL_MAGNITUDE_PASS_MIN_MG}..{ACCEL_MAGNITUDE_PASS_MAX_MG} mg", "平均加速度模长")
    add("command_success", NOT_TESTED if command_success_rate is None else PASS if command_success_rate == 100.0 else FAIL,
        command_success_rate, "=100%", "命令成功率")
    statuses = {item.status for item in items}
    conclusion = "FAIL" if FAIL in statuses else "WARN" if WARN in statuses else "PASS" if NOT_TESTED not in statuses else "INFORMATION_INSUFFICIENT"
    return ValidationResult(conclusion, tuple(items))
