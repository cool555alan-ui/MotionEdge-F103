#!/usr/bin/env python3
"""MotionEdge Phase 5 FreeRTOS交互式实机验收。"""

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
from motionctl import commands
from motionctl.device import DeviceClient
from motionctl.transport import SerialTransport


TASK_NAMES = ("SensorTask", "CommunicationTask", "TelemetryTask", "HealthTask")


def run_command_checks(port: str, baud: int) -> dict[str, object]:
    results: dict[str, object] = {}
    client = DeviceClient(SerialTransport(port, baud), timeout=2.0)
    try:
        client.request(commands.PING)
        results["ping"] = base.PASS
        info = client.request(commands.GET_DEVICE_INFO)
        results["device_info"] = base.PASS if len(info) == 4 else base.FAIL
        status = client.request(commands.GET_STATUS)
        results["status"] = base.PASS if len(status) == 2 else base.FAIL
        config = commands.RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
        results["config"] = base.PASS
        motion = None
        for _ in range(20):
            try:
                motion = client.request(commands.GET_LATEST_MOTION)
                break
            except RuntimeError as exc:
                if "NOT_READY" not in str(exc):
                    raise
                time.sleep(0.25)
        results["latest_motion"] = base.PASS if motion is not None and len(motion) == 45 else base.FAIL
        client.request(commands.SET_STREAM_STATE, b"\x01")
        client.request(commands.SET_STREAM_STATE, b"\x00")
        results["stream_state"] = base.PASS
        results["firmware"] = f"{info[0]}.{info[1]}.{info[2]}" if len(info) == 4 else "unknown"
        results["app_state"] = status[0] if len(status) == 2 else None
        results["motion_state"] = status[1] if len(status) == 2 else None
        results["runtime_config"] = config.__dict__
    except (OSError, RuntimeError, ValueError, IndexError) as exc:
        results["error"] = str(exc)
        for name in ("ping", "device_info", "status", "config",
                     "latest_motion", "stream_state"):
            results.setdefault(name, base.FAIL)
    finally:
        client.transport.close()
    return results


def last_tuple(pattern: str, text: str, width: int) -> tuple[int, ...] | None:
    matches = re.findall(pattern, text)
    if not matches:
        return None
    values = matches[-1]
    if width == 1:
        values = (values,)
    return tuple(int(value) for value in values)


