from __future__ import annotations

import csv
import json
import math
import statistics
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "phase09" / "pid-attitude"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_summary(name: str) -> dict:
    return json.loads((OUT / name / "control-experiment-summary.json").read_text(encoding="utf-8"))


def numeric(rows: list[dict], field: str) -> list[float]:
    return [float(row[field]) for row in rows]


def max_step(values: list[float]) -> float:
    return max((abs(b - a) for a, b in zip(values, values[1:])), default=0.0)


def experiment_comparison() -> list[dict]:
    configs = [
        ("P_ONLY", "pitch-p-only", 1.0, 0.0, 0.0),
        ("PD_FINAL", "pitch-pd-valid", 1.0, 0.0, 0.05),
    ]
    result = []
    for mode, folder, kp, ki, kd in configs:
        summary = load_summary(folder)
        rows = read_rows(OUT / folder / "control-experiment.csv")
        result.append({
            "mode": mode, "kp_us_per_deg": kp, "ki": ki,
            "kd_us_per_deg_per_s": kd, "integral_mode": "DISABLED",
            "samples": summary["samples"], "duration_s": summary["duration_s"],
            "input_min_deg": min(numeric(rows, "relative_angle_deg")),
            "input_max_deg": max(numeric(rows, "relative_angle_deg")),
            "pwm_rms_offset_us": summary["pwm_rms_offset_us"],
            "pwm_std_us": summary["pwm_std_us"],
            "pwm_peak_to_peak_us": summary["pwm_peak_to_peak_us"],
            "max_output_step_us": max_step(numeric(rows, "output_us")),
            "direction_reversals": summary["direction_reversals"],
            "saturation_count": summary["saturation_count"],
            "input_pwm_correlation": summary["input_pwm_correlation"],
            "interpretation": "HUMAN_INPUT_LIMITED",
        })
    result.append({**result[-1], "mode": "GENERAL_PID_FINAL_KI_ZERO",
                   "note": "General PID module used as PD; Ki intentionally zero."})
    return result


def static_mapping(pd_rows: list[dict]) -> list[dict]:
    result = []
    for target in (-15, -10, -5, 0, 5, 10, 15):
        row = min(pd_rows, key=lambda value: abs(float(value["relative_angle_deg"]) - target))
        result.append({
            "reference_target_deg": target,
            "measured_roll_deg": row["roll_deg"],
            "measured_pitch_deg": row["pitch_deg"],
            "relative_angle_deg": row["relative_angle_deg"],
            "p_us": row["p_us"], "i_us": row["i_us"], "d_us": row["d_us"],
            "output_us": row["output_us"], "actual_pwm_us": row["actual_pwm_us"],
            "limitation": "REFERENCE_LIMITED; nearest real sample, not servo angle",
        })
    return result


def deadband_comparison() -> list[dict]:
    result = []
    for value in (0.5, 1.0, 1.5, 2.0):
        folder = f"deadband-{value:.1f}"
        summary = load_summary(folder)
        rows = read_rows(OUT / folder / "control-experiment.csv")
        pwm = numeric(rows, "actual_pwm_us")
        result.append({
            "deadband_deg": value, "samples": len(rows),
            "duration_s": summary["duration_s"],
            "pwm_min_us": min(pwm), "pwm_max_us": max(pwm),
            "pwm_std_us": statistics.pstdev(pwm),
            "pwm_change_count": sum(a != b for a, b in zip(pwm, pwm[1:])),
            "direction_reversals": summary["direction_reversals"],
            "saturation_count": summary["saturation_count"],
            "deadband_samples": summary["deadband_samples"],
            "selected": value == 1.0,
        })
    return result


def stability_rows() -> tuple[list[dict], dict]:
    source = OUT / "stability-600s" / "continuous-final"
    rows = read_rows(source / "control-experiment.csv")
    first = int(rows[0]["host_monotonic_ns"])
    result = []
    for row in rows:
        elapsed = (int(row["host_monotonic_ns"]) - first) / 1e9
        if elapsed < 120:
            stage = "00-120_STILL"
        elif elapsed < 240:
            stage = "120-240_ROLL_MOTION"
        elif elapsed < 360:
            stage = "240-360_STILL"
        elif elapsed < 480:
            stage = "360-480_PITCH_MOTION_NOT_OBSERVED"
        else:
            stage = "480-600_STILL"
        result.append({"elapsed_s": f"{elapsed:.6f}", "stage": stage, **row})
    return result, json.loads((source / "control-experiment-summary.json").read_text(encoding="utf-8"))


