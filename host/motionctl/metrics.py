"""不依赖串口的纯数据统计。"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Iterable

from .models import CommandResult, MotionSample


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100.0
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def infer_sequence_step(sequences: list[int], configured_step: int | None = None) -> tuple[int | None, str]:
    if configured_step is not None and configured_step > 0:
        return configured_step, "device_config"
    positive = [b - a for a, b in zip(sequences, sequences[1:]) if b > a]
    if not positive:
        return None, "insufficient_data"
    return Counter(positive).most_common(1)[0][0], "dominant_step"


def motion_metrics(samples: Iterable[MotionSample], *, expected_step: int | None = None,
                   requested_duration_s: float | None = None) -> dict[str, object]:
    rows = list(samples)
    if not rows:
        return {"frame_count": 0, "valid_frame_count": 0, "invalid_frame_count": 0,
                "requested_duration_s": requested_duration_s}
    device = [row.device_timestamp_ms for row in rows]
    host = [row.host_monotonic_ns for row in rows if row.host_monotonic_ns is not None]
    intervals = [float(b - a) for a, b in zip(device, device[1:])]
    host_intervals = [(b - a) / 1_000_000.0 for a, b in zip(host, host[1:])]
    sequences = [row.sample_sequence for row in rows]
    step, source = infer_sequence_step(sequences, expected_step)
    deltas = [b - a for a, b in zip(sequences, sequences[1:])]
    duplicates = sum(delta == 0 for delta in deltas)
    regressions = sum(delta < 0 for delta in deltas)
    gaps = sum(delta > step for delta in deltas) if step else 0
    lost = sum(max(0, delta // step - 1) for delta in deltas if step and delta > 0)
    duration_s = (device[-1] - device[0]) / 1000.0 if len(device) > 1 else 0.0
    frequencies = [1000.0 / value for value in intervals if value > 0]
    accel_magnitudes = [math.sqrt(row.ax_mg ** 2 + row.ay_mg ** 2 + row.az_mg ** 2)
                         for row in rows]
    def stats(values: list[float]) -> dict[str, float | None]:
        return {"mean": statistics.fmean(values) if values else None,
                "median": statistics.median(values) if values else None,
                "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0 if values else None,
                "p95": percentile(values, 95), "min": min(values) if values else None,
                "max": max(values) if values else None}
    def axis(values: list[float]) -> dict[str, float]:
        return {"min": min(values), "max": max(values), "mean": statistics.fmean(values),
                "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
                "peak_to_peak": max(values) - min(values)}
    return {
        "frame_count": len(rows), "valid_frame_count": sum(row.status_flags == 0 for row in rows),
        "invalid_frame_count": sum(row.status_flags != 0 for row in rows),
        "requested_duration_s": requested_duration_s, "captured_duration_s": duration_s,
        "device_timestamp_monotonic": all(b > a for a, b in zip(device, device[1:])),
        "host_timestamp_monotonic": all(b > a for a, b in zip(host, host[1:])),
        "interval_ms": stats(intervals), "host_interval_ms": stats(host_intervals),
        "frequency_hz": {**stats(frequencies), "average": len(rows) / duration_s if duration_s else None},
        "sequence": {"first": sequences[0], "last": sequences[-1], "expected_step": step,
                     "step_source": source, "duplicates": duplicates, "regressions": regressions,
                     "gaps": gaps, "estimated_lost": lost},
        "roll_deg": axis([row.roll_deg for row in rows]),
        "pitch_deg": axis([row.pitch_deg for row in rows]),
        "accel_magnitude_mg": {**stats(accel_magnitudes),
                               "mean_absolute_error_from_1000": statistics.fmean(
                                   abs(value - 1000.0) for value in accel_magnitudes)},
        "accel_axes_mg": {name: {"min": min(values), "max": max(values)} for name, values in {
            "x": [row.ax_mg for row in rows], "y": [row.ay_mg for row in rows],
            "z": [row.az_mg for row in rows]}.items()},
        "gyro_mdps_ranges": {name: {"min": min(values), "max": max(values)} for name, values in {
            "x": [row.gx_mdps for row in rows], "y": [row.gy_mdps for row in rows],
            "z": [row.gz_mdps for row in rows]}.items()},
    }


def command_metrics(results: Iterable[CommandResult]) -> dict[str, object]:
    rows = list(results)
    rtts = [row.rtt_ms for row in rows if row.success]
    return {"requests": len(rows), "successes": sum(row.success for row in rows),
            "timeouts": sum(bool(row.error and "timeout" in row.error.lower()) for row in rows),
            "errors": sum(not row.success for row in rows),
            "success_rate_percent": 100.0 * sum(row.success for row in rows) / len(rows) if rows else None,
            "rtt_ms": {"mean": statistics.fmean(rtts) if rtts else None,
                       "median": statistics.median(rtts) if rtts else None,
                       "p95": percentile(rtts, 95), "max": max(rtts) if rtts else None}}