def analyse_rtos(rows: list[base.CapturedRow], captured_lines: list[tuple[str, str]],
                 parse_errors: int, command_results: dict[str, object],
                 elapsed_seconds: float) -> dict[str, object]:
    lines = [line for _, line in captured_lines]
    text = "\n".join(lines)
    result = base.analyse(rows, lines, parse_errors)
    kernel = last_tuple(r"\[INFO\]\[RTOS\] kernel=(\d+)", text, 1)
    run = last_tuple(r"\[INFO\]\[RTOS\].*?run=(\d+)/(\d+)/(\d+)/(\d+)", text, 4)
    heartbeat = last_tuple(r"\[INFO\]\[RTOS-HB\] hb=(\d+)/(\d+)/(\d+)/(\d+)", text, 4)
    miss = last_tuple(r"\[INFO\]\[RTOS-DEADLINE\] miss=(\d+)/(\d+)/(\d+)/(\d+)", text, 4)
    post_calibration_misses: tuple[int, ...] | None = None
    # 断线恢复会重新校准；稳定段的 deadline 必须从最后一次校准完成后计算。
    calibration_end = text.rfind("[INFO][CAL] complete")
    if calibration_end >= 0:
        stable_miss_rows = re.findall(
            r"\[INFO\]\[RTOS-DEADLINE\] miss=(\d+)/(\d+)/(\d+)/(\d+)",
            text[calibration_end:])
        if stable_miss_rows:
            first = tuple(int(value) for value in stable_miss_rows[0])
            last = tuple(int(value) for value in stable_miss_rows[-1])
            post_calibration_misses = tuple(end - start for start, end in zip(first, last))
    heap = last_tuple(r"\[INFO\]\[RTOS-DEADLINE\].*?heap=(\d+)/(\d+)", text, 2)
    stack_words = last_tuple(r"\[INFO\]\[RTOS-MEM\] stack_words=(\d+)/(\d+)/(\d+)/(\d+)", text, 4)
    stack_unit = last_tuple(r"\[INFO\]\[RTOS-MEM\].*? unit=(\d+)B", text, 1)
    stack = last_tuple(r"\[INFO\]\[RTOS-MEM-BYTES\] stack_bytes=(\d+)/(\d+)/(\d+)/(\d+)", text, 4)
    queue = last_tuple(r"\[INFO\]\[RTOS-IPC\].*?q=(\d+)/(\d+)/(\d+)", text, 3)
    mutex = last_tuple(r"\[INFO\]\[RTOS-IPC\].*?mutex=(\d+)/(\d+)/(\d+)", text, 3)
    failures = last_tuple(r"\[INFO\]\[RTOS-FAIL\] stack_overflow=(\d+) malloc_failure=(\d+)", text, 2)
    execution = last_tuple(r"\[INFO\]\[RTOS-TIME\] exec_us=(\d+)/(\d+)/(\d+)/(\d+)", text, 4)
    jitter = last_tuple(r"\[INFO\]\[RTOS-JITTER\] jitter_us=(\d+)/(\d+)/(\d+)/(\d+)", text, 4)
    comm = last_tuple(r"\[INFO\]\[RTOS-COMM\] rx=(\d+) crc=(\d+) parser=(\d+) command=(\d+) tx=(\d+)", text, 5)
    uptimes = [int(value) for value in re.findall(r"\buptime_ms=(\d+)", text)]
    observed_seconds = (uptimes[-1] / 1000.0) if uptimes else elapsed_seconds
    frequencies = ([count / observed_seconds for count in run]
                   if run and observed_seconds > 0 else None)
    phase_states: dict[str, list[str]] = {}
    for phase, line in captured_lines:
        states = re.findall(r"\bstate=(RUNNING|DEGRADED|FAULT)\b", line)
        if states:
            phase_states.setdefault(phase, []).extend(states)
    recovery_states = phase_states.get("recovery", []) + phase_states.get("soak", [])
    last_uncalibrated = max(
        (index for index, row in enumerate(rows) if row.values["calibrated"] == 0),
        default=-1)
    stable_rows = rows[last_uncalibrated + 1:]
    stable_continuity = base.continuity(stable_rows)
    checks = result["checks"]
    checks.update({
        "rtos_scheduler_started": base.PASS if kernel == (2,) and run else base.FAIL,
        "sensor_task_frequency": (base.NOT_TESTED if not frequencies else
                                   base.PASS if 95.0 <= frequencies[0] <= 105.0 else base.FAIL),
        "communication_task_frequency": (base.NOT_TESTED if not frequencies else
                                          base.PASS if 450.0 <= frequencies[1] <= 550.0 else base.WARN),
        "telemetry_task_frequency": (base.NOT_TESTED if not frequencies else
                                      base.PASS if 9.0 <= frequencies[2] <= 11.0 else base.FAIL),
        "health_task_frequency": (base.NOT_TESTED if not frequencies else
                                   base.PASS if 0.9 <= frequencies[3] <= 1.1 else base.FAIL),
        "command_ping": command_results.get("ping", base.NOT_TESTED),
        "command_device_info": command_results.get("device_info", base.NOT_TESTED),
        "command_status": command_results.get("status", base.NOT_TESTED),
        "command_config": command_results.get("config", base.NOT_TESTED),
        "command_latest_motion": command_results.get("latest_motion", base.NOT_TESTED),
        "command_stream_state": command_results.get("stream_state", base.NOT_TESTED),
        "task_stack_margin": (base.NOT_TESTED if not stack else
                              base.PASS if (min(stack[:3]) >= 256 and stack[3] >= 128)
                              else base.FAIL),
        "command_queue_not_full": (base.NOT_TESTED if not queue else
                                   base.PASS if queue[2] == 0 else base.FAIL),
        "mutex_no_timeout": (base.NOT_TESTED if not mutex else
                             base.PASS if mutex == (0, 0, 0) else base.FAIL),
        "critical_deadlines": (base.NOT_TESTED if post_calibration_misses is None else
                               base.PASS if sum(post_calibration_misses) == 0 else base.FAIL),
        "rtos_heap_observed": base.PASS if heap and heap[0] > 0 and heap[1] > 0 else base.FAIL,
        "communication_errors": (base.NOT_TESTED if not comm else
                                 base.PASS if sum(comm) == 0 else base.FAIL),
        "rtos_fatal_hooks": (base.NOT_TESTED if not failures else
                             base.PASS if failures == (0, 0) else base.FAIL),
        "sensor_disconnect_degraded": (base.PASS if "DEGRADED" in phase_states.get("disconnect", [])
                                       else base.FAIL),
        "sensor_reconnect_running": (base.PASS if "RUNNING" in recovery_states else base.FAIL),
        "sequence_continuity": (
            base.NOT_TESTED if not stable_rows else
            base.PASS if (stable_continuity["sequence_regressions"] == 0 and
                          stable_continuity["estimated_lost_frames"] == 0) else base.FAIL),
        "application_state": (
            base.FAIL if "FAULT" in result.get("health_states", []) else
            base.PASS if recovery_states and recovery_states[-1] == "RUNNING" else base.WARN),
        "ten_minute_runtime": (base.PASS if elapsed_seconds >= 600.0 and run and rows
                               else base.FAIL),
    })
    result.update({
        "rtos_run_counts": dict(zip(TASK_NAMES, run)) if run else None,
        "rtos_last_heartbeat_ms": dict(zip(TASK_NAMES, heartbeat)) if heartbeat else None,
        "rtos_frequencies_hz": dict(zip(TASK_NAMES, frequencies)) if frequencies else None,
        "deadline_miss_counts": dict(zip(TASK_NAMES, miss)) if miss else None,
        "post_calibration_deadline_miss_delta": (
            dict(zip(TASK_NAMES, post_calibration_misses))
            if post_calibration_misses is not None else None),
        "stack_high_water_bytes": dict(zip(TASK_NAMES, stack)) if stack else None,
        "stack_high_water_raw": dict(zip(TASK_NAMES, stack_words)) if stack_words else None,
        "stack_high_water_unit_bytes": stack_unit[0] if stack_unit else None,
        "max_execution_us_tick_resolution": dict(zip(TASK_NAMES, execution)) if execution else None,
        "max_jitter_us_tick_resolution": dict(zip(TASK_NAMES, jitter)) if jitter else None,
        "heap_bytes": {"free": heap[0], "minimum_ever_free": heap[1]} if heap else None,
        "command_queue": {"current": queue[0], "maximum": queue[1], "full_count": queue[2]} if queue else None,
        "mutex_timeouts": ({"uart": mutex[0], "snapshot": mutex[1], "logger": mutex[2]}
                           if mutex else None),
        "communication_counters": ({"rx_overflow": comm[0], "crc": comm[1],
                                     "parser": comm[2], "command": comm[3], "tx": comm[4]}
                                   if comm else None),
        "fatal_hook_counts": ({"stack_overflow": failures[0], "malloc_failure": failures[1]}
                              if failures else None),
        "command_results": command_results,
        "phase_states": phase_states,
        "elapsed_seconds": elapsed_seconds,
        "post_recovery_continuity": stable_continuity,
    })
    return result


