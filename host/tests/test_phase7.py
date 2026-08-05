from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
import uuid
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from motionctl.gateway import CommandResultCache, Gateway, ReconnectBackoff
from motionctl.gateway_config import load_gateway_config
from motionctl.gateway_metrics import GatewayMetrics
from motionctl.mqtt_models import (ALLOWED_COMMANDS, MqttCommand, json_bytes,
                                    response_payload, utc_iso, utc_now)
from motionctl.mqtt_topics import TopicSet

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "motionedge-gateway.example.toml"
FLOW = ROOT / "node-red" / "flows" / "motionedge-phase07.json"


def command(name="ping", request_id=None, issued=None, expires=None, params=None):
    now = issued or utc_now()
    return {"schema_version": 1, "request_id": request_id or str(uuid.uuid4()),
            "command": name, "issued_at": utc_iso(now),
            "expires_at": utc_iso(expires or now + timedelta(seconds=30)),
            "params": params or {}}


class FakeMqtt:
    def __init__(self, config, **kwargs):
        self.connected = True; self.reconnect_count = 0; self.kwargs = kwargs
        self.subscriptions = []; self.published = []
    def add_subscription(self, topic, qos): self.subscriptions.append((topic, qos))
    def start(self): self.connected = True
    def publish(self, topic, payload, *, qos, retain):
        self.published.append((topic, payload, qos, retain)); return self.connected
    def stop(self): self.connected = False


