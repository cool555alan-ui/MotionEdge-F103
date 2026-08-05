#!/usr/bin/env python3
"""Phase 5 恢复后连续稳定运行采集，不重复人工运动与掉线步骤。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import serial

import hardware_validate as base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=600.0)
    parser.add_argument("--programmer-cli", type=Path, required=True)
    parser.add_argument("--stlink-serial", required=True)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("artifacts/rtos-validation"))
    args = parser.parse_args()
    if args.seconds < 600.0:
        parser.error("稳定运行验收不得少于 600 秒")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "stability-soak-raw.log"
    csv_path = args.output_dir / "stability-soak-capture.csv"
    summary_path = args.output_dir / "stability-soak-summary.json"

    port = serial.Serial(args.port, args.baud, timeout=0.1, xonxoff=False,
                         rtscts=False, dsrdtr=False)
    collector = base.Collector(port, raw_path)
    collector.phase = "warmup"
    collector.start()
    try:
        reset = subprocess.run(
            [str(args.programmer_cli), "-c",
             f"port=SWD sn={args.stlink_serial} freq=4000", "-rst"],
            capture_output=True, text=True, check=False)
        if reset.returncode != 0:
            raise RuntimeError(reset.stderr or reset.stdout)

        # 等待真实启动、身份识别、校准完成及 RUNNING，随后才开始 600 秒计时。
        warmup_deadline = time.monotonic() + 120.0
        while time.monotonic() < warmup_deadline:
            text = "\n".join(line for _, line in collector.lines)
            if ("WHO_AM_I=0x70" in text and "[INFO][CAL] complete" in text and
                    re.search(r"\bstate=RUNNING\b", text)):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("120 秒内未完成 MPU6500 识别、校准和 RUNNING")

        collector.phase = "soak"
        start = time.monotonic()
        time.sleep(args.seconds)
        elapsed = time.monotonic() - start
    finally:
        collector.stop()
        port.close()

    all_rows, parse_errors = base.parse_lines(collector.lines)
    rows = [row for row in all_rows if row.phase == "soak"]
    continuity = base.continuity(rows)
    soak_lines = [line for phase, line in collector.lines if phase == "soak"]
    text = "\n".join(soak_lines)
    states = re.findall(r"\bstate=(RUNNING|DEGRADED|FAULT)\b", text)
    miss_rows = [tuple(map(int, values)) for values in re.findall(
        r"\[INFO\]\[RTOS-DEADLINE\] miss=(\d+)/(\d+)/(\d+)/(\d+)", text)]
    miss_delta = ([end - begin for begin, end in zip(miss_rows[0], miss_rows[-1])]
                  if miss_rows else None)
    fatal = re.findall(
        r"\[INFO\]\[RTOS-FAIL\] stack_overflow=(\d+) malloc_failure=(\d+)", text)
    comm = re.findall(
        r"\[INFO\]\[RTOS-COMM\] rx=(\d+) crc=(\d+) parser=(\d+) command=(\d+) tx=(\d+)",
        text)
    checks = {
        "duration_600_seconds": "PASS" if elapsed >= 600.0 else "FAIL",
        "valid_frames": "PASS" if len(rows) >= 5900 else "FAIL",
        "timestamp_continuity": "PASS" if continuity["monotonic"] else "FAIL",
        "sequence_continuity": "PASS" if (
            continuity["estimated_lost_frames"] == 0 and
            continuity["sequence_regressions"] == 0) else "FAIL",
        "application_running": "PASS" if states and set(states) == {"RUNNING"} else "FAIL",
        "deadline_no_increase": "PASS" if miss_delta and sum(miss_delta) == 0 else "FAIL",
        "serial_parse_errors": "PASS" if parse_errors == 0 else "FAIL",
        "fatal_hooks": "PASS" if fatal and tuple(map(int, fatal[-1])) == (0, 0) else "FAIL",
        "communication_errors": "PASS" if comm and sum(map(int, comm[-1])) == 0 else "FAIL",
    }
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(base.COLUMNS)
        for row in rows:
            writer.writerow(row.values[name] for name in base.COLUMNS)
    result = {
        "validation_date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "port": args.port, "baud": args.baud, "elapsed_seconds": elapsed,
        "frame_count": len(rows), "continuity": continuity,
        "deadline_miss_delta": miss_delta, "state_counts": {
            name: states.count(name) for name in ("RUNNING", "DEGRADED", "FAULT")},
        "parse_errors": parse_errors, "checks": checks,
    }
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    return 1 if "FAIL" in checks.values() else 0


if __name__ == "__main__":
    raise SystemExit(main())
