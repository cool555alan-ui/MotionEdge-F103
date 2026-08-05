"""流式、原子落盘且可在 Ctrl+C 后保留部分证据的采集。"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import commands
from .commands import decode_health, decode_motion
from .metrics import motion_metrics
from .models import CaptureMetadata, HealthSample, MotionSample, stable_dict
from .protocol import encode_frame

TELEMETRY_COLUMNS = (
    "host_monotonic_ns", "device_timestamp_ms", "sample_sequence", "status_flags",
    "calibrated", "ax_mg", "ay_mg", "az_mg", "gx_mdps", "gy_mdps", "gz_mdps",
    "roll_deg", "pitch_deg", "roll_cdeg_raw", "pitch_cdeg_raw")


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(stable_dict(value), stream, ensure_ascii=False, indent=2)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def capture_session(client, output: Path, duration_s: float, metadata: CaptureMetadata,
                    progress: Callable[[float, MotionSample | None], None] | None = None) -> dict[str, object]:
    if duration_s <= 0:
        raise ValueError("capture duration must be positive")
    output.mkdir(parents=True, exist_ok=True)
    raw_final, telemetry_final = output / "serial-raw.bin", output / "telemetry.csv"
    commands_final = output / "commands.csv"
    raw_temp, telemetry_temp = raw_final.with_suffix(".bin.tmp"), telemetry_final.with_suffix(".csv.tmp")
    commands_temp = commands_final.with_suffix(".csv.tmp")
    motion_frames = 0
    last_sample: MotionSample | None = None
    health: list[HealthSample] = []
    interrupted = False
    start_ns = time.monotonic_ns()
    last_progress = 0.0
    with raw_temp.open("wb") as raw_stream, telemetry_temp.open("w", encoding="utf-8", newline="") as telemetry_stream:
        writer = csv.DictWriter(telemetry_stream, fieldnames=TELEMETRY_COLUMNS, lineterminator="\n")
        writer.writeheader()
        try:
            while (time.monotonic_ns() - start_ns) / 1e9 < duration_s:
                chunk = client.transport.read(256)
                if chunk:
                    raw_stream.write(chunk)
                    for frame in client.parser.feed(chunk):
                        host_ns = time.monotonic_ns()
                        if frame.type == commands.MOTION_TELEMETRY:
                            sample = decode_motion(frame.payload, host_ns)
                            last_sample = sample
                            motion_frames += 1
                            writer.writerow(asdict(sample))
                        elif frame.type == commands.HEALTH_TELEMETRY:
                            health.append(decode_health(frame.payload, host_ns))
                elapsed = (time.monotonic_ns() - start_ns) / 1e9
                if progress is not None and elapsed - last_progress >= 0.2:
                    progress(elapsed, last_sample)
                    last_progress = elapsed
        except KeyboardInterrupt:
            interrupted = True
        finally:
            raw_stream.flush(); os.fsync(raw_stream.fileno())
            telemetry_stream.flush(); os.fsync(telemetry_stream.fileno())
    raw_temp.replace(raw_final); telemetry_temp.replace(telemetry_final)
    with commands_temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("command", "success", "rtt_ms", "sequence", "error"), lineterminator="\n")
        writer.writeheader()
        for item in client.command_results:
            writer.writerow(asdict(item))
        stream.flush(); os.fsync(stream.fileno())
    commands_temp.replace(commands_final)
    elapsed_s = (time.monotonic_ns() - start_ns) / 1e9
    _atomic_json(output / "session-metadata.json", metadata)
    summary = {"started_at": metadata.started_at, "ended_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
               "requested_duration_s": duration_s, "elapsed_s": elapsed_s,
               "interrupted": interrupted, "motion_frames": motion_frames, "health_frames": len(health),
               "parser": {"frames": client.parser.frames, "crc_errors": client.parser.crc_errors,
                          "length_errors": client.parser.length_errors,
                          "version_errors": client.parser.version_errors,
                          "discarded_bytes": client.parser.discarded_bytes},
               "metrics": motion_metrics(load_telemetry(telemetry_final), requested_duration_s=duration_s),
               "health": [stable_dict(item) for item in health]}
    _atomic_json(output / "capture-summary.json", summary)
    return summary


def load_telemetry(path: Path) -> list[MotionSample]:
    csv_path = path / "telemetry.csv" if path.is_dir() else path
    if not csv_path.is_file():
        return []
    result = []
    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            result.append(MotionSample(
                int(row["device_timestamp_ms"]), int(row["sample_sequence"]), int(row["status_flags"]),
                row["calibrated"].lower() in ("true", "1"), int(row["ax_mg"]), int(row["ay_mg"]),
                int(row["az_mg"]), int(row["gx_mdps"]), int(row["gy_mdps"]), int(row["gz_mdps"]),
                float(row["roll_deg"]), float(row["pitch_deg"]), int(row["roll_cdeg_raw"]),
                int(row["pitch_cdeg_raw"]), int(row["host_monotonic_ns"])))
    return result