class Phase7Tests(unittest.TestCase):
    def test_topic_generation(self):
        t = TopicSet("dev-01", "gw-01")
        self.assertEqual(t.motion, "motionedge/v1/devices/dev-01/telemetry/motion")

    def test_gateway_topics(self):
        self.assertTrue(TopicSet("dev-01", "gw-01").gateway_metrics.endswith("/metrics"))

    def test_qos_retain_contract(self):
        r = TopicSet("dev-01", "gw-01").rules()
        self.assertTrue(r["state"].retain); self.assertFalse(r["motion"].retain)
        self.assertFalse(r["command"].retain); self.assertEqual(r["command"].qos, 1)

    def test_json_null_is_preserved(self):
        self.assertIn(b'"mcu":null', json_bytes({"mcu": None}))

    def test_command_parse(self):
        value = MqttCommand.parse(json.dumps(command()))
        self.assertEqual(value.command, "ping")

    def test_request_id_must_be_uuid(self):
        with self.assertRaises(ValueError): MqttCommand.parse(json.dumps(command(request_id="bad")))

    def test_unknown_command_rejected(self):
        raw = command(); raw["command"] = "pwm"
        with self.assertRaises(ValueError): MqttCommand.parse(json.dumps(raw))

    def test_side_effect_whitelist_has_no_actuator(self):
        self.assertNotIn("pwm", ALLOWED_COMMANDS); self.assertNotIn("pid", ALLOWED_COMMANDS)

    def test_expired_command(self):
        old = utc_now() - timedelta(seconds=60)
        value = MqttCommand.parse(json.dumps(command(issued=old, expires=old + timedelta(seconds=1))))
        self.assertTrue(value.expired())

    def test_response_schema(self):
        value = response_payload(str(uuid.uuid4()), "ping", True, transport_attempts=2)
        self.assertEqual(value["transport_attempts"], 2); self.assertIsNone(value["error"])

    def test_cache_duplicate(self):
        cache = CommandResultCache(2, 60); cache.put("a", {"ok": True})
        self.assertTrue(cache.get("a")["ok"])

    def test_cache_capacity(self):
        cache = CommandResultCache(2, 60)
        for key in "abc": cache.put(key, {"key": key})
        self.assertIsNone(cache.get("a")); self.assertEqual(len(cache), 2)

    def test_cache_ttl(self):
        cache = CommandResultCache(2, 0.001); cache.put("a", {"ok": True}); time.sleep(0.003)
        self.assertIsNone(cache.get("a"))

    def test_config_load(self):
        config = load_gateway_config(EXAMPLE)
        self.assertEqual(config.mqtt.port, 1884); self.assertEqual(config.limits.command_queue_capacity, 16)

    def test_config_missing_fails(self):
        with self.assertRaises(ValueError): load_gateway_config(ROOT / "missing.toml")

    def test_config_unknown_field_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.toml"
            path.write_text(EXAMPLE.read_text(encoding="utf-8") + "\nunknown=1\n", encoding="utf-8")
            with self.assertRaises(ValueError): load_gateway_config(path)

    def test_password_environment(self):
        old = os.environ.get("MOTIONEDGE_MQTT_PASSWORD")
        try:
            os.environ["MOTIONEDGE_MQTT_PASSWORD"] = "secret"
            self.assertEqual(load_gateway_config(EXAMPLE).mqtt.password, "secret")
        finally:
            if old is None: os.environ.pop("MOTIONEDGE_MQTT_PASSWORD", None)
            else: os.environ["MOTIONEDGE_MQTT_PASSWORD"] = old

    def test_metrics_separate_logical_transport_retry(self):
        m = GatewayMetrics(); m.increment("logical_requests"); m.increment("transport_attempts", 2); m.increment("safe_retries")
        value = m.snapshot(); self.assertEqual((value["logical_requests"], value["transport_attempts"], value["safe_retries"]), (1, 2, 1))

    def test_metrics_latency_bounded(self):
        m = GatewayMetrics(4)
        for value in range(10): m.record_processing(value)
        self.assertEqual(m.snapshot()["gateway_processing_ms"]["count"], 4)

    def test_retained_command_rejected(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        raw = command("start_calibration"); gateway._handle_command(json_bytes(raw), True)
        self.assertEqual(gateway.metrics.snapshot()["retained_rejected"], 1)

    def test_duplicate_request_uses_cache(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        raw = command(); payload = json_bytes(raw)
        gateway._handle_command(payload, False); gateway._handle_command(payload, False)
        self.assertEqual(gateway.metrics.snapshot()["duplicate_commands"], 1)

    def test_command_queue_is_fixed(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        self.assertEqual(gateway.command_queue.maxsize, 16)

    def test_lwt_is_offline_retained_topic(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        self.assertEqual(gateway._mqtt.kwargs["will_payload"], b"offline")
        self.assertTrue(gateway._mqtt.kwargs["will_topic"].endswith("/availability"))

    def test_flow_json_and_unique_ids(self):
        flows = json.loads(FLOW.read_text(encoding="utf-8")); ids = [row["id"] for row in flows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_flow_uses_core_nodes(self):
        types = {row["type"] for row in json.loads(FLOW.read_text(encoding="utf-8"))}
        self.assertTrue({"mqtt in", "mqtt out", "function", "http in", "websocket out"}.issubset(types))

    def test_flow_topic_matches_python(self):
        text = FLOW.read_text(encoding="utf-8")
        self.assertIn("motionedge/v1/devices/+/telemetry/motion", text)

    def test_ui_history_is_bounded(self):
        text = (ROOT / "node-red" / "public" / "app.js").read_text(encoding="utf-8")
        self.assertIn("MAX_POINTS=300", text); self.assertIn("history.shift()", text)

    def test_flow_has_status_and_metrics_endpoints(self):
        text = FLOW.read_text(encoding="utf-8")
        self.assertIn("/motionedge/api/status", text); self.assertIn("/motionedge/api/metrics", text)

    def test_gateway_status_has_bounded_queue(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        self.assertEqual(gateway.status()["command_queue"], 0)

    def test_empty_retained_clear_is_not_a_command_error(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        gateway._on_mqtt_message(gateway.topics.command, b"", False)
        self.assertEqual(gateway.metrics.snapshot()["command_errors"], 0)

    def test_gateway_metrics_has_schema_version(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        self.assertEqual(gateway._gateway_metrics()["schema_version"], 1)

    def test_serial_backoff_is_exponential_bounded_and_resettable(self):
        backoff = ReconnectBackoff(500, 1000, jitter_ratio=0.0)
        self.assertEqual([backoff.next_delay() for _ in range(3)], [0.5, 1.0, 1.0])
        backoff.reset()
        self.assertEqual(backoff.next_delay(), 0.5)


if __name__ == "__main__": unittest.main()
