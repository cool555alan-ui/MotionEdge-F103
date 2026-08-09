from __future__ import annotations

import json
import struct
import unittest
import uuid
from datetime import timedelta

from motionctl import commands
from motionctl.cli import build_parser
from motionctl.gateway import Gateway
from motionctl.gateway_config import load_gateway_config
from motionctl.mqtt_models import ALLOWED_COMMANDS, SIDE_EFFECT_COMMANDS, json_bytes, utc_iso, utc_now

from test_phase7 import EXAMPLE, FakeMqtt, command


def actuator_payload(*, armed=True, owner=2):
    return struct.pack("<BBBBhhHHHHIIIII", 1 if armed else 0, 4, int(armed), owner,
                       1000, 900, 1611, 1600, 1000, 2000,
                       25, 2, 3, 4, 5)


class FakeDevice:
    def __init__(self):
        self.calls = []
        self.attempt_results = []

    def request(self, command_id, payload=b"", *, retry=None):
        self.calls.append((command_id, payload, retry))
        if command_id == commands.ACTUATOR_GET_STATUS:
            return actuator_payload()
        return b""


class Phase9Tests(unittest.TestCase):
    def test_health_codec_includes_rtos_deadlines(self):
        payload = struct.pack("<IBB10I", 1000, 2, 2, 100, 0, 0, 10, 0, 0,
                              1, 2, 3, 4)
        value = commands.decode_health(payload)
        self.assertEqual((value.sensor_deadline_miss,
                          value.communication_deadline_miss,
                          value.telemetry_deadline_miss,
                          value.health_deadline_miss), (1, 2, 3, 4))

    def test_actuator_status_codec(self):
        value = commands.decode_actuator_status(actuator_payload())
        self.assertTrue(value.armed)
        self.assertEqual(value.owner, "SERIAL")
        self.assertEqual(value.target_angle_deg, 10.0)
        self.assertEqual(value.estop_count, 5)

    def test_actuator_status_rejects_wrong_size(self):
        with self.assertRaises(ValueError):
            commands.decode_actuator_status(b"\0" * 35)

    def test_cli_surface(self):
        parser = build_parser()
        value = parser.parse_args(["actuator", "set-angle", "--port", "COM8", "--angle", "10"])
        self.assertEqual(value.actuator_command, "set-angle")
        value = parser.parse_args(["actuator", "calibrate-range", "--port", "COM8"])
        self.assertEqual(value.step_us, 25)

    def test_mqtt_whitelist_and_side_effects(self):
        expected = {"actuator_status", "actuator_arm", "actuator_disarm",
                    "actuator_center", "actuator_set_target", "actuator_estop"}
        self.assertTrue(expected.issubset(ALLOWED_COMMANDS))
        self.assertTrue((expected - {"actuator_status"}).issubset(SIDE_EFFECT_COMMANDS))
        self.assertNotIn("pid_enable", ALLOWED_COMMANDS)

    def test_mqtt_target_uses_owner_and_no_retry(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        device = FakeDevice(); gateway._device = device
        raw = command("actuator_set_target", params={"angle_deg": 12.5})
        gateway._handle_command(json_bytes(raw), False)
        self.assertEqual(device.calls[0],
                         (commands.ACTUATOR_SET_TARGET,
                          struct.pack("<Bh", commands.ACTUATOR_OWNER_MQTT, 1250),
                          False))

    def test_retained_actuator_command_rejected_before_device(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        device = FakeDevice(); gateway._device = device
        gateway._handle_command(json_bytes(command("actuator_arm")), True)
        self.assertEqual(device.calls, [])
        self.assertEqual(gateway.metrics.snapshot()["retained_rejected"], 1)

    def test_duplicate_request_does_not_repeat_motion(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        device = FakeDevice(); gateway._device = device
        request_id = str(uuid.uuid4())
        payload = json_bytes(command("actuator_center", request_id=request_id))
        gateway._handle_command(payload, False); gateway._handle_command(payload, False)
        self.assertEqual(len(device.calls), 1)

    def test_expired_actuator_command_rejected(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        device = FakeDevice(); gateway._device = device
        old = utc_now() - timedelta(seconds=60)
        gateway._handle_command(json_bytes(command("actuator_estop", issued=old,
                                                   expires=old + timedelta(seconds=1))), False)
        self.assertEqual(device.calls, [])
        self.assertEqual(gateway.metrics.snapshot()["expired_commands"], 1)

    def test_actuator_topic_is_not_retained(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        self.assertFalse(gateway.rules["actuator"].retain)
        self.assertTrue(gateway.topics.actuator.endswith("/telemetry/actuator"))


if __name__ == "__main__": unittest.main()
