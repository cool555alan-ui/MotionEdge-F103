"""离线 Markdown、JSON、CSV 与本地图表报告。"""

from __future__ import annotations

import csv
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from .capture import load_telemetry
from .errors import ReportError
from .metrics import motion_metrics
from .models import stable_dict
from .validation import validate_metrics


def generate_report(session: Path, output: Path) -> dict[str, object]:
    samples = load_telemetry(session)
    capture_path = session / "capture-summary.json"
    metadata_path = session / "session-metadata.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.is_file() else {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    requested = capture.get("requested_duration_s") or metadata.get("requested_duration_s")
    metrics = motion_metrics(samples, requested_duration_s=requested)
    parser = capture.get("parser", {})
    health_rows = capture.get("health", [])
    health_states = [row.get("app_state_raw") for row in health_rows if isinstance(row, dict)]
    fault_seen = 4 in health_states if health_states else metadata.get("fault_seen")
    degraded_persistent = bool(health_states) and all(state == 3 for state in health_states)
    validation = validate_metrics(metrics,
                                  identity_ok=bool(metadata.get("device_info")),
                                  ping_ok=metadata.get("ping_ok"),
                                  parser_errors=(parser.get("length_errors", 0) + parser.get("version_errors", 0)) if parser else None,
                                  crc_errors=parser.get("crc_errors") if parser else None,
                                  command_success_rate=metadata.get("command_success_rate"),
                                  fault_seen=fault_seen,
                                  degraded_persistent=(degraded_persistent if health_states
                                                       else metadata.get("degraded_persistent")))
    output.mkdir(parents=True, exist_ok=True)
    charts: list[str] = []
    if samples:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            t0 = samples[0].host_monotonic_ns or 0
            times = [((row.host_monotonic_ns or t0) - t0) / 1e9 for row in samples]
            figure, axis = plt.subplots(figsize=(10, 4.5))
            axis.plot(times, [row.roll_deg for row in samples], label="Roll")
            axis.plot(times, [row.pitch_deg for row in samples], label="Pitch")
            axis.set(title="Roll / Pitch vs Time", xlabel="Session time (s)", ylabel="Attitude (degree)")
            axis.grid(True); axis.legend(); figure.tight_layout()
            attitude = output / "attitude.png"; figure.savefig(attitude, dpi=140); plt.close(figure); charts.append(attitude.name)
            intervals = [(b.device_timestamp_ms - a.device_timestamp_ms) for a, b in zip(samples, samples[1:])]
            figure, axis = plt.subplots(figsize=(10, 4.5))
            axis.plot(times[1:], intervals)
            axis.set(title="Telemetry Interval vs Time", xlabel="Session time (s)", ylabel="Interval (ms)")
            axis.grid(True); figure.tight_layout()
            timing = output / "telemetry-timing.png"; figure.savefig(timing, dpi=140); plt.close(figure); charts.append(timing.name)
        except Exception as exc:
            capture["chart_warning"] = str(exc)
    result = {"report_time": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
              "host": {"python": platform.python_version(), "platform": platform.platform()},
              "metadata": metadata, "capture": capture, "metrics": metrics,
              "validation": stable_dict(validation), "charts": charts}
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "metrics.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n"); writer.writerow(("metric", "value"))
        def flatten(prefix, value):
            if isinstance(value, dict):
                for key, item in value.items(): yield from flatten(f"{prefix}.{key}" if prefix else key, item)
            else: yield prefix, value
        writer.writerows(flatten("", metrics))
    device = metadata.get("device_info") or {}
    config = metadata.get("initial_config") or {}
    lines = ["# MotionEdge Phase 6 自动报告", "", "## 会话信息", "",
             f"- 报告时间：{result['report_time']}", f"- Git提交：{metadata.get('git_commit', 'NOT_AVAILABLE')}",
             f"- 工具版本：{metadata.get('tool_version', 'NOT_AVAILABLE')}",
             f"- 串口：{metadata.get('port', 'NOT_AVAILABLE')} @ {metadata.get('baud', 'NOT_AVAILABLE')}",
             f"- 固件/协议：{device.get('firmware_version', 'NOT_AVAILABLE')} / {device.get('protocol_version', 'NOT_AVAILABLE')}",
             f"- MCU/IMU：{device.get('mcu_model') or 'NOT_AVAILABLE'} / {device.get('imu_model') or 'NOT_AVAILABLE'}", "",
             "## 设备配置", "", f"```json\n{json.dumps(config, ensure_ascii=False, indent=2)}\n```", "",
             "## 数据完整性", "", f"- 帧数：{metrics.get('frame_count', 0)}", f"- 频率：{metrics.get('frequency_hz')}",
             f"- 间隔：{metrics.get('interval_ms')}", f"- Sequence：{metrics.get('sequence')}", "",
             "## 姿态数据", "", f"- Roll：{metrics.get('roll_deg', 'NOT_TESTED')}", f"- Pitch：{metrics.get('pitch_deg', 'NOT_TESTED')}",
             f"- 加速度模长：{metrics.get('accel_magnitude_mg', 'NOT_TESTED')}", "", "## 系统健康", "",
             f"- Health：{capture.get('health', 'NOT_AVAILABLE')}", "", "## 命令性能", "",
             f"- {metadata.get('command_metrics', 'NOT_AVAILABLE')}", "", "## 验收矩阵", ""]
    lines.extend(f"- `{item.name}`：**{item.status}**；实际={item.actual}；阈值={item.threshold}；{item.reason}"
                 for item in validation.items)
    conclusion = ("Phase 6通过" if validation.conclusion == "PASS" else
                  "有警告但可继续" if validation.conclusion == "WARN" else
                  "信息不足" if validation.conclusion == "INFORMATION_INSUFFICIENT" else "必须修复")
    lines += ["", "## 结论", "", conclusion, "", "## 图表", ""] + [f"- [{name}]({name})" for name in charts]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
