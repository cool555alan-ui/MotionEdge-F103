"""motionctl gateway子命令。"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import __version__, commands
from .commands import decode_device_info, decode_status
from .device import DeviceClient
from .errors import EXIT_RUNTIME, EXIT_SUCCESS
from .gateway import Gateway
from .gateway_config import load_gateway_config
from .mqtt_topics import TopicSet
from .transport import SerialTransport


def add_gateway_parser(subs) -> None:
    root = subs.add_parser("gateway", help="MQTT边缘网关")
    children = root.add_subparsers(dest="gateway_command", required=True)
    doctor = children.add_parser("doctor")
    doctor.add_argument("--port", required=True); doctor.add_argument("--baud", type=int, default=115200)
    doctor.add_argument("--broker", default="127.0.0.1"); doctor.add_argument("--mqtt-port", type=int, default=1884)
    doctor.add_argument("--node-red-url", default="http://127.0.0.1:1880")
    run = children.add_parser("run"); run.add_argument("--config", type=Path, required=True)
    run.add_argument("--duration", type=float)
    status = children.add_parser("status"); status.add_argument("--config", type=Path, required=True)
    validate = children.add_parser("validate"); validate.add_argument("--config", type=Path, required=True)
    validate.add_argument("--duration", type=float, default=30.0)


def _mqtt_round_trip(host: str, port: int, timeout: float = 3.0) -> bool:
    import paho.mqtt.client as mqtt
    token = f"motionedge-doctor-{time.monotonic_ns()}"; topic = f"motionedge/v1/diagnostics/{token}"
    received = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=token)
    def connected(instance, userdata, flags, reason_code, properties):
        if getattr(reason_code, "value", reason_code) == 0: instance.subscribe(topic, qos=1); instance.publish(topic, token, qos=1)
    def message(instance, userdata, msg):
        if msg.payload.decode("utf-8", "replace") == token: received.set()
    client.on_connect, client.on_message = connected, message
    try:
        client.connect(host, port, 10); client.loop_start(); return received.wait(timeout)
    except OSError: return False
    finally:
        try: client.disconnect(); client.loop_stop()
        except Exception: pass


def _doctor(args) -> int:
    checks = {}; info = status = None
    try:
        with DeviceClient(SerialTransport(args.port, args.baud), retries=3) as device:
            device.request(commands.PING)
            info = decode_device_info(device.request(commands.GET_DEVICE_INFO))
            status = decode_status(device.request(commands.GET_STATUS))
        checks["serial_device"] = "PASS"
    except Exception as exc:
        checks["serial_device"] = "FAIL"; checks["serial_error"] = str(exc)
    checks["mqtt_round_trip"] = "PASS" if _mqtt_round_trip(args.broker, args.mqtt_port) else "FAIL"
    try:
        import urllib.request
        with urllib.request.urlopen(args.node_red_url, timeout=2) as response:
            checks["node_red"] = "PASS" if response.status < 400 else "WARN"
    except Exception: checks["node_red"] = "WARN"
    topics = TopicSet("validation-device", "validation-gateway").rules()
    checks["topic_contract"] = "PASS" if (not topics["motion"].retain and topics["state"].retain) else "FAIL"
    result = "FAIL" if "FAIL" in checks.values() else "WARN" if "WARN" in checks.values() else "PASS"
    print(json.dumps({"result": result, "checks": checks,
                      "firmware": info.firmware_version if info else None,
                      "protocol": info.protocol_version if info else None,
                      "application": status.app_state if status else None,
                      "gateway_version": __version__}, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS if result in ("PASS", "WARN") else EXIT_RUNTIME


def run_gateway_command(args) -> int:
    if args.gateway_command == "doctor": return _doctor(args)
    config = load_gateway_config(args.config)
    if args.gateway_command == "run":
        gateway = Gateway(config)
        try: result = gateway.run(args.duration)
        except KeyboardInterrupt: gateway.stop(); result = gateway.status()
        print(json.dumps(result, ensure_ascii=False, indent=2)); return EXIT_SUCCESS
    if args.gateway_command == "status":
        print(json.dumps({"gateway_version": __version__, "config": str(args.config),
                          "broker": f"{config.mqtt.host}:{config.mqtt.port}",
                          "device_id": config.gateway.device_id,
                          "gateway_id": config.gateway.gateway_id}, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS
    gateway = Gateway(config); result = gateway.run(args.duration)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS if result["metrics"]["motion_published"] > 0 else EXIT_RUNTIME
