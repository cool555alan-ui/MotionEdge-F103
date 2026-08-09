"""Generate auditable Phase 8 Markdown, JSON, CSV, and figures from real evidence."""

from __future__ import annotations
import csv
import json
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

from .attitude_metrics import descriptive,drift_metrics,noise_metrics,static_accuracy
from .experiment import atomic_json,read_rows


def _load(path:Path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else None


def _duration_s(rows:list[dict])->float:
    if len(rows)<2:return 0.0
    return (float(rows[-1]["device_timestamp_ms"])-float(rows[0]["device_timestamp_ms"]))/1000.0


def _status_static(metrics,reference):
    if not metrics or not metrics.get("count"):return "NOT_TESTED"
    if not reference or reference.get("uncertainty_deg") is None:return "REFERENCE_LIMITED"
    if reference["uncertainty_deg"]>.5:return "REFERENCE_LIMITED"
    if metrics["mae"]<=1.5 and metrics["max_abs_error"]<=3 and (metrics["fit"]["r_squared"] or 0)>=.995:return "PASS"
    if metrics["mae"]<=2.5 and metrics["max_abs_error"]<=5:return "WARN"
    return "FAIL"


def _status_noise(metrics,duration):
    if not metrics or duration<600:return "NOT_TESTED"
    std=max(metrics[a]["stddev"] for a in ("roll","pitch"));p2p=max(metrics[a]["peak_to_peak"] for a in ("roll","pitch"))
    return "PASS" if std<=.5 and p2p<=3 else "WARN" if std<=1 and p2p<=6 else "FAIL"


def _status_drift(metrics,duration):
    if not metrics or duration<1800:return "NOT_TESTED"
    drift=max(abs(metrics[a]["total_drift"]) for a in ("roll","pitch"));slope=max(abs(metrics[a]["slope_deg_per_min"]) for a in ("roll","pitch"))
    return "PASS" if drift<=2 and slope<=.1 else "WARN" if drift<=5 else "FAIL"


def _git_commit(root:Path)->str:
    result=subprocess.run(["git","rev-parse","HEAD"],cwd=root,text=True,capture_output=True,check=False)
    return result.stdout.strip() or "UNKNOWN"


def _figures(root:Path,out:Path,data:dict)->list[str]:
    import matplotlib;matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures=out/"figures";figures.mkdir(parents=True,exist_ok=True);created=[]
    def save(name):
        path=figures/name;plt.tight_layout();plt.savefig(path,dpi=140);plt.close();created.append(str(Path("figures")/name))
    static_rows={axis:read_rows(root/f"static-{axis}"/"static-used.csv") for axis in ("roll","pitch")}
    for axis,rows in static_rows.items():
        if not rows:continue
        target=[r["reference_deg"] for r in rows];measured=[r[f"{axis}_deg"] for r in rows]
        plt.figure();plt.scatter(target,measured,s=4,alpha=.3,label="samples");bounds=[min(target),max(target)];plt.plot(bounds,bounds,"k--",label="reference")
        plt.xlabel("Reference angle (deg)");plt.ylabel(f"Measured {axis} (deg)");plt.title(f"{axis.title()} reference vs measurement (reference limited)");plt.legend();save(f"static-{axis}-comparison.png")
        plt.figure();plt.scatter(target,[a-b for a,b in zip(measured,target)],s=4);plt.axhline(0,color="k",linestyle="--")
        plt.xlabel("Reference angle (deg)");plt.ylabel("Relative error (deg)");plt.title(f"{axis.title()} relative error");save(f"static-{axis}-error.png")
    if any(static_rows.values()):
        plt.figure()
        for axis,rows in static_rows.items():
            if rows:
                cross="pitch_deg" if axis=="roll" else "roll_deg"
                plt.scatter([r["reference_deg"] for r in rows],[r[cross] for r in rows],s=4,alpha=.25,label=f"{axis} test cross axis")
        plt.xlabel("Reference angle (deg)");plt.ylabel("Cross-axis angle (deg)");plt.title("Cross-axis coupling (fixture included)");plt.legend();save("cross-axis-coupling.png")
    noise_rows=data.get("noise_rows",[])
    if noise_rows:
        t=[(r["device_timestamp_ms"]-noise_rows[0]["device_timestamp_ms"])/1000 for r in noise_rows]
        plt.figure();plt.plot(t,[r["roll_deg"] for r in noise_rows],label="Roll");plt.plot(t,[r["pitch_deg"] for r in noise_rows],label="Pitch")
        plt.xlabel("Time (s)");plt.ylabel("Angle (deg)");plt.title("600-second calibrated stationary noise");plt.legend();save("stationary-noise-timeseries.png")
        plt.figure();plt.hist([r["roll_deg"] for r in noise_rows],bins=40,alpha=.6,label="Roll");plt.hist([r["pitch_deg"] for r in noise_rows],bins=40,alpha=.6,label="Pitch")
        plt.xlabel("Angle (deg)");plt.ylabel("Samples");plt.title("Stationary angle distribution");plt.legend();save("stationary-angle-histogram.png")
    drift_rows=read_rows(root/"long-drift"/"samples.csv")
    if drift_rows:
        t=[(r["device_timestamp_ms"]-drift_rows[0]["device_timestamp_ms"])/60000 for r in drift_rows]
        plt.figure();plt.plot(t,[r["roll_deg"] for r in drift_rows],label="Roll");plt.plot(t,[r["pitch_deg"] for r in drift_rows],label="Pitch")
        plt.xlabel("Time (min)");plt.ylabel("Angle (deg)");plt.title("30-minute calibrated stationary drift");plt.legend();save("long-drift.png")
    ranking=data.get("tuning") or []
    if ranking:
        plt.figure()
        for row in ranking:plt.scatter(row["noise_stddev"],row["dynamic_lag"],label=row["name"],s=55)
        plt.xlabel("Noise stddev (deg)");plt.ylabel("B-level relative lag (s)");plt.title("Measured noise-response trade-off");plt.legend();save("tuning-tradeoff.png")
        selected=ranking[0]
        plt.figure(figsize=(7,3));plt.bar(["alpha","gyro weight"],[selected["alpha"],selected["gyro_weight"]]);plt.ylim(0,1)
        plt.ylabel("Dimensionless value");plt.title(f"Selected configuration: {selected['name']} (unchanged)");save("current-vs-final-parameters.png")
    return created


def generate_phase08_report(root:Path,output:Path)->dict:
    output.mkdir(parents=True,exist_ok=True);repo=root.parent.parent
    reference=_load(root/"reference"/"reference-setup.json")
    static={};static_rows={};static_summaries={}
    for axis in ("roll","pitch"):
        rows=read_rows(root/f"static-{axis}"/"static-used.csv");static_rows[axis]=rows
        static[axis]=static_accuracy(rows,axis) if rows else None
        static_summaries[axis]=_load(root/f"static-{axis}"/"summary.json")
    captured_noise=read_rows(root/"static-noise"/"samples.csv")
    calibrated_noise=[row for row in captured_noise if row.get("calibrated")]
    drift_rows=read_rows(root/"long-drift"/"samples.csv")
    noise_rows=calibrated_noise;noise_source="static-noise calibrated rows"
    if _duration_s(noise_rows)<600 and _duration_s(drift_rows)>=600:
        start=float(drift_rows[0]["device_timestamp_ms"])
        noise_rows=[row for row in drift_rows if float(row["device_timestamp_ms"])-start<=600000]
        noise_source="first 600 seconds of fully calibrated 1800-second drift capture"
    noise=noise_metrics(noise_rows) if noise_rows else None;noise_duration=_duration_s(noise_rows)
    drift=drift_metrics(drift_rows) if drift_rows else None;drift_duration=_duration_s(drift_rows)
    dynamic=_load(root/"dynamic"/"summary.json")
    ranking=_load(root/"tuning"/"tuning-ranking.json") or []
    final_config=_load(root/"tuning"/"final-configuration.json")
    mqtt=_load(output/"mqtt-nodered-quick-regression.json")
    engineering_regression=_load(output/"regression-summary.json")
    drift_summary=_load(root/"long-drift"/"summary.json") or {}
    parser=(drift_summary.get("parser") or {})
    health_last=drift_summary.get("health_last") or {}
    stable_config=((drift_summary.get("metadata") or {}).get("config") or {})
    final_stability=(drift_duration>=600 and (drift or {}).get("sequence",{}).get("continuous") and
                     sum(int(parser.get(key,0)) for key in ("crc_errors","length_errors","version_errors"))==0 and
                     health_last.get("app_state_raw")==2 and health_last.get("sensor_state_raw")==2 and
                     final_config and stable_config.get("alpha_milli")==final_config.get("alpha_milli") and
                     stable_config.get("gyro_weight_milli")==final_config.get("gyro_weight_milli"))
    mqtt_ok=bool(mqtt) and all(value=="PASS" for value in (mqtt.get("checks") or {}).values())
    checks={
        "static_roll":_status_static(static["roll"],reference),"static_pitch":_status_static(static["pitch"],reference),
        "static_roll_completeness":"PASS" if (static_summaries["roll"] or {}).get("data_completeness",{}).get("complete",True) else "WARN",
        "static_pitch_completeness":"PASS" if (static_summaries["pitch"] or {}).get("data_completeness",{}).get("complete",True) else "WARN",
        "noise_600s":_status_noise(noise,noise_duration),"drift_1800s":_status_drift(drift,drift_duration),
        "dynamic_motion":"WARN" if dynamic and (dynamic.get("aggregate") or {}).get("motion_response")=="OBSERVED" else "NOT_TESTED",
        "dynamic_return_to_level":"NOT_TESTED" if dynamic and (dynamic.get("aggregate") or {}).get("recovery_response")=="NOT_TESTED" else "PASS",
        "tuning":"PASS" if len(ranking)==4 and final_config else "NOT_TESTED",
        "final_configuration_stability":"PASS" if final_stability else ("FAIL" if drift_rows and final_config else "NOT_TESTED"),
        "mqtt_node_red_quick_regression":"PASS" if mqtt_ok else ("FAIL" if mqtt else "NOT_TESTED"),
        "absolute_yaw":"NOT_APPLICABLE"
    }
    core=("static_roll","static_pitch","noise_600s","drift_1800s","dynamic_motion","tuning","final_configuration_stability","mqtt_node_red_quick_regression")
    core_values=[checks[key] for key in core]
    conclusion=("FAIL" if "FAIL" in core_values else "INCOMPLETE" if "NOT_TESTED" in core_values else
                "REFERENCE_LIMITED" if "REFERENCE_LIMITED" in core_values else "WARN" if "WARN" in core_values else "PASS")
    metadata_source=((drift_summary.get("metadata") or {}) if drift_summary else {})
    data={"result":conclusion,"environment":{"git_commit":_git_commit(repo),"firmware_version":metadata_source.get("firmware_version","0.6.0"),
          "motionctl_version":"0.8.0","mcu":"STM32F103C8T6","imu":"MPU6500","port":metadata_source.get("port","NOT_RECORDED"),
          "baud":metadata_source.get("baud",115200),"sensor_hz":100,"telemetry_hz":10,"configuration":stable_config},
          "reference":reference,"static":static,"static_experiment":{axis:(summary or {}).get("data_completeness") for axis,summary in static_summaries.items()},
          "noise":noise,"noise_source":noise_source,"noise_duration_s":noise_duration,"drift":drift,"drift_duration_s":drift_duration,
          "dynamic":dynamic,"tuning":ranking,"final_configuration":final_config,"mqtt_node_red":mqtt,
          "engineering_regression":engineering_regression,"checks":checks,
          "limits":["No magnetometer: absolute Yaw is unobservable.","Linear acceleration biases gravity tilt.",
          "Complementary filter is not inertial navigation.","Apple iPhone level reference uncertainty is unknown.",
          "No environmental-chamber temperature characterization.","Breadboard fixture and sensor mounting contribute cross-axis error.",
          "10 Hz filtered telemetry cannot support honest 100 Hz offline parameter replay."]}
    figure_data={**data,"noise_rows":noise_rows};data["figures"]=_figures(root,output,figure_data)
    atomic_json(output/"phase08-characterization-summary.json",data)
    with (output/"static-angle-results.csv").open("w",encoding="utf-8",newline="") as stream:
        fields=["axis","target_deg","repeat","mean_deg","bias_deg","stddev_deg","count"]
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for axis,rows in static_rows.items():
            groups=defaultdict(list)
            for row in rows:groups[(float(row["reference_deg"]),int(row["repeat"]))].append(float(row[f"{axis}_deg"]))
            for (target,repeat),values in sorted(groups.items()):
                writer.writerow({"axis":axis,"target_deg":target,"repeat":repeat,"mean_deg":statistics.fmean(values),
                                 "bias_deg":statistics.fmean(values)-target,"stddev_deg":descriptive(values)["stddev"],"count":len(values)})
    for filename,metrics in (("noise-results.csv",noise),("drift-results.csv",drift)):
        with (output/filename).open("w",encoding="utf-8",newline="") as stream:
            writer=csv.writer(stream);writer.writerow(["metric","json_value"])
            for key,value in (metrics or {}).items():writer.writerow([key,json.dumps(value,ensure_ascii=False)])
    with (output/"dynamic-results.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream);writer.writerow(["trial","angle_min","angle_max","range_deg","max_gyro_mdps","frames"])
        for trial in (dynamic or {}).get("trials",[]):writer.writerow([trial.get("trial"),trial.get("angle_min"),trial.get("angle_max"),
            (trial.get("angle_max")-trial.get("angle_min")) if trial.get("angle_max") is not None else None,trial.get("max_gyro_mdps"),trial.get("frames")])
    with (output/"tuning-ranking.csv").open("w",encoding="utf-8",newline="") as stream:
        fields=["rank","name","alpha","gyro_weight","total_score","static_mae","noise_stddev","peak_to_peak","dynamic_lag","overshoot","drift","cross_axis"]
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(ranking)
    lines=["# Phase 8 attitude characterization report","",f"- Conclusion: **{conclusion}**",
           f"- Commit tested: `{data['environment']['git_commit']}`","- Firmware: 0.6.0; motionctl: 0.8.0",
           "- Hardware: STM32F103C8T6 + MPU6500 (0x68, WHO_AM_I 0x70)",f"- Serial: {data['environment']['port']}, {data['environment']['baud']} 8N1",
           f"- Reference: Apple iPhone built-in level; uncertainty: REFERENCE_UNCERTAINTY_UNKNOWN",
           "- Claim boundary: engineering comparison only; no laboratory absolute-accuracy claim.","",
           "## Acceptance matrix","",*[f"- {key}: {value}" for key,value in checks.items()],"",
           "## Static accuracy","","```json",json.dumps(static,ensure_ascii=False,indent=2),"```","",
           "## Stationary noise","",f"Source: {noise_source}; duration {noise_duration:.1f} s.","```json",json.dumps(noise,ensure_ascii=False,indent=2),"```","",
           "## Long drift","",f"Duration: {drift_duration:.1f} s.","```json",json.dumps(drift,ensure_ascii=False,indent=2),"```","",
           "## Dynamic response","","B-level manual motion only; the user did not return to level in the first 10-trial set, so recovery and strict step-response metrics are NOT_TESTED.",
           "```json",json.dumps(dynamic,ensure_ascii=False,indent=2),"```","","## Parameter tuning","",
           "100 Hz offline replay was not performed because the existing protocol exposes only 10 Hz filtered telemetry. Four candidates were instead validated online with configuration read-back and restoration.",
           "```json",json.dumps({"ranking":ranking,"selected":final_config},ensure_ascii=False,indent=2),"```","",
           "## Data integrity","","```json",json.dumps({"final_stability":final_stability,"mqtt_node_red":mqtt},ensure_ascii=False,indent=2),"```","",
           "## Engineering regression","","```json",json.dumps(engineering_regression,ensure_ascii=False,indent=2),"```","",
           "## Known limitations","",*[f"- {item}" for item in data["limits"]]]
    (output/"phase08-characterization-report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return data
