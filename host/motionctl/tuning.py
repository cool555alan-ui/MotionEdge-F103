"""Pure, transparent multi-objective ranking for measured parameter candidates."""

from __future__ import annotations
import math
import statistics
from typing import Mapping,Sequence

from .attitude_metrics import noise_metrics,regression
from .tuning_profiles import SCORE_WEIGHTS

METRIC_KEYS=tuple(SCORE_WEIGHTS)

def measured_candidate_metrics(static_rows:Sequence[Mapping[str,float]],
                               plus_rows:Sequence[Mapping[str,float]],
                               minus_rows:Sequence[Mapping[str,float]],
                               dynamic_rows:Sequence[Mapping[str,float]])->dict[str,float]:
    """从同一候选的实测片段生成透明评分指标；动态时延仅为B级相对指标。"""
    if not static_rows or not plus_rows or not minus_rows or not dynamic_rows:
        raise ValueError("candidate metrics require all measured segments")
    noise=noise_metrics(static_rows)
    plus=statistics.fmean(float(row["roll_deg"]) for row in plus_rows)
    minus=statistics.fmean(float(row["roll_deg"]) for row in minus_rows)
    cross_plus=statistics.fmean(float(row["pitch_deg"]) for row in plus_rows)
    cross_minus=statistics.fmean(float(row["pitch_deg"]) for row in minus_rows)
    static_mae=(abs(plus-30.0)+abs(minus+30.0))/2.0
    times=[float(row["device_timestamp_ms"]) for row in dynamic_rows]
    angles=[float(row["roll_deg"]) for row in dynamic_rows]
    gyro=[abs(float(row["gx_mdps"])) for row in dynamic_rows]
    baseline=statistics.fmean(angles[:min(5,len(angles))])
    deviations=[abs(value-baseline) for value in angles]
    peak_index=max(range(len(deviations)),key=deviations.__getitem__)
    threshold=max(5000.0,max(gyro)*0.15)
    onset=next((index for index,value in enumerate(gyro[:peak_index+1]) if value>=threshold),0)
    lag=max(0.0,(times[peak_index]-times[onset])/1000.0)
    time_min=[(value-times[0])/60000.0 for value in times[:len(static_rows)]]
    static_times=[(float(row["device_timestamp_ms"])-float(static_rows[0]["device_timestamp_ms"]))/60000.0 for row in static_rows]
    slopes=[abs(float(regression(static_times,[float(row[f"{axis}_deg"]) for row in static_rows])["slope"] or 0.0)) for axis in ("roll","pitch")]
    return {"static_mae":static_mae,
            "noise_stddev":max(float(noise[axis]["stddev"]) for axis in ("roll","pitch")),
            "peak_to_peak":max(float(noise[axis]["peak_to_peak"]) for axis in ("roll","pitch")),
            "dynamic_lag":lag,"overshoot":max(0.0,max(deviations)-30.0),
            "drift":max(slopes),"cross_axis":abs(cross_plus-cross_minus)/6.0}

def score_candidates(candidates:list[dict],weights:dict[str,float]|None=None)->list[dict]:
    weights=weights or SCORE_WEIGHTS
    if not candidates:return []
    if abs(sum(weights.values())-1.0)>1e-9:raise ValueError("weights must sum to one")
    for row in candidates:
        for key in weights:
            value=float(row[key])
            if not math.isfinite(value) or value<0:raise ValueError(f"invalid tuning metric {key}")
    maxima={key:max(float(row[key]) for row in candidates) for key in weights}
    minima={key:min(float(row[key]) for row in candidates) for key in weights}
    ranked=[]
    for row in candidates:
        components={}
        for key,weight in weights.items():
            span=maxima[key]-minima[key]
            normalized=0.0 if span==0 else (float(row[key])-minima[key])/span
            components[key]=normalized*weight
        ranked.append({**row,"score_components":components,"total_score":sum(components.values())})
    ranked.sort(key=lambda row:(row["total_score"],row.get("alpha",0),row.get("gyro_weight",0)))
    for index,row in enumerate(ranked,1):row["rank"]=index
    return ranked
