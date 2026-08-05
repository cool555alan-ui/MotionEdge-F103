from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import paho.mqtt.client as mqtt

from motionctl.gateway_config import load_gateway_config
from motionctl.mqtt_models import json_bytes, utc_iso, utc_now
from motionctl.mqtt_topics import TopicSet

parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True)
args = parser.parse_args(); config = load_gateway_config(args.config)
root = Path(__file__).resolve().parents[1]; topics = TopicSet(config.gateway.device_id, config.gateway.gateway_id)
messages: list[tuple[float, str, bytes, bool]] = []; lock = threading.Lock(); connected = threading.Event()
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"phase07-integration-{uuid.uuid4()}")
def on_connect(c,u,f,rc,p):
    if getattr(rc,"value",rc)==0: c.subscribe("motionedge/v1/#", qos=1); connected.set()
def on_message(c,u,m):
    with lock: messages.append((time.monotonic(),m.topic,bytes(m.payload),bool(m.retain)))
client.on_connect=on_connect;client.on_message=on_message
client.connect(config.mqtt.host,config.mqtt.port,10);client.loop_start()
if not connected.wait(5): raise SystemExit("subscriber connect timeout")
creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
def start_gateway():
    return subprocess.Popen([sys.executable,str(root/"host"/"phase7_sim_gateway.py"),"--config",args.config,"--duration","120"],cwd=root,creationflags=creationflags)
def wait_for(predicate,timeout=10):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        with lock:
            if predicate(list(messages)): return True
        time.sleep(.05)
    return False
def payloads(topic):
    with lock: return [json.loads(p.decode()) for _,t,p,_ in messages if t==topic and p.startswith(b"{")]
# 清除前次中断测试可能遗留的retained命令，避免跨测试污染。
client.publish(topics.command,b"",qos=1,retain=True).wait_for_publish()
gateway=start_gateway()
try:
    assert wait_for(lambda rows:any(t==topics.gateway_availability and p==b"online" for _,t,p,_ in rows)),"online missing"
    assert wait_for(lambda rows:sum(t==topics.motion for _,t,_,_ in rows)>=10),"motion missing"
    now=utc_now();request_id=str(uuid.uuid4())
    cmd={"schema_version":1,"request_id":request_id,"command":"ping","issued_at":utc_iso(now),"expires_at":utc_iso(now+timedelta(seconds=30)),"params":{}}
    client.publish(topics.command,json_bytes(cmd),qos=1,retain=False)
    assert wait_for(lambda rows:any(t==topics.response and request_id.encode() in p for _,t,p,_ in rows)),"ping response missing"
    client.publish(topics.command,json_bytes(cmd),qos=1,retain=False)
    assert wait_for(lambda rows:sum(t==topics.response and request_id.encode() in p for _,t,p,_ in rows)>=2),"dedup response missing"
    old=utc_now()-timedelta(seconds=60);expired_id=str(uuid.uuid4())
    expired={"schema_version":1,"request_id":expired_id,"command":"get_status","issued_at":utc_iso(old),"expires_at":utc_iso(old+timedelta(seconds=1)),"params":{}}
    client.publish(topics.command,json_bytes(expired),qos=1,retain=False)
    assert wait_for(lambda rows:any(t==topics.response and b"COMMAND_EXPIRED" in p for _,t,p,_ in rows)),"expired rejection missing"
    gateway.terminate();gateway.wait(5)
    assert wait_for(lambda rows:any(t==topics.gateway_availability and p==b"offline" for _,t,p,_ in rows),5),"LWT offline missing"
    retained_id=str(uuid.uuid4());retained={"schema_version":1,"request_id":retained_id,"command":"start_calibration","issued_at":utc_iso(),"expires_at":utc_iso(utc_now()+timedelta(seconds=30)),"params":{}}
    client.publish(topics.command,json_bytes(retained),qos=1,retain=True).wait_for_publish()
    gateway=start_gateway()
    assert wait_for(lambda rows:any(t==topics.response and b"RETAINED_COMMAND_REJECTED" in p for _,t,p,_ in rows)),"retained rejection missing"
    client.publish(topics.command,b"",qos=1,retain=True).wait_for_publish()
    assert wait_for(lambda rows:sum(t==topics.gateway_availability and p==b"online" for _,t,p,_ in rows)>=2,10),"restart online missing"
    before=time.monotonic();subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(root/"tools"/"stop-phase07-broker.ps1")],cwd=root,check=True,creationflags=creationflags)
    time.sleep(5)
    subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(root/"tools"/"start-phase07-broker.ps1")],cwd=root,check=True,creationflags=creationflags)
    assert wait_for(lambda rows:sum(t==topics.gateway_availability and p==b"online" for _,t,p,_ in rows)>=3,15),"broker recovery online missing"
    recovery=time.monotonic()-before-5
    with lock: snapshot=list(messages)
    summary={"simulated":True,"result":"PASS","messages":len(snapshot),
             "motion":sum(t==topics.motion for _,t,_,_ in snapshot),
             "responses":sum(t==topics.response for _,t,_,_ in snapshot),
             "duplicate_response":True,"expired_rejected":True,"retained_rejected":True,
             "lwt_offline":True,"broker_recovery_s":recovery}
    out=root/"artifacts"/"phase07"/"integration-summary.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
finally:
    if gateway.poll() is None: gateway.terminate(); gateway.wait(5)
    client.disconnect();client.loop_stop()
