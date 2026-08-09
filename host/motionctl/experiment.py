"""Real-device Phase 8 experiment primitives with atomic evidence and config restoration."""

from __future__ import annotations
import csv
import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from . import commands
from .commands import RuntimeConfig,decode_health,decode_motion

SAMPLE_FIELDS=("host_monotonic_ns","device_timestamp_ms","sample_sequence","status_flags","calibrated",
               "ax_mg","ay_mg","az_mg","gx_mdps","gy_mdps","gz_mdps","roll_deg","pitch_deg",
               "target_deg","reference_deg","axis","repeat","phase","disturbed")

def read_configuration(client)->RuntimeConfig:
    """读取运行配置；连续超时后重开串口一次，清除USB-UART瞬态堵塞。"""
    try:
        return RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
    except Exception as first_error:
        transport=getattr(client,"transport",None)
        if transport is None or not hasattr(transport,"close") or not hasattr(transport,"open"):
            raise
        try:
            transport.close();time.sleep(0.2);transport.open();client.flush_input()
            return RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
        except Exception as recovery_error:
            raise RuntimeError("unable to read configuration after serial reconnect") from recovery_error

def atomic_json(path:Path,value)->None:
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+".tmp")
    with temporary.open("w",encoding="utf-8") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.write("\n");stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)

@contextmanager
def preserve_configuration(client):
    original=read_configuration(client)
    try:yield original
    finally:
        current=read_configuration(client)
        if current!=original:
            set_configuration(client,original)
        confirmed=read_configuration(client)
        if confirmed!=original:raise RuntimeError("original device configuration was not restored")

def set_configuration(client,config:RuntimeConfig)->RuntimeConfig:
    if not config.validate():raise ValueError("invalid runtime configuration")
    try:client.request(commands.SET_CONFIG,config.pack(),retry=False)
    except Exception:
        pass
    confirmed=read_configuration(client)
    if confirmed!=config:
        client.request(commands.SET_CONFIG,config.pack(),retry=False)
        confirmed=read_configuration(client)
    if confirmed!=config:raise RuntimeError("device configuration read-back mismatch")
    return confirmed

def ensure_stream_state(client,enabled:bool)->RuntimeConfig:
    """Issue once, then read back; repeat only when read-back proves it was not applied."""
    current=read_configuration(client)
    if current.telemetry_enabled==enabled:return current
    try:client.request(commands.SET_STREAM_STATE,bytes((int(enabled),)),retry=False)
    except Exception:
        pass
    confirmed=read_configuration(client)
    if confirmed.telemetry_enabled!=enabled:
        client.request(commands.SET_STREAM_STATE,bytes((int(enabled),)),retry=False)
        confirmed=read_configuration(client)
    if confirmed.telemetry_enabled!=enabled:raise RuntimeError("device stream state read-back mismatch")
    return confirmed

def capture_rows(client,duration_s:float,*,target_deg:float|None=None,reference_deg:float|None=None,
                 axis:str="none",repeat:int=0,phase:str="capture",disturbed:bool=False,
                 progress:bool=True)->tuple[list[dict],list[dict],dict]:
    if duration_s<=0:raise ValueError("duration must be positive")
    original=read_configuration(client)
    if not original.telemetry_enabled:ensure_stream_state(client,True)
    client.flush_input();rows=[];health=[];started=time.monotonic();last_print=0.0
    try:
        while time.monotonic()-started<duration_s:
            for frame in client.poll():
                host_ns=time.monotonic_ns()
                if frame.type==commands.MOTION_TELEMETRY:
                    sample=decode_motion(frame.payload,host_ns)
                    row=asdict(sample);row.update(target_deg=target_deg,reference_deg=reference_deg,
                                                  axis=axis,repeat=repeat,phase=phase,disturbed=disturbed)
                    rows.append(row)
                elif frame.type==commands.HEALTH_TELEMETRY:health.append(asdict(decode_health(frame.payload,host_ns)))
            elapsed=time.monotonic()-started
            if progress and elapsed-last_print>=1:
                latest=rows[-1] if rows else None
                suffix="" if latest is None else f" roll={latest['roll_deg']:7.2f} pitch={latest['pitch_deg']:7.2f}"
                print(f"\r{elapsed:7.1f}/{duration_s:.1f}s{suffix}",end="",flush=True);last_print=elapsed
    finally:
        if not original.telemetry_enabled:ensure_stream_state(client,False)
        if progress:print()
    parser={"frames":client.parser.frames,"crc_errors":client.parser.crc_errors,
            "length_errors":client.parser.length_errors,"version_errors":client.parser.version_errors,
            "discarded_bytes":client.parser.discarded_bytes}
    return rows,health,parser

def write_rows(path:Path,rows:list[dict])->None:
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+".tmp")
    with temporary.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=SAMPLE_FIELDS,extrasaction="ignore",lineterminator="\n")
        writer.writeheader();writer.writerows(rows);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)

def read_rows(path:Path)->list[dict]:
    if not path.is_file():return []
    rows=[]
    with path.open("r",encoding="utf-8",newline="") as stream:
        for row in csv.DictReader(stream):
            converted=dict(row)
            for key in ("host_monotonic_ns","device_timestamp_ms","sample_sequence","status_flags","ax_mg","ay_mg","az_mg","gx_mdps","gy_mdps","gz_mdps","repeat"):
                converted[key]=int(row[key])
            for key in ("roll_deg","pitch_deg"):
                converted[key]=float(row[key])
            for key in ("target_deg","reference_deg"):
                converted[key]=None if row[key] in ("","None") else float(row[key])
            converted["calibrated"]=row["calibrated"].lower() in ("true","1")
            converted["disturbed"]=row["disturbed"].lower() in ("true","1")
            rows.append(converted)
    return rows
