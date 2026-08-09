"""真实姿态输入到PID/PWM的有限采集与统计，不执行自动参数搜索。"""

from __future__ import annotations

import csv
import json
import math
import statistics
import time
from pathlib import Path

from . import commands
from .commands import (RuntimeConfig, decode_control_status, decode_motion)


def _rms(values: list[float]) -> float | None:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else None


def summarize_control_rows(rows: list[dict]) -> dict:
    if not rows:
        return {"status": "NOT_TESTED", "samples": 0}
    pwm = [float(row["actual_pwm_us"]) for row in rows]
    output = [float(row["output_us"]) for row in rows]
    relative = [float(row["relative_angle_deg"]) for row in rows]
    reversals = sum(1 for a, b in zip(output, output[1:])
                    if a and b and (a > 0) != (b > 0))
    intervals = [(b["host_monotonic_ns"] - a["host_monotonic_ns"]) / 1e9
                 for a, b in zip(rows, rows[1:]) if b["host_monotonic_ns"] > a["host_monotonic_ns"]]
    correlation = None
    if len(rows) > 1 and statistics.pstdev(relative) and statistics.pstdev(output):
        mr, mo = statistics.mean(relative), statistics.mean(output)
        correlation = sum((x-mr)*(y-mo) for x, y in zip(relative, output)) / math.sqrt(
            sum((x-mr)**2 for x in relative) * sum((y-mo)**2 for y in output))
    return {
        "status": "PASS",
        "samples": len(rows),
        "duration_s": ((rows[-1]["host_monotonic_ns"] - rows[0]["host_monotonic_ns"]) / 1e9
                       if len(rows) > 1 else 0.0),
        "control_frequency_hz": (1.0 / statistics.mean(intervals) if intervals else None),
        "pwm_min_us": min(pwm), "pwm_max_us": max(pwm),
        "pwm_mean_us": statistics.mean(pwm),
        "pwm_std_us": statistics.pstdev(pwm),
        "pwm_rms_offset_us": _rms([value - 1500.0 for value in pwm]),
        "pwm_peak_to_peak_us": max(pwm) - min(pwm),
        "output_rms_us": _rms(output),
        "direction_reversals": reversals,
        "saturation_count": sum(int(row["saturated"]) for row in rows),
        "deadband_samples": sum(int(row["in_deadband"]) for row in rows),
        "input_pwm_correlation": correlation,
        "interpretation": "HUMAN_INPUT_LIMITED",
    }


def run_control_capture(client, args, *, interactive: bool) -> dict:
    output: Path = args.output
    if args.duration <= 0:
        raise ValueError("duration must be positive")
    status = decode_control_status(client.request(commands.CONTROL_GET_STATUS))
    if not status.enabled:
        raise ValueError("control must already be armed and enabled before capture")
    config = RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
    if interactive:
        print("保持零位，然后缓慢倾斜到正方向、回零、负方向、回零；不要快速甩动。")
        input("确认舵机无遮挡且可随时断电，按Enter开始采集：")
    if not config.telemetry_enabled:
        client.request(commands.SET_STREAM_STATE, b"\1", retry=False)
    client.flush_input()
    rows: list[dict] = []
    latest_motion = None
    deadline = time.monotonic() + args.duration
    try:
        while time.monotonic() < deadline:
            client.poll()
            while client.telemetry:
                received_ns, frame = client.telemetry.popleft()
                if frame.type == commands.MOTION_TELEMETRY:
                    latest_motion = decode_motion(frame.payload, received_ns)
                elif frame.type == commands.CONTROL_TELEMETRY and latest_motion is not None:
                    control = decode_control_status(frame.payload)
                    rows.append({
                        "host_monotonic_ns": received_ns,
                        "device_timestamp_ms": latest_motion.device_timestamp_ms,
                        "axis": control.axis,
                        "roll_deg": latest_motion.roll_deg,
                        "pitch_deg": latest_motion.pitch_deg,
                        "relative_angle_deg": control.relative_angle_cdeg / 100.0,
                        "effective_error_deg": control.effective_error_cdeg / 100.0,
                        "p_us": control.p_term_us,
                        "i_us": control.i_term_us,
                        "d_us": control.d_term_us,
                        "output_us": control.output_us,
                        "actual_pwm_us": control.actual_pulse_us,
                        "saturated": int(control.saturated),
                        "in_deadband": int(control.in_deadband),
                        "mode": control.mode,
                    })
            time.sleep(0.005)
    finally:
        if not config.telemetry_enabled:
            client.request(commands.SET_STREAM_STATE, b"\0", retry=False)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "control-experiment.csv"
    fields = list(rows[0]) if rows else ["host_monotonic_ns", "device_timestamp_ms",
                                         "axis", "roll_deg", "pitch_deg",
                                         "relative_angle_deg", "effective_error_deg",
                                         "p_us", "i_us", "d_us", "output_us",
                                         "actual_pwm_us", "saturated", "in_deadband", "mode"]
    temporary = csv_path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    temporary.replace(csv_path)
    summary = summarize_control_rows(rows)
    (output / "control-experiment-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**summary, "csv": str(csv_path)}