def write_report(path: Path, metadata: dict[str, object], result: dict[str, object]) -> None:
    checks = result["checks"]
    ranges = result.get("stage_b_ranges", {})
    continuity = result["continuity"]
    accel = result["static_accel_magnitude_mg"]
    lines = [
        "# MotionEdge Phase 5 FreeRTOS实机验收报告", "",
        f"- 验证日期：{metadata['validation_date']}",
        f"- 固件提交/源码状态：`{metadata['commit']}` / {metadata['source_state']}",
        f"- 固件版本/配置：`{metadata['firmware_version']}` / Debug",
        f"- ST-LINK：{metadata['stlink']}",
        f"- 串口：`{metadata['port']}`，{metadata['baud']} 8N1，无流控",
        f"- 实际运行时间：{result['elapsed_seconds']:.1f} s", "",
        "## RTOS统计", "",
        f"- 任务运行次数：{result['rtos_run_counts']}",
        f"- 最后心跳（ms）：{result['rtos_last_heartbeat_ms']}",
        f"- 任务频率：{result['rtos_frequencies_hz']}",
        f"- 栈高水位原始值（Words）：{result['stack_high_water_raw']}；单位={result['stack_high_water_unit_bytes']} B/Word",
        f"- 最小剩余栈（Bytes）：{result['stack_high_water_bytes']}",
        f"- Deadline miss：{result['deadline_miss_counts']}",
        f"- 校准完成后Deadline miss增量：{result['post_calibration_deadline_miss_delta']}",
        f"- 最大执行时间/抖动（1 ms tick换算）：{result['max_execution_us_tick_resolution']} / {result['max_jitter_us_tick_resolution']}",
        f"- RTOS堆：{result['heap_bytes']}",
        f"- 命令队列：{result['command_queue']}",
        f"- 互斥锁超时：{result['mutex_timeouts']}",
        f"- 通信错误：{result['communication_counters']}",
        f"- 栈溢出/malloc失败：{result['fatal_hook_counts']}",
        f"- 命令结果：{result['command_results']}", "",
        "## 运动数据", "",
        f"- 有效帧：{result['frame_count']}；估算丢帧：{continuity['estimated_lost_frames']}；sequence回退/重复：{continuity['sequence_regressions']}",
        f"- 采样间隔：mean={continuity['mean_interval_ms']} ms，median={continuity['median_interval_ms']} ms",
        f"- 静止加速度模长：mean={accel['mean']} mg，range={accel['min']}..{accel['max']} mg",
        f"- Roll：{ranges.get('roll_cdeg', {}).get('min')}..{ranges.get('roll_cdeg', {}).get('max')} cdeg",
        f"- Pitch：{ranges.get('pitch_cdeg', {}).get('min')}..{ranges.get('pitch_cdeg', {}).get('max')} cdeg",
        f"- 掉线/恢复状态：{result['phase_states']}", "",
        "## 裸机资源对比", "",
        f"- 裸机/空RTOS基线：Flash {metadata['baseline_flash']} B，RAM {metadata['baseline_ram']} B",
        f"- Phase 5 Debug：Flash {metadata['debug_flash']} B，RAM {metadata['debug_ram']} B",
        f"- 增量：Flash {metadata['debug_flash'] - metadata['baseline_flash']:+d} B，RAM {metadata['debug_ram'] - metadata['baseline_ram']:+d} B", "",
        "## 分级结果", "",
    ]
    lines.extend(f"- `{name}`：**{status}**" for name, status in checks.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_task_stats(path: Path, captured_lines: list[tuple[str, str]]) -> None:
    """把每秒健康日志展开为逐任务CSV，保留API原值、单位和字节换算。"""
    samples: list[dict[str, object]] = []
    for phase, line in captured_lines:
        run = re.search(r"\[INFO\]\[RTOS\] kernel=(\d+) run=(\d+)/(\d+)/(\d+)/(\d+)", line)
        if run:
            values = [int(value) for value in run.groups()]
            samples.append({"phase": phase, "kernel": values[0], "run": values[1:5]})
            continue
        if not samples:
            continue
        heartbeat = re.search(r"\[INFO\]\[RTOS-HB\] hb=(\d+)/(\d+)/(\d+)/(\d+)", line)
        if heartbeat:
            samples[-1]["heartbeat"] = [int(value) for value in heartbeat.groups()]
        deadline = re.search(r"\[INFO\]\[RTOS-DEADLINE\] miss=(\d+)/(\d+)/(\d+)/(\d+)"
                             r" heap=(\d+)/(\d+)", line)
        if deadline:
            values = [int(value) for value in deadline.groups()]
            samples[-1].update({"miss": values[:4], "heap": values[4:6]})
        memory = re.search(r"\[INFO\]\[RTOS-MEM\] stack_words=(\d+)/(\d+)/(\d+)/(\d+)"
                           r" unit=(\d+)B", line)
        if memory:
            values = [int(value) for value in memory.groups()]
            samples[-1].update({"stack_words": values[:4], "unit": values[4]})
        memory_bytes = re.search(r"\[INFO\]\[RTOS-MEM-BYTES\] stack_bytes=(\d+)/(\d+)/(\d+)/(\d+)", line)
        if memory_bytes:
            samples[-1]["stack_bytes"] = [int(value) for value in memory_bytes.groups()]
        ipc = re.search(r"\[INFO\]\[RTOS-IPC\] q=(\d+)/(\d+)/(\d+)"
                        r" mutex=(\d+)/(\d+)/(\d+)", line)
        if ipc:
            samples[-1]["ipc"] = [int(value) for value in ipc.groups()] + [None, None]
        failures = re.search(r"\[INFO\]\[RTOS-FAIL\] stack_overflow=(\d+) malloc_failure=(\d+)", line)
        if failures:
            ipc = samples[-1].setdefault("ipc", [None] * 8)
            ipc[6:8] = [int(value) for value in failures.groups()]

    fields = ["sample", "phase", "task", "kernel_state", "run_count",
              "last_heartbeat_ms", "frequency_hz", "deadline_miss",
              "stack_high_water_raw", "raw_unit", "stack_unit_bytes",
              "stack_high_water_bytes", "free_heap_bytes", "minimum_ever_free_heap_bytes",
              "queue_current", "queue_maximum", "queue_full_count", "uart_mutex_timeouts",
              "snapshot_mutex_timeouts", "logger_mutex_timeouts", "stack_overflows",
              "malloc_failures"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for sample_index, sample in enumerate(samples, 1):
            for task_index, task_name in enumerate(TASK_NAMES):
                heartbeat = sample.get("heartbeat", [None] * 4)[task_index]
                run_count = sample["run"][task_index]
                ipc = sample.get("ipc", [None] * 8)
                writer.writerow({
                    "sample": sample_index, "phase": sample["phase"], "task": task_name,
                    "kernel_state": sample["kernel"], "run_count": run_count,
                    "last_heartbeat_ms": heartbeat,
                    "frequency_hz": (run_count * 1000.0 / heartbeat) if heartbeat else None,
                    "deadline_miss": sample.get("miss", [None] * 4)[task_index],
                    "stack_high_water_raw": sample.get("stack_words", [None] * 4)[task_index],
                    "raw_unit": "StackType_t words", "stack_unit_bytes": sample.get("unit"),
                    "stack_high_water_bytes": sample.get("stack_bytes", [None] * 4)[task_index],
                    "free_heap_bytes": sample.get("heap", [None, None])[0],
                    "minimum_ever_free_heap_bytes": sample.get("heap", [None, None])[1],
                    "queue_current": ipc[0], "queue_maximum": ipc[1], "queue_full_count": ipc[2],
                    "uart_mutex_timeouts": ipc[3], "snapshot_mutex_timeouts": ipc[4],
                    "logger_mutex_timeouts": ipc[5], "stack_overflows": ipc[6],
                    "malloc_failures": ipc[7],
                })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--duration-seconds", type=float, default=600.0)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/rtos-validation"))
    parser.add_argument("--programmer-cli", type=Path, required=True)
    parser.add_argument("--stlink-serial")
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--firmware-version", default="0.5.0")
    parser.add_argument("--source-state", default="working tree with uncommitted changes")
    parser.add_argument("--stlink", default="unknown")
    parser.add_argument("--baseline-flash", type=int, default=51448)
    parser.add_argument("--baseline-ram", type=int, default=10456)
    parser.add_argument("--debug-flash", type=int, required=True)
    parser.add_argument("--debug-ram", type=int, required=True)
    args = parser.parse_args()
    if args.duration_seconds < 600.0:
        parser.error("FreeRTOS实机验收不得少于600秒")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "serial-raw.log"
    capture_path = args.output_dir / "rtos-hardware-capture.csv"
    task_stats_path = args.output_dir / "rtos-task-stats.csv"
    summary_path = args.output_dir / "rtos-validation-summary.json"
    report_path = args.output_dir / "rtos-validation-report.md"

    print("先验证PING、状态和配置读取命令，请保持开发板已连接。")
    command_results = run_command_checks(args.port, args.baud)
    print(json.dumps(command_results, ensure_ascii=False, indent=2))
    try:
        port = serial.Serial(args.port, args.baud, timeout=0.1, xonxoff=False,
                             rtscts=False, dsrdtr=False)
    except serial.SerialException as exc:
        print(f"FAIL: 无法打开串口 {args.port}: {exc}")
        return 2
    collector = base.Collector(port, raw_path)
    collector.start()
    start = time.monotonic()
    try:
        input("保持面包板静止，按复位键，然后按Enter开始采集。")
        reset_command = [str(args.programmer_cli), "-c", "port=SWD", "freq=4000"]
        if args.stlink_serial:
            reset_command.append(f"sn={args.stlink_serial}")
        reset_command.append("-rst")
        reset = subprocess.run(reset_command, capture_output=True, text=True, check=False)
        print(reset.stdout)
        if reset.returncode != 0:
            print(reset.stderr)
            return 3
        collector.phase = "a"
        print("静止启动、扫描和校准采集60秒……")
        time.sleep(60.0)
        collector.phase = "b"
        input("缓慢向左、向右、向前、向后倾斜面包板，然后按Enter开始采集。")
        print("运动采集30秒，最后5秒请停止移动……")
        time.sleep(30.0)
        collector.phase = "disconnect"
        input("现在断开MPU6500的SDA或电源，按Enter继续。")
        time.sleep(10.0)
        collector.phase = "recovery"
        input("重新连接MPU6500并保持静止，按Enter继续。")
        time.sleep(20.0)
        collector.phase = "soak"
        print(f"恢复后继续稳定运行采集 {args.duration_seconds:.0f} 秒，请勿关闭终端……")
        time.sleep(args.duration_seconds)
    except (EOFError, KeyboardInterrupt):
        print("验收被中止，保留已有原始日志。")
        return 4
    finally:
        elapsed = time.monotonic() - start
        collector.stop()
        port.close()

    # 采集前串口若残留文本流可能使首次命令同步超时；采集结束后必须再次做真实命令回归。
    post_command_results = run_command_checks(args.port, args.baud)
    if all(post_command_results.get(name) == base.PASS for name in
           ("ping", "device_info", "status", "config", "latest_motion", "stream_state")):
        command_results = post_command_results

    rows, parse_errors = base.parse_lines(collector.lines)
    result = analyse_rtos(rows, collector.lines, parse_errors, command_results, elapsed)
    with capture_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(base.COLUMNS)
        for row in rows:
            writer.writerow(row.values[name] for name in base.COLUMNS)
    write_task_stats(task_stats_path, collector.lines)
    metadata = {
        "validation_date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "commit": args.commit, "firmware_version": args.firmware_version,
        "source_state": args.source_state, "stlink": args.stlink,
        "port": args.port, "baud": args.baud,
        "baseline_flash": args.baseline_flash, "baseline_ram": args.baseline_ram,
        "debug_flash": args.debug_flash, "debug_ram": args.debug_ram,
    }
    summary_path.write_text(json.dumps({"metadata": metadata, **result}, ensure_ascii=False,
                                       indent=2) + "\n", encoding="utf-8")
    write_report(report_path, metadata, result)
    print(f"验收完成：{elapsed:.1f}s，frames={len(rows)}，报告={report_path}")
    for name, status in result["checks"].items():
        print(f"{status:10s} {name}")
    return 1 if base.FAIL in result["checks"].values() else 0


if __name__ == "__main__":
    raise SystemExit(main())
