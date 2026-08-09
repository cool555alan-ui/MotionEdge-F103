"""Pure Phase 8 attitude characterization statistics; no serial dependency."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Iterable, Mapping, Sequence


def finite(values: Iterable[float]) -> list[float]:
    result = [float(value) for value in values]
    if any(not math.isfinite(value) for value in result):
        raise ValueError("NaN or Inf in measurement data")
    return result


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(finite(values))
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper-position) + ordered[upper] * (position-lower)


def descriptive(values: Iterable[float]) -> dict[str, float | int | None]:
    data = finite(values)
    if not data:
        return {key: None for key in ("mean", "stddev", "min", "max", "peak_to_peak",
                                      "median", "mad", "p2_5", "p97_5") } | {"count": 0}
    mean = statistics.fmean(data)
    median = statistics.median(data)
    return {"count": len(data), "mean": mean,
            "stddev": statistics.stdev(data) if len(data) > 1 else 0.0,
            "min": min(data), "max": max(data), "peak_to_peak": max(data)-min(data),
            "median": median, "mad": statistics.median(abs(value-median) for value in data),
            "p2_5": percentile(data, .025), "p97_5": percentile(data, .975)}


def regression(x_values: Iterable[float], y_values: Iterable[float]) -> dict[str, float | None]:
    x, y = finite(x_values), finite(y_values)
    if len(x) != len(y) or len(x) < 2:
        return {"slope": None, "intercept": None, "r_squared": None}
    x_mean, y_mean = statistics.fmean(x), statistics.fmean(y)
    denominator = sum((value-x_mean)**2 for value in x)
    if denominator == 0:
        return {"slope": None, "intercept": y_mean, "r_squared": None}
    slope = sum((a-x_mean)*(b-y_mean) for a,b in zip(x,y))/denominator
    intercept = y_mean-slope*x_mean
    residual = sum((b-(slope*a+intercept))**2 for a,b in zip(x,y))
    total = sum((b-y_mean)**2 for b in y)
    return {"slope": slope, "intercept": intercept,
            "r_squared": 1.0-residual/total if total else 1.0}


def static_accuracy(rows: Sequence[Mapping[str, float]], axis: str) -> dict:
    if axis not in ("roll", "pitch"):
        raise ValueError("axis must be roll or pitch")
    measured_key, cross_key = f"{axis}_deg", "pitch_deg" if axis == "roll" else "roll_deg"
    valid = [row for row in rows if row.get("reference_deg") is not None]
    if not valid:
        return {"count": 0, "status": "NOT_TESTED"}
    measured = finite(row[measured_key] for row in valid)
    reference = finite(row["reference_deg"] for row in valid)
    errors = [value-target for value,target in zip(measured,reference)]
    groups: dict[tuple[float,int], list[float]] = defaultdict(list)
    angle_means: dict[float,list[float]] = defaultdict(list)
    cross_means: dict[float,list[float]] = defaultdict(list)
    for row in valid:
        target = float(row["target_deg"]); repeat = int(row.get("repeat",0))
        groups[(target,repeat)].append(float(row[measured_key]))
        angle_means[target].append(float(row[measured_key]))
        cross_means[target].append(float(row[cross_key]))
    segment_means = {key:statistics.fmean(values) for key,values in groups.items()}
    repeat_std = []
    for target in sorted({key[0] for key in segment_means}):
        values = [mean for (angle,_),mean in segment_means.items() if angle == target]
        if len(values)>1: repeat_std.append(statistics.stdev(values))
    hysteresis=[]
    for target in angle_means:
        values=[mean for (angle,_),mean in segment_means.items() if angle==target]
        if len(values)>1: hysteresis.append(max(values)-min(values))
    zero_values=angle_means.get(0.0,[])
    cross_x=sorted(cross_means)
    cross_y=[statistics.fmean(cross_means[target]) for target in cross_x]
    cross_fit=regression(cross_x,cross_y)
    error_stats=descriptive(errors)
    return {"count":len(valid), "mae":statistics.fmean(abs(value) for value in errors),
            "rmse":math.sqrt(statistics.fmean(value*value for value in errors)),
            "max_abs_error":max(abs(value) for value in errors),
            "bias":statistics.fmean(errors), "error":error_stats,
            "measurement":descriptive(measured), "fit":regression(reference,measured),
            "repeatability_stddev":statistics.fmean(repeat_std) if repeat_std else 0.0,
            "hysteresis_max":max(hysteresis,default=0.0),
            "return_to_zero_error":abs(statistics.fmean(zero_values)) if zero_values else None,
            "cross_axis_deg_per_10deg": (cross_fit["slope"]*10.0 if cross_fit["slope"] is not None else None),
            "cross_axis_peak_to_peak": max(cross_y)-min(cross_y) if cross_y else None}


def sequence_metrics(sequences: Iterable[int], expected_step: int = 10) -> dict[str,int|bool]:
    data=list(sequences); differences=[b-a for a,b in zip(data,data[1:])]
    return {"count":len(data), "duplicates":sum(value==0 for value in differences),
            "regressions":sum(value<0 for value in differences),
            "gaps":sum(value>0 and value!=expected_step for value in differences),
            "continuous":all(value==expected_step for value in differences)}


def noise_metrics(rows: Sequence[Mapping[str,float]]) -> dict:
    if not rows: return {"count":0,"status":"NOT_TESTED"}
    result={axis:descriptive(row[f"{axis}_deg"] for row in rows) for axis in ("roll","pitch")}
    for axis in ("roll","pitch"):
        mean=result[axis]["mean"]
        deviations=[abs(float(row[f"{axis}_deg"])-mean) for row in rows]
        result[axis]["p95_absolute_deviation"]=percentile(deviations,.95)
        values=[float(row[f"{axis}_deg"]) for row in rows]
        result[axis]["max_instantaneous_jump"]=max((abs(b-a) for a,b in zip(values,values[1:])),default=0.0)
    magnitudes=[math.sqrt(sum(float(row[f"a{axis}_mg"])**2 for axis in "xyz")) for row in rows]
    result["accel_magnitude_mg"]=descriptive(magnitudes)
    result["gyro_mdps"]={axis:descriptive(row[f"g{axis}_mdps"] for row in rows) for axis in "xyz"}
    result["sequence"]=sequence_metrics(int(row["sample_sequence"]) for row in rows)
    result["count"]=len(rows)
    return result


def drift_metrics(rows: Sequence[Mapping[str,float]], warmup_s: float = 60.0) -> dict:
    if not rows:return {"count":0,"status":"NOT_TESTED"}
    start=float(rows[0]["device_timestamp_ms"]); usable=[row for row in rows if (float(row["device_timestamp_ms"])-start)/1000>=warmup_s]
    if len(usable)<2:return {"count":len(rows),"status":"NOT_TESTED"}
    time_min=[(float(row["device_timestamp_ms"])-float(usable[0]["device_timestamp_ms"]))/60000 for row in usable]
    result={"count":len(rows),"warmup_samples":len(rows)-len(usable),"sequence":sequence_metrics(int(row["sample_sequence"]) for row in rows)}
    for axis in ("roll","pitch"):
        values=[float(row[f"{axis}_deg"]) for row in usable]
        window=max(1,min(len(values),round(60*len(values)/max(1,(float(usable[-1]["device_timestamp_ms"])-float(usable[0]["device_timestamp_ms"]))/1000))))
        first=statistics.fmean(values[:window]);last=statistics.fmean(values[-window:])
        fit=regression(time_min,values)
        result[axis]={"initial_60s_mean":first,"final_60s_mean":last,"total_drift":last-first,
                      "max_deviation":max(abs(value-first) for value in values),"slope_deg_per_min":fit["slope"]}
    result["five_minute_windows"]=[]
    for index in range(0,max(1,math.ceil(max(time_min,default=0)/5))):
        selected=[row for row,t in zip(usable,time_min) if index*5<=t<(index+1)*5]
        if selected:
            result["five_minute_windows"].append({"start_min":index*5,
                "roll_mean":statistics.fmean(float(row["roll_deg"]) for row in selected),
                "pitch_mean":statistics.fmean(float(row["pitch_deg"]) for row in selected)})
    magnitudes=[math.sqrt(sum(float(row[f"a{axis}_mg"])**2 for axis in "xyz")) for row in usable]
    result["accel_magnitude_mg"]=descriptive(magnitudes)
    result["gyro_mdps"]={axis:descriptive(float(row[f"g{axis}_mdps"]) for row in usable) for axis in "xyz"}
    result["temperature"]="NOT_AVAILABLE_IN_PROTOCOL"
    return result
