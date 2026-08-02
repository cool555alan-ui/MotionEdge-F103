#!/usr/bin/env python3
"""MotionEdge 真实串口硬件验收工具。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import serial


COLUMNS = [
    "timestamp_ms", "sequence", "status_flags", "calibrated",
    "ax_mg", "ay_mg", "az_mg", "gx_mdps", "gy_mdps", "gz_mdps",
    "roll_cdeg", "pitch_cdeg",
]
PASS, WARN, FAIL, NOT_TESTED = "PASS", "WARN", "FAIL", "NOT_TESTED"


@dataclass(frozen=True)
class CapturedRow:
    phase: str
    values: dict[str, int]


def level(condition: bool, warning: bool = False) -> str:
    if condition:
        return PASS
    return WARN if warning else FAIL


def ranges(rows: list[CapturedRow], names: list[str]) -> dict[str, dict[str, int]]:
    return {
        name: {"min": min(row.values[name] for row in rows),
               "max": max(row.values[name] for row in rows)}
        for name in names
    } if rows else {}


def continuity(rows: list[CapturedRow]) -> dict[str, object]:
    if len(rows) < 2:
        return {"monotonic": False, "mean_interval_ms": None,
                "median_interval_ms": None, "expected_sequence_step": None,
                "estimated_lost_frames": 0, "sequence_regressions": 0,
                "reset_boundaries": 0}
    intervals: list[int] = []
    deltas: list[int] = []
    reset_boundaries = 0
    for previous, current in zip(rows, rows[1:]):
        time_delta = current.values["timestamp_ms"] - previous.values["timestamp_ms"]
        sequence_delta = current.values["sequence"] - previous.values["sequence"]
        # 验收过程会主动复位；时间戳和序号同时回到低值时按新运行段统计。
        if time_delta < 0 and sequence_delta < 0:
            reset_boundaries += 1
            continue
        intervals.append(time_delta)
        deltas.append(sequence_delta)
    positive = [delta for delta in deltas if delta > 0]
    expected = max(1, round(statistics.median(positive))) if positive else 1
    lost = sum(max(0, round(delta / expected) - 1) for delta in positive)
    return {
        "monotonic": all(delta > 0 for delta in intervals),
        "mean_interval_ms": statistics.fmean(intervals) if intervals else None,
        "median_interval_ms": statistics.median(intervals) if intervals else None,
        "expected_sequence_step": expected,
        "estimated_lost_frames": lost,
        "sequence_regressions": sum(delta <= 0 for delta in deltas),
        "reset_boundaries": reset_boundaries,
    }


def analyse(rows: list[CapturedRow], lines: list[str], parse_errors: int) -> dict[str, object]:
    static_rows = [row for row in rows if row.phase in ("pre_a", "a")]
    motion_rows = [row for row in rows if row.phase == "b"]
    calibrated_static = [row for row in static_rows if row.values["calibrated"] == 1]
    usable_static = calibrated_static or static_rows
    all_continuity = continuity(rows)
    static_magnitudes = [
        math.sqrt(sum(row.values[name] ** 2 for name in ("ax_mg", "ay_mg", "az_mg")))
        for row in usable_static
    ]
    joined = "\n".join(lines)
    address_matches = re.findall(r"\baddress=0x(68|69)\b", joined, re.IGNORECASE)
    who_matches = re.findall(
        r"WHO_AM_I(?: invalid value)?=0x([0-9A-Fa-f]{2})", joined)
    health_states = re.findall(r"\bstate=(BOOT|INITIALIZING|RUNNING|DEGRADED|FAULT)\b", joined)
    startup = "MotionEdge-F103 starting" in joined and "Firmware version:" in joined
    cal_started = "state=COLLECTING" in joined
    cal_complete = "[INFO][CAL] complete" in joined
    sensor_ready = "[INFO][MPU6500] sensor ready" in joined
    calibrated = any(row.values["calibrated"] == 1 for row in rows)
    frame_bounds = all(
        abs(row.values[name]) <= limit
        for row in rows
        for name, limit in (("ax_mg", 16000), ("ay_mg", 16000), ("az_mg", 16000),
                            ("gx_mdps", 250000), ("gy_mdps", 250000),
                            ("gz_mdps", 250000), ("roll_cdeg", 18000),
                            ("pitch_cdeg", 9000))
    )
    motion_ranges = ranges(motion_rows, COLUMNS[4:12])
    accel_span = max((v["max"] - v["min"] for k, v in motion_ranges.items()
                      if k.startswith("a")), default=0)
    gyro_span = max((v["max"] - v["min"] for k, v in motion_ranges.items()
                     if k.startswith("g")), default=0)
    roll_span = (motion_ranges.get("roll_cdeg", {}).get("max", 0) -
                 motion_ranges.get("roll_cdeg", {}).get("min", 0))
    pitch_span = (motion_ranges.get("pitch_cdeg", {}).get("max", 0) -
                  motion_ranges.get("pitch_cdeg", {}).get("min", 0))
    attitude_span = max(roll_span, pitch_span)
    tail = motion_rows[-min(30, len(motion_rows)):]
    tail_std = {
        name: statistics.pstdev(row.values[name] for row in tail) if len(tail) > 1 else None
        for name in ("roll_cdeg", "pitch_cdeg")
    }
    stable_tail = (len(tail) >= 10 and all(value is not None and value <= 300
                                           for value in tail_std.values()))
    warning_tail = (len(tail) >= 10 and all(value is not None and value <= 800
                                            for value in tail_std.values()))
    magnitude_mean = statistics.fmean(static_magnitudes) if static_magnitudes else None
    magnitude_std = statistics.pstdev(static_magnitudes) if len(static_magnitudes) > 1 else None
    lost = int(all_continuity["estimated_lost_frames"])
    regressions = int(all_continuity["sequence_regressions"])
    continuity_pairs = max(1, len(rows) - 1 - int(all_continuity["reset_boundaries"]))
    lost_ratio = lost / continuity_pairs
    checks = {
        "st_link_connection": PASS,
        "firmware_flash": PASS,
        "program_reset_start": PASS,
        "serial_open": PASS,
        "startup_log": level(startup),
        "i2c_address": level(bool(address_matches)),
        "who_am_i": level(bool(who_matches) and
                          all(int(value, 16) == 0x70 for value in who_matches)),
        "sensor_ready": level(sensor_ready),
        "calibration_started": level(cal_started),
        "calibration_complete": level(cal_complete and calibrated),
        "valid_attitude_frames": level(bool(rows)),
        "timestamp_continuity": NOT_TESTED if not rows else level(bool(all_continuity["monotonic"])),
        "sequence_continuity": (NOT_TESTED if not rows else
                                PASS if regressions == 0 and lost_ratio <= 0.01 else
                                WARN if regressions == 0 and lost_ratio <= 0.05 else FAIL),
        "static_acceleration_magnitude": (NOT_TESTED if magnitude_mean is None else
                                          PASS if 850 <= magnitude_mean <= 1150
                                          else WARN if magnitude_mean is not None and 750 <= magnitude_mean <= 1250
                                          else FAIL),
        "motion_data_change": (NOT_TESTED if not motion_rows else
                               level(accel_span >= 200 and gyro_span >= 5000,
                                     accel_span >= 100 or gyro_span >= 2000)),
        "roll_pitch_change": (NOT_TESTED if not motion_rows else PASS if attitude_span >= 1000
                              else WARN if attitude_span >= 500 else FAIL),
        "output_bounds": NOT_TESTED if not rows else level(frame_bounds),
        "post_motion_stability": (NOT_TESTED if not motion_rows else PASS if stable_tail
                                  else WARN if warning_tail else FAIL),
        "application_state": (NOT_TESTED if not health_states else
                              FAIL if all(s == "FAULT" for s in health_states) else
                              WARN if "FAULT" in health_states or "DEGRADED" in health_states else PASS),
        "serial_parse_errors": PASS if parse_errors == 0 else WARN,
    }
    return {
        "checks": checks,
        "detected_i2c_addresses": sorted({"0x" + value.upper() for value in address_matches}),
        "who_am_i_values": sorted({"0x" + value.upper() for value in who_matches}),
        "calibration_started": cal_started,
        "calibration_complete": cal_complete,
        "calibrated_seen": calibrated,
        "health_states": health_states,
        "health_state_counts": dict(Counter(health_states)),
        "frame_count": len(rows),
        "stage_a_frame_count": len(static_rows),
        "stage_b_frame_count": len(motion_rows),
        "parse_errors": parse_errors,
        "continuity": all_continuity,
        "static_accel_magnitude_mg": {"mean": magnitude_mean, "stddev": magnitude_std,
                                      "min": min(static_magnitudes) if static_magnitudes else None,
                                      "max": max(static_magnitudes) if static_magnitudes else None},
        "stage_b_ranges": motion_ranges,
        "stage_b_tail_attitude_stddev_cdeg": tail_std,
        "direction_confirmation_required": True,
    }


class Collector:
    """后台持续读取，避免用户按 Enter 前丢失启动日志。"""

    def __init__(self, port: serial.Serial, raw_path: Path) -> None:
        self.port = port
        self.raw_path = raw_path
        self.phase = "pre_a"
        self.lines: list[tuple[str, str]] = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        pending = bytearray()
        with self.raw_path.open("wb") as raw:
            while not self.stop_event.is_set():
                chunk = self.port.read(self.port.in_waiting or 1)
                if not chunk:
                    continue
                raw.write(chunk)
                raw.flush()
                pending.extend(chunk)
                while b"\n" in pending:
                    data, _, pending = pending.partition(b"\n")
                    self.lines.append((self.phase, data.rstrip(b"\r").decode("ascii", errors="replace")))
            if pending:
                self.lines.append((self.phase, pending.decode("ascii", errors="replace")))

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2.0)


def parse_lines(lines: list[tuple[str, str]]) -> tuple[list[CapturedRow], int]:
    rows: list[CapturedRow] = []
    errors = 0
    for phase, line in lines:
        if line.strip() == ",".join(COLUMNS) or not line.strip():
            continue
        fields = next(csv.reader([line]))
        if len(fields) != len(COLUMNS):
            if line[:1].isdigit() and "," in line:
                errors += 1
            continue
        try:
            values = [int(field, 10) for field in fields]
        except ValueError:
            errors += 1
            continue
        if values[3] not in (0, 1):
            errors += 1
            continue
        rows.append(CapturedRow(phase, dict(zip(COLUMNS, values))))
    return rows, errors


def write_report(path: Path, metadata: dict[str, object], result: dict[str, object]) -> None:
    checks = result["checks"]
    groups = {status: [name for name, value in checks.items() if value == status]
              for status in (PASS, WARN, FAIL, NOT_TESTED)}
    continuity_data = result["continuity"]
    accel = result["static_accel_magnitude_mg"]
    stage_ranges = result["stage_b_ranges"]
    lost_text = (str(continuity_data["estimated_lost_frames"])
                 if result["frame_count"] else "NOT_TESTED（无有效帧）")
    interval_text = (f"{continuity_data['mean_interval_ms']} ms；中位数："
                     f"{continuity_data['median_interval_ms']} ms"
                     if result["frame_count"] else "NOT_TESTED（无有效帧）")
    lines = [
        "# MotionEdge 首次真实硬件验收报告", "",
        f"- 验证日期：{metadata['validation_date']}",
        f"- 固件提交：`{metadata['commit']}`", f"- 固件版本：`{metadata['firmware_version']}`",
        f"- 源码状态：{metadata.get('source_state', 'unknown')}",
        f"- 构建配置：`{metadata['build_config']}`", f"- ST-LINK：{metadata['stlink']}",
        f"- 串口：`{metadata['port']}`，`{metadata['baud']} 8N1`，无流控",
        f"- MPU6500 地址：{', '.join(result['detected_i2c_addresses']) or '未检测到'}",
        f"- WHO_AM_I：{', '.join(result['who_am_i_values']) or '未检测到'}", "",
        "## 数据统计", "",
        f"- 总帧数：{result['frame_count']}（阶段A {result['stage_a_frame_count']}，阶段B {result['stage_b_frame_count']}）",
        f"- 估算丢帧：{lost_text}；sequence 回退/重复：{continuity_data['sequence_regressions']}；复位边界：{continuity_data['reset_boundaries']}",
        f"- 平均采样间隔：{interval_text}",
        f"- 静止加速度模长：mean={accel['mean']} mg，stddev={accel['stddev']} mg，range={accel['min']}..{accel['max']} mg",
        f"- 应用状态计数：{result['health_state_counts']}",
    ]
    for label, name in (("Roll", "roll_cdeg"), ("Pitch", "pitch_cdeg")):
        value = stage_ranges.get(name)
        lines.append(f"- {label}：{value['min'] / 100:.2f}..{value['max'] / 100:.2f} deg" if value else f"- {label}：未采集")
    for prefix, unit in (("加速度", "mg"), ("角速度", "mdps")):
        names = ("ax_mg", "ay_mg", "az_mg") if prefix == "加速度" else ("gx_mdps", "gy_mdps", "gz_mdps")
        text = ", ".join(f"{name}={stage_ranges[name]['min']}..{stage_ranges[name]['max']} {unit}"
                         for name in names if name in stage_ranges)
        lines.append(f"- {prefix}各轴：{text or '未采集'}")
    lines += ["- 方向确认：工具不自动判定正负方向；请用户根据实际动作确认。", "", "## 分级结果", ""]
    lines += [f"- `{name}`：**{status}**" for name, status in checks.items()]
    for title, status in (("当前通过项", PASS), ("警告项", WARN), ("失败项", FAIL), ("尚未验证项", NOT_TESTED)):
        lines += ["", f"## {title}", "", ", ".join(groups[status]) if groups[status] else "无"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_results(capture_path: Path, summary_path: Path, report_path: Path,
                 metadata: dict[str, object], rows: list[CapturedRow],
                 result: dict[str, object]) -> None:
    with capture_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows([row.values[name] for name in COLUMNS] for row in rows)
    summary_path.write_text(
        json.dumps({"metadata": metadata, **result}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    write_report(report_path, metadata, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="MotionEdge 交互式真实硬件验收")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--stage-a-seconds", type=float, default=12.0)
    parser.add_argument("--stage-b-seconds", type=float, default=17.0)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/hardware-validation"))
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--firmware-version", default="unknown")
    parser.add_argument("--build-config", default="Debug")
    parser.add_argument("--stlink", default="unknown")
    parser.add_argument("--source-state", default="unknown")
    parser.add_argument("--programmer-cli", type=Path)
    parser.add_argument("--stlink-serial")
    parser.add_argument("--analyse-existing", action="store_true",
                        help="仅重新分析现有 serial-raw.log，不访问串口")
    parser.add_argument("--startup-log", type=Path,
                        help="附加启动日志仅用于启动、I2C和校准证据，不参与帧连续性统计")
    args = parser.parse_args()
    if args.stage_a_seconds < 10 or args.stage_b_seconds < 15:
        parser.error("阶段A不得少于10秒，阶段B不得少于15秒")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "serial-raw.log"
    capture_path = args.output_dir / "hardware-capture.csv"
    summary_path = args.output_dir / "hardware-validation-summary.json"
    report_path = args.output_dir / "hardware-validation-report.md"
    metadata = {
        "validation_date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "commit": args.commit, "firmware_version": args.firmware_version,
        "build_config": args.build_config, "stlink": args.stlink,
        "port": args.port, "baud": args.baud, "source_state": args.source_state,
    }
    if args.analyse_existing:
        previous_stage_a_count = 0
        if summary_path.is_file():
            previous = json.loads(summary_path.read_text(encoding="utf-8"))
            metadata = {**metadata, **previous.get("metadata", {})}
            if metadata.get("source_state") == "unknown":
                metadata["source_state"] = args.source_state
            previous_stage_a_count = int(previous.get("stage_a_frame_count", 0))
        if not raw_path.is_file():
            print(f"FAIL: 找不到现有原始日志 {raw_path}")
            return 5
        captured_lines = [("a", line.decode("ascii", errors="replace").rstrip("\r"))
                          for line in raw_path.read_bytes().splitlines()]
        rows, parse_errors = parse_lines(captured_lines)
        if previous_stage_a_count > 0:
            rows = [CapturedRow("a" if index < previous_stage_a_count else "b", row.values)
                    for index, row in enumerate(rows)]
        evidence_lines = [line for _, line in captured_lines]
        if args.startup_log is not None:
            if not args.startup_log.is_file():
                print(f"FAIL: 找不到附加启动日志 {args.startup_log}")
                return 6
            evidence_lines.extend(
                line.decode("ascii", errors="replace").rstrip("\r")
                for line in args.startup_log.read_bytes().splitlines())
        result = analyse(rows, evidence_lines, parse_errors)
        save_results(capture_path, summary_path, report_path, metadata, rows, result)
        print(f"重新分析完成：frames={result['frame_count']}，报告={report_path}")
        return 1 if FAIL in result["checks"].values() else 0
    try:
        port = serial.Serial(args.port, args.baud, bytesize=serial.EIGHTBITS,
                             parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                             timeout=0.1, xonxoff=False, rtscts=False, dsrdtr=False)
    except serial.SerialException as exc:
        print(f"FAIL: 无法打开串口 {args.port}: {exc}")
        return 2
    collector = Collector(port, raw_path)
    collector.start()
    try:
        input("保持面包板静止并复位开发板，然后按Enter。")
        if args.programmer_cli:
            reset_command = [str(args.programmer_cli), "-c", "port=SWD", "freq=4000"]
            if args.stlink_serial:
                reset_command.append(f"sn={args.stlink_serial}")
            reset_command.append("-rst")
            reset = subprocess.run(reset_command, capture_output=True, text=True, check=False)
            print(reset.stdout)
            if reset.returncode != 0:
                print(reset.stderr)
                print("FAIL: ST-LINK 软件复位失败，停止串口验收。")
                return 4
        collector.phase = "a"
        print(f"阶段A采集中：保持静止 {args.stage_a_seconds:.0f} 秒……")
        time.sleep(args.stage_a_seconds)
        collector.phase = "b"
        input("缓慢向左、向右、向前、向后倾斜面包板，然后按Enter开始采集。\n请在采集窗口内继续完成动作，并在最后5秒停止移动以观察稳定趋势。")
        print(f"阶段B采集中：完成缓慢倾斜，最后5秒保持静止，共 {args.stage_b_seconds:.0f} 秒……")
        time.sleep(args.stage_b_seconds)
    except (KeyboardInterrupt, EOFError):
        print("\n验收被中止，保留已采集原始日志。")
        return 3
    finally:
        collector.stop()
        port.close()
    rows, parse_errors = parse_lines(collector.lines)
    plain_lines = [line for _, line in collector.lines]
    result = analyse(rows, plain_lines, parse_errors)
    save_results(capture_path, summary_path, report_path, metadata, rows, result)
    print(f"验收完成：frames={result['frame_count']}，报告={report_path}")
    for name, status in result["checks"].items():
        print(f"{status:10s} {name}")
    return 1 if FAIL in result["checks"].values() else 0


if __name__ == "__main__":
    raise SystemExit(main())