def make_charts(stability: list[dict], comparisons: list[dict], deadbands: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    elapsed = numeric(stability, "elapsed_s")
    roll = numeric(stability, "roll_deg")
    pitch = numeric(stability, "pitch_deg")
    pwm = numeric(stability, "actual_pwm_us")

    plt.figure(figsize=(10, 4)); plt.plot(elapsed, roll, label="Roll"); plt.plot(elapsed, pitch, label="Pitch")
    plt.xlabel("Time (s)"); plt.ylabel("Angle (deg)"); plt.legend(); plt.tight_layout(); plt.savefig(OUT / "angle-vs-time.png", dpi=140); plt.close()
    plt.figure(figsize=(10, 4)); plt.plot(elapsed, numeric(stability, "p_us"), label="P"); plt.plot(elapsed, numeric(stability, "i_us"), label="I"); plt.plot(elapsed, numeric(stability, "d_us"), label="D")
    plt.xlabel("Time (s)"); plt.ylabel("PID term (us)"); plt.legend(); plt.tight_layout(); plt.savefig(OUT / "pid-terms.png", dpi=140); plt.close()
    plt.figure(figsize=(10, 4)); plt.plot(elapsed, pwm); plt.axhline(1490, color="r", ls="--"); plt.axhline(1510, color="r", ls="--")
    plt.xlabel("Time (s)"); plt.ylabel("PWM (us)"); plt.tight_layout(); plt.savefig(OUT / "pwm-output.png", dpi=140); plt.close()
    labels = [row["mode"] for row in comparisons[:2]]; x = range(len(labels))
    plt.figure(figsize=(7, 4)); plt.bar(x, [row["pwm_std_us"] for row in comparisons[:2]], label="PWM std"); plt.bar(x, [row["pwm_rms_offset_us"] for row in comparisons[:2]], alpha=.55, label="PWM RMS offset")
    plt.xticks(list(x), labels); plt.ylabel("us"); plt.legend(); plt.tight_layout(); plt.savefig(OUT / "p-vs-pd.png", dpi=140); plt.close()
    plt.figure(figsize=(7, 4)); plt.bar([str(row["deadband_deg"]) for row in deadbands], [row["pwm_change_count"] for row in deadbands])
    plt.xlabel("Deadband (deg)"); plt.ylabel("Static PWM changes / 120 s"); plt.tight_layout(); plt.savefig(OUT / "deadband-effect.png", dpi=140); plt.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    comparisons = experiment_comparison()
    pd_rows = read_rows(OUT / "pitch-pd-valid" / "control-experiment.csv")
    dynamic = []
    for label, folder in (("P_ONLY", "pitch-p-only"), ("PD", "pitch-pd-valid"), ("REVERSE", "pitch-pd-reverse")):
        for row in read_rows(OUT / folder / "control-experiment.csv"):
            dynamic.append({"experiment": label, **row})
    deadbands = deadband_comparison()
    stability, stability_summary = stability_rows()
    safety = [
        {"check": "Arm", "status": "PASS", "scope": "REAL_HARDWARE"},
        {"check": "Disarm", "status": "PASS", "scope": "REAL_HARDWARE"},
        {"check": "ESTOP", "status": "PASS", "scope": "REAL_HARDWARE"},
        {"check": "Sensor offline", "status": "PASS", "scope": "REAL_HARDWARE", "evidence": "sensor-offline-final.txt"},
        {"check": "Motion stale", "status": "PASS", "scope": "REAL_HARDWARE_RAM_INJECTION", "evidence": "motion-stale-injection.txt"},
        {"check": "App Fault", "status": "PASS", "scope": "REAL_HARDWARE_RAM_INJECTION", "evidence": "app-fault-injection.txt"},
        {"check": "PWM clamp", "status": "PASS", "scope": "REAL_HARDWARE", "evidence": "1490..1510 observed; absolute service window 1450..1550"},
        {"check": "Broker down 10 s", "status": "PASS", "scope": "REAL_HARDWARE", "evidence": "update_count 104580 to 106300"},
        {"check": "Gateway exit 10 s", "status": "PASS", "scope": "REAL_HARDWARE", "evidence": "update_count 106300 to 108282"},
    ]
    write_rows(OUT / "pid-config-comparison.csv", comparisons)
    write_rows(OUT / "static-input-output.csv", static_mapping(pd_rows))
    write_rows(OUT / "dynamic-input-output.csv", dynamic)
    write_rows(OUT / "deadband-comparison.csv", deadbands)
    write_rows(OUT / "safety-validation.csv", safety)
    write_rows(OUT / "stability-600s.csv", stability)
    make_charts(stability, comparisons, deadbands)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    summary = {
        "status": "PASS_WITH_WARNINGS",
        "validated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": commit, "firmware_version": "0.9.1", "gateway_version": "0.9.1",
        "control": {"axis": "PITCH", "frequency_hz_local": 100, "kp": 1.0, "ki": 0.0, "kd": 0.05,
                    "deadband_deg": 1.0, "derivative_alpha": 0.2, "integral_mode": "DISABLED",
                    "pid_output_limit_us": [-10, 10], "actuator_absolute_window_us": [1450, 1550]},
        "stability_600s": {**stability_summary, "fault_count_delta": 0, "stale_count_delta": 0,
                           "nonfinite_count_delta": 0, "final_disabled": True, "final_estop": True},
        "rtos": {"stack_remaining_bytes": [384, 568, 200, 456], "heap_free_bytes": 3064,
                 "minimum_ever_heap_bytes": 2440, "deadline_miss_cumulative": [19, 0, 0, 0],
                 "stack_overflow": 0, "malloc_failure": 0},
        "regression": {"c_assertions": "717/717", "python_tests": "123/123", "phase_checks": "1-9B PASS",
                       "debug_flash_bytes": 57736, "debug_ram_bytes": 17688,
                       "release_flash_bytes": 50516, "release_ram_bytes": 17688, "compiler_warnings": 0},
        "warnings": ["Pitch motion was not observed inside the continuous 360-480 s segment; separate real Pitch experiment covers -45.15..45.61 deg.",
                     "Sensor deadline miss is cumulative 19 since reset; a start snapshot was not captured.",
                     "PWM electrical jitter NOT_TESTED; iPhone angle reference remains REFERENCE_LIMITED."],
        "not_applicable": ["external plant settling time", "external plant overshoot", "external steady-state control error"],
    }
    (OUT / "phase09b-pid-attitude-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = f"""# Phase 9B PID Attitude Control Hardware Validation

- Status: **PASS_WITH_WARNINGS**
- Date: {summary['validated_at']}
- Commit: `{commit}` (validation worktree is not committed yet)
- Firmware/Gateway: 0.9.1 / 0.9.1

## Final configuration

Pitch, Normal, Kp=1.0 us/deg, Ki=0, Kd=0.05 us/(deg/s), deadband=1.0 deg, derivative alpha=0.2, integral disabled. PID output is a PWM offset limited to +/-10 us and still passes through ActuatorService's absolute 1450..1550 us clamp.

## Real hardware results

- Roll interaction: -7.70..5.42 deg, PWM 1492..1505 us, correlation 0.972.
- Pitch interaction: -45.15..45.61 deg, PWM 1490..1510 us, 3 reversals.
- Reverse mapping: relative/PWM correlation -0.996.
- Continuous run: {stability_summary['samples']} frames / {stability_summary['duration_s']:.2f} s, PWM {stability_summary['pwm_min_us']:.0f}..{stability_summary['pwm_max_us']:.0f} us, faults 0, final Disabled/ESTOP.
- RTOS stack remaining: 384/568/200/456 B; heap 3064/2440 B; stack overflow and malloc failure 0.
- Broker-down and gateway-exit local-control tests: PASS. Node-RED quick regression: 52 frames, all parser/sequence checks 0, P95 1 ms.

## Safety

Arm, Disarm, ESTOP, Sensor offline, Motion stale, App Fault and PWM clamp all passed on real hardware. App Fault and Motion stale used volatile RAM injection at ELF-map addresses and were followed by reset; Flash and Option Bytes were not changed.

## Warnings

- The continuous 360-480 s stage did not contain visible Pitch movement; independent Pitch hardware evidence covers both directions.
- SensorTask deadline miss is a cumulative value of 19 since reset; no start snapshot exists, so its delta is NOT_TESTED.
- PWM electrical jitter is NOT_TESTED. The iPhone reference is REFERENCE_LIMITED.

## Control Interpretation and Limitations

1. The system has one MPU6500 and it measures user-held input attitude.
2. SG90 motion does not feed back into that MPU6500, so no external mechanical attitude loop exists.
3. The PID genuinely runs on STM32 at 100 Hz and changes real SG90 PWM; SG90 has its own internal position loop.
4. This is PID-based attitude-driven servo control. External plant settling time, overshoot and steady-state control error are NOT_APPLICABLE.

本阶段实现了基于单IMU姿态输入的PID舵机控制，PID在STM32端100 Hz真实运行；由于舵机运动不反馈至同一MPU6500，因此不将其描述为外部姿态闭环控制。
"""
    (OUT / "phase09b-pid-attitude-report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
