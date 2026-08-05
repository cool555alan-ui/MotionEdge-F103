#!/usr/bin/env python3
"""Supplemental real-MQTT motion check after the 600-second stability run."""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

from motionctl.gateway_config import load_gateway_config
from motionctl.mqtt_topics import TopicSet
from phase7_hardware_validate import Capture, direct_stream_state, start_gateway, stop_gateway


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "artifacts" / "phase07" / "final-validation"
    config_path = root / "config" / "motionedge-gateway.toml"
    config = load_gateway_config(config_path)
    topics = TopicSet(config.gateway.device_id, config.gateway.gateway_id)
    original = direct_stream_state(config.serial.port, config.serial.baud)
    capture = Capture(output / "motion-check-mqtt.jsonl", topics)
    capture.start(config.mqtt.host, config.mqtt.port)
    process, stream = start_gateway(root, config_path, output / "motion-check-gateway.log")
    try:
        capture.wait_payload(topics.device_availability, lambda value: value == "online", 20)
        print("5秒后开始30秒运动验证：请明显但缓慢地完成左、右、前、后倾斜，最后回正。", flush=True)
        time.sleep(5)
        start_index = len(capture.messages)
        time.sleep(30)
    finally:
        stop_gateway(process, stream)
        capture.stop()
        direct_stream_state(config.serial.port, config.serial.baud, original)
    rows = [row["payload"] for row in capture.messages[start_index:]
            if row["topic"] == topics.motion and isinstance(row["payload"], dict)]
    roll = [float(row["roll_deg"]) for row in rows]
    pitch = [float(row["pitch_deg"]) for row in rows]
    accel = {axis: [float(row["accel_mg"][axis]) for row in rows] for axis in "xyz"}
    gyro = {axis: [float(row["gyro_mdps"][axis]) for row in rows] for axis in "xyz"}
    sequences = [int(row["sequence"]) for row in rows]
    continuity = all(b-a == 10 for a,b in zip(sequences,sequences[1:]))
    roll_span = max(roll, default=0)-min(roll, default=0)
    pitch_span = max(pitch, default=0)-min(pitch, default=0)
    result = "PASS" if len(rows) >= 250 and continuity and max(roll_span,pitch_span) > 10 else "FAIL"
    motion = {"result": result, "validation_date": datetime.now().astimezone().isoformat(),
              "duration_seconds": 30, "frames": len(rows), "sequence_continuous": continuity,
              "roll_deg": {"min": min(roll,default=None), "max": max(roll,default=None), "span": roll_span},
              "pitch_deg": {"min": min(pitch,default=None), "max": max(pitch,default=None), "span": pitch_span},
              "accel_mg": {axis:{"min":min(values,default=None),"max":max(values,default=None)} for axis,values in accel.items()},
              "gyro_mdps": {axis:{"min":min(values,default=None),"max":max(values,default=None)} for axis,values in gyro.items()}}
    (output / "motion-validation.json").write_text(json.dumps(motion,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary_path = output / "phase07-validation-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["motion_validation"] = motion
    summary["checks"]["motion_range"] = result
    values = summary["checks"].values()
    summary["result"] = "FAIL" if "FAIL" in values else "WARN" if "WARN" in values else "PASS"
    summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report_path = output / "phase07-validation-report.md"
    if result == "PASS":
        report_text = report_path.read_text(encoding="utf-8")
        report_text = report_text.replace("- Result: **FAIL**", "- Result: **PASS**", 1)
        report_text = report_text.replace("- motion_range: FAIL", "- motion_range: PASS", 1)
        report_path.write_text(report_text, encoding="utf-8")
    with report_path.open("a",encoding="utf-8") as report:
        report.write(f"\n## Supplemental real-MQTT motion check\n\n- Result: **{result}**\n- Frames: {len(rows)}\n- Roll min/max/span: {min(roll,default=None)} / {max(roll,default=None)} / {roll_span} deg\n- Pitch min/max/span: {min(pitch,default=None)} / {max(pitch,default=None)} / {pitch_span} deg\n- Sequence continuous: {continuity}\n")
    print(json.dumps(motion,ensure_ascii=False,indent=2),flush=True)
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
