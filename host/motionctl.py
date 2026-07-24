#!/usr/bin/env python3
"""MotionEdge CSV采集、模拟、校验、汇总和回放命令行工具。"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

COLUMNS = [
    "timestamp_ms",
    "sequence",
    "status_flags",
    "calibrated",
    "ax_mg",
    "ay_mg",
    "az_mg",
    "gx_mdps",
    "gy_mdps",
    "gz_mdps",
    "roll_cdeg",
    "pitch_cdeg",
]


@dataclass(frozen=True)
class MotionRow:
    values: tuple[int, ...]

    def __getitem__(self, name: str) -> int:
        return self.values[COLUMNS.index(name)]


def parse_row(fields: list[str], line_number: int) -> MotionRow:
    if len(fields) != len(COLUMNS):
        raise ValueError(
            f"line {line_number}: expected {len(COLUMNS)} columns, got {len(fields)}"
        )
    try:
        values = tuple(int(field, 10) for field in fields)
    except ValueError as exc:
        raise ValueError(f"line {line_number}: every field must be an integer") from exc
    if values[3] not in (0, 1):
        raise ValueError(f"line {line_number}: calibrated must be 0 or 1")
    if not -18000 <= values[10] <= 18000:
        raise ValueError(f"line {line_number}: roll_cdeg is outside [-18000, 18000]")
    if not -9000 <= values[11] <= 9000:
        raise ValueError(f"line {line_number}: pitch_cdeg is outside [-9000, 9000]")
    return MotionRow(values)


def load_rows(path: Path, check_sequence: bool = True) -> list[MotionRow]:
    if not path.is_file():
        raise ValueError(f"file not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("CSV file is empty") from exc
        if header != COLUMNS:
            raise ValueError("CSV header does not match the firmware schema")
        rows = [parse_row(fields, index) for index, fields in enumerate(reader, 2)]
    if not rows:
        raise ValueError("CSV contains a header but no data frames")
    for previous, current in zip(rows, rows[1:]):
        if current["timestamp_ms"] < previous["timestamp_ms"]:
            raise ValueError("timestamps must be non-decreasing")
        if check_sequence and current["sequence"] != previous["sequence"] + 1:
            raise ValueError(
                f"sequence gap: {previous['sequence']} -> {current['sequence']}"
            )
    return rows


def validate_file(path: Path) -> list[MotionRow]:
    rows = load_rows(path, check_sequence=True)
    print(f"VALID: {path} frames={len(rows)}")
    return rows


def summarize_rows(rows: list[MotionRow]) -> dict[str, object]:
    timestamps = [row["timestamp_ms"] for row in rows]
    sequences = [row["sequence"] for row in rows]
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]
    lost = sum(max(0, b - a - 1) for a, b in zip(sequences, sequences[1:]))
    rolls = [row["roll_cdeg"] for row in rows]
    pitches = [row["pitch_cdeg"] for row in rows]
    flags = Counter(row["status_flags"] for row in rows)
    return {
        "total_frames": len(rows),
        "valid_frames": sum(1 for row in rows if row["status_flags"] == 0),
        "start_ms": timestamps[0],
        "end_ms": timestamps[-1],
        "average_interval_ms": statistics.fmean(intervals) if intervals else 0.0,
        "lost_sequences": lost,
        "roll_min_cdeg": min(rolls),
        "roll_max_cdeg": max(rolls),
        "roll_mean_cdeg": statistics.fmean(rolls),
        "pitch_min_cdeg": min(pitches),
        "pitch_max_cdeg": max(pitches),
        "pitch_mean_cdeg": statistics.fmean(pitches),
        "status_flags": dict(sorted(flags.items())),
    }


def print_summary(summary: dict[str, object]) -> None:
    for key, value in summary.items():
        print(f"{key}: {value}")


def simulate(seconds: float, output: Path) -> None:
    if not math.isfinite(seconds) or seconds <= 0.0:
        raise ValueError("--seconds must be a positive finite number")
    frame_count = max(1, int(seconds * 100.0))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(COLUMNS)
        for sequence in range(1, frame_count + 1):
            phase = sequence / frame_count
            roll = 0
            pitch = 0
            if phase >= 1.0 / 3.0 and phase < 2.0 / 3.0:
                roll = int(3000.0 * math.sin((phase - 1.0 / 3.0) * 3.0 * math.pi))
            elif phase >= 2.0 / 3.0:
                pitch = int(2000.0 * math.sin((phase - 2.0 / 3.0) * 3.0 * math.pi))
            roll_rad = math.radians(roll / 100.0)
            pitch_rad = math.radians(pitch / 100.0)
            ax = int(-1000.0 * math.sin(pitch_rad))
            ay = int(1000.0 * math.sin(roll_rad) * math.cos(pitch_rad))
            az = int(1000.0 * math.cos(roll_rad) * math.cos(pitch_rad))
            writer.writerow(
                [sequence * 10, sequence, 0, 1, ax, ay, az, 0, 0, 0, roll, pitch]
            )
    print(f"SIMULATED DATA: generated {frame_count} frames at {output}")


def record(port: str, baud: int, output: Path) -> None:
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise RuntimeError("record requires pyserial; install host/requirements.txt") from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = serial.Serial(port=port, baudrate=baud, timeout=1.0)
    except serial.SerialException as exc:
        raise RuntimeError(f"unable to open serial port {port}: {exc}") from exc
    accepted = 0
    try:
        with connection, output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\r\n")
            writer.writerow(COLUMNS)
            print(f"Recording {port} at {baud} baud; press Ctrl+C to stop")
            while True:
                text = connection.readline().decode("utf-8", errors="strict").strip()
                if not text or text.startswith("[") or text == ",".join(COLUMNS):
                    continue
                fields = next(csv.reader([text]))
                try:
                    row = parse_row(fields, accepted + 2)
                except ValueError as exc:
                    print(f"ignored non-CSV line: {exc}", file=sys.stderr)
                    continue
                writer.writerow(row.values)
                accepted += 1
                if accepted % 25 == 0:
                    stream.flush()
    except KeyboardInterrupt:
        print(f"Stopped safely after {accepted} frames")


def replay(rows: Iterable[MotionRow], speed: float) -> None:
    if not math.isfinite(speed) or speed <= 0.0:
        raise ValueError("--speed must be a positive finite number")
    previous_timestamp: int | None = None
    print(",".join(COLUMNS))
    for row in rows:
        timestamp = row["timestamp_ms"]
        if previous_timestamp is not None:
            time.sleep(max(0.0, (timestamp - previous_timestamp) / 1000.0 / speed))
        print(",".join(str(value) for value in row.values))
        previous_timestamp = timestamp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    simulate_parser = subparsers.add_parser("simulate")
    simulate_parser.add_argument("--seconds", type=float, default=5.0)
    simulate_parser.add_argument("--output", type=Path, required=True)
    for command in ("validate", "summary", "replay"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("path", type=Path)
        if command == "replay":
            command_parser.add_argument("--speed", type=float, default=1.0)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--port", required=True)
    record_parser.add_argument("--baud", type=int, default=115200)
    record_parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "simulate":
            simulate(args.seconds, args.output)
        elif args.command == "validate":
            validate_file(args.path)
        elif args.command == "summary":
            print_summary(summarize_rows(load_rows(args.path, check_sequence=False)))
        elif args.command == "replay":
            replay(load_rows(args.path, check_sequence=False), args.speed)
        elif args.command == "record":
            record(args.port, args.baud, args.output)
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
