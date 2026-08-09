"""Phase 8 reference, static, noise, drift, and dynamic experiment orchestration."""

from __future__ import annotations
import csv
import json
import random
import statistics
import time
from dataclasses import asdict
from pathlib import Path

from . import __version__,commands
from .attitude_metrics import drift_metrics,noise_metrics,static_accuracy
from .commands import RuntimeConfig,decode_device_info
from .experiment import atomic_json,capture_rows,preserve_configuration,set_configuration,write_rows
from .tuning import measured_candidate_metrics

REFERENCE_TYPES={"1":"digital inclinometer","2":"fixed-angle fixture","3":"mechanical protractor",
                 "4":"phone inclinometer application","5":"other"}

def record_reference(output:Path)->dict:
    print("参考方式：1数字倾角仪 2固定角度治具 3机械量角器 4手机倾角应用 5其他")
    choice=input("请选择：").strip();kind=REFERENCE_TYPES.get(choice,choice or "other")
    resolution=input("标称分辨率（度，未知留空）：").strip()
    accuracy=input("已知精度/不确定度（±度，未知留空）：").strip()
    setup=input("固定方式：").strip();orientation=input("面包板方向与安装朝向：").strip()
    value={"reference_type":kind,"resolution_deg":float(resolution) if resolution else None,
           "uncertainty_deg":float(accuracy) if accuracy else None,
           "uncertainty_status":"KNOWN" if accuracy else "REFERENCE_UNCERTAINTY_UNKNOWN",
           "fixture":setup or "NOT_PROVIDED","board_orientation":orientation or "NOT_PROVIDED",
           "coordinate_convention":"X forward, Y right, Z up; Roll about X, Pitch about Y",
           "recorded_at":time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    atomic_json(output/value_path("reference-setup.json"),value);return value

def value_path(name:str)->Path:return Path(name)

def experiment_metadata(client,port:str,baud:int,kind:str,extra:dict)->dict:
    info=decode_device_info(client.request(commands.GET_DEVICE_INFO));config=RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
    return {"experiment":kind,"motionctl_version":__version__,"firmware_version":info.firmware_version,
            "protocol_version":info.protocol_version,"port":port,"baud":baud,"config":asdict(config),
            "created_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),**extra}

def static_experiment(client,output:Path,angles:list[float],repeats:int,settle_s:float,capture_s:float,axis:str,port:str,baud:int)->dict:
    if axis not in ("roll","pitch") or repeats<=0:raise ValueError("invalid static experiment")
    output.mkdir(parents=True,exist_ok=True);all_rows=[];segments=[]
    base=[0.0]+[value for magnitude in sorted({abs(value) for value in angles if value}) for value in (magnitude,-magnitude) if value in angles]
    orders=[]
    for repeat in range(repeats):
        order=list(base if repeat%2==0 else reversed(base));
        if repeat>=2:random.Random(8000+repeat).shuffle(order)
        orders.append(order)
    with preserve_configuration(client):
        for repeat,order in enumerate(orders,1):
            for target in order:
                input(f"请将{axis.upper()}固定到标称 {target:+.1f}°，稳定后按Enter：")
                typed=input("参考设备实际读数（直接Enter使用标称值）：").strip();reference=float(typed) if typed else target
                time.sleep(settle_s)
                rows,health,parser=capture_rows(client,capture_s,target_deg=target,reference_deg=reference,axis=axis,repeat=repeat,phase="static")
                discard_count=round(min(5.0,capture_s/4)*10);used=rows[discard_count:]
                all_rows.extend(used);segments.append({"repeat":repeat,"target_deg":target,"reference_deg":reference,
                    "captured":len(rows),"used":len(used),"mean":statistics.fmean(row[f"{axis}_deg"] for row in used) if used else None,
                    "parser":parser})
                write_rows(output/f"repeat-{repeat}-angle-{target:+g}-raw.csv",rows)
    write_rows(output/"static-used.csv",all_rows)
    result={"metadata":experiment_metadata(client,port,baud,f"static-{axis}",{"angles":angles,"repeats":repeats,"settle_s":settle_s,"capture_s":capture_s,"orders":orders}),
            "segments":segments,"metrics":static_accuracy(all_rows,axis)}
    atomic_json(output/"summary.json",result);return result

def continuous_experiment(client,output:Path,duration_s:float,kind:str,port:str,baud:int)->dict:
    output.mkdir(parents=True,exist_ok=True);input(f"请保持面包板水平静止，按Enter开始 {duration_s:.0f} 秒{kind}测试：")
    with preserve_configuration(client):rows,health,parser=capture_rows(client,duration_s,phase=kind)
    write_rows(output/"samples.csv",rows)
    metrics=noise_metrics(rows) if kind=="noise" else drift_metrics(rows)
    result={"metadata":experiment_metadata(client,port,baud,kind,{"duration_s":duration_s}),"metrics":metrics,
            "health_first":health[0] if health else None,"health_last":health[-1] if health else None,"parser":parser}
    atomic_json(output/"summary.json",result);return result

def coordinate_experiment(client,output:Path,port:str,baud:int)->dict:
    output.mkdir(parents=True,exist_ok=True)
    with preserve_configuration(client):
        input("水平放置面包板，确认X向前、Y向右、Z向上，然后按Enter：")
        baseline,_,_=capture_rows(client,5,phase="coordinate-baseline")
        input("保持前后不动，将面包板右侧明显抬高，然后按Enter：")
        right,_,_=capture_rows(client,5,phase="coordinate-right-raised")
        input("恢复水平，再将面包板前侧明显抬高，然后按Enter：")
        front,_,_=capture_rows(client,5,phase="coordinate-front-raised")
    def means(rows):return {axis:statistics.fmean(row[f"{axis}_deg"] for row in rows) for axis in ("roll","pitch")}
    base,right_mean,front_mean=means(baseline),means(right),means(front)
    result={"metadata":experiment_metadata(client,port,baud,"coordinate",{}),"baseline":base,"right_raised":right_mean,"front_raised":front_mean,
            "right_raised_delta":{"roll":right_mean["roll"]-base["roll"],"pitch":right_mean["pitch"]-base["pitch"]},
            "front_raised_delta":{"roll":front_mean["roll"]-base["roll"],"pitch":front_mean["pitch"]-base["pitch"]},
            "observed_roll_sign":"positive" if right_mean["roll"]>base["roll"] else "negative",
            "observed_pitch_sign":"positive" if front_mean["pitch"]>base["pitch"] else "negative"}
    write_rows(output/"coordinate-samples.csv",baseline+right+front);atomic_json(output/"summary.json",result);return result

def dynamic_experiment(client,output:Path,target_angle:float,trials:int,axis:str,port:str,baud:int)->dict:
    output.mkdir(parents=True,exist_ok=True);all_rows=[];trials_out=[]
    with preserve_configuration(client):
        for trial in range(1,trials+1):
            input(f"动态B级 第{trial}/{trials}次：水平开始，按Enter后人工转到 {target_angle:+g}°再回零：")
            rows,health,parser=capture_rows(client,8,target_deg=target_angle,axis=axis,repeat=trial,phase="dynamic")
            all_rows.extend(rows);values=[row[f"{axis}_deg"] for row in rows]
            gyros=[abs(row[f"g{'x' if axis=='roll' else 'y'}_mdps"]) for row in rows]
            trials_out.append({"trial":trial,"angle_min":min(values,default=None),"angle_max":max(values,default=None),
                               "max_gyro_mdps":max(gyros,default=None),"frames":len(rows),"parser":parser})
            write_rows(output/f"trial-{trial}-raw.csv",rows)
    result={"metadata":experiment_metadata(client,port,baud,"dynamic",{"level":"B_MANUAL","axis":axis,"target_angle":target_angle,"trials":trials,
             "limitation":"Manual motion duration is not algorithm response delay."}),"trials":trials_out}
    atomic_json(output/"summary.json",result);return result

def candidate_experiment(client,output:Path,name:str,alpha:float,gyro_weight:float,
                         static_s:float,port:str,baud:int)->dict:
    """在线验证一个参数候选，并在退出时恢复原配置。"""
    output.mkdir(parents=True,exist_ok=True)
    with preserve_configuration(client) as original:
        candidate=RuntimeConfig(**{**asdict(original),"alpha_milli":round(alpha*1000),
                                   "gyro_weight_milli":round(gyro_weight*1000)})
        confirmed=set_configuration(client,candidate)
        input(f"候选 {name}：保持水平静止，按 Enter 开始 {static_s:.0f} 秒噪声采集：")
        static_rows,static_health,static_parser=capture_rows(client,static_s,phase=f"candidate-{name}-static")
        input(f"候选 {name}：固定到 Roll +30 度，稳定后按 Enter：")
        time.sleep(5);plus_rows,_,plus_parser=capture_rows(client,10,target_deg=30,reference_deg=30,axis="roll",phase=f"candidate-{name}-plus30")
        input(f"候选 {name}：固定到 Roll -30 度，稳定后按 Enter：")
        time.sleep(5);minus_rows,_,minus_parser=capture_rows(client,10,target_deg=-30,reference_deg=-30,axis="roll",phase=f"candidate-{name}-minus30")
        input(f"候选 {name}：先回水平；按 Enter 后缓慢到 +30 度并务必回到水平：")
        dynamic_rows,_,dynamic_parser=capture_rows(client,12,target_deg=30,axis="roll",phase=f"candidate-{name}-dynamic")
        plus_used,minus_used=plus_rows[-50:],minus_rows[-50:]
        metrics=measured_candidate_metrics(static_rows,plus_used,minus_used,dynamic_rows)
        recovery_mean=statistics.fmean(row["roll_deg"] for row in dynamic_rows[-20:]) if len(dynamic_rows)>=20 else None
        result={"metadata":experiment_metadata(client,port,baud,"tuning-candidate",{
                    "name":name,"alpha":alpha,"gyro_weight":gyro_weight,"static_duration_s":static_s,
                    "dynamic_level":"B_MANUAL","offline_replay":"NOT_PERFORMED_10HZ_FILTERED_TELEMETRY_INSUFFICIENT"}),
                "confirmed_config":asdict(confirmed),"metrics":{"name":name,"alpha":alpha,"gyro_weight":gyro_weight,**metrics},
                "frames":{"static":len(static_rows),"plus30":len(plus_rows),"minus30":len(minus_rows),"dynamic":len(dynamic_rows)},
                "recovery":{"final_2s_roll_mean_deg":recovery_mean,"status":"PASS" if recovery_mean is not None and abs(recovery_mean)<=5 else "WARN"},
                "parsers":{"static":static_parser,"plus30":plus_parser,"minus30":minus_parser,"dynamic":dynamic_parser},
                "health_first":static_health[0] if static_health else None,"health_last":static_health[-1] if static_health else None}
        write_rows(output/"static-samples.csv",static_rows);write_rows(output/"plus30-samples.csv",plus_rows)
        write_rows(output/"minus30-samples.csv",minus_rows);write_rows(output/"dynamic-samples.csv",dynamic_rows)
        atomic_json(output/"summary.json",result)
    return result
