from __future__ import annotations

import math
import struct
import unittest

from motionctl import commands
from motionctl.cli import build_parser
from motionctl.control_experiment import summarize_control_rows
from motionctl.gateway import Gateway
from motionctl.gateway_config import load_gateway_config
from motionctl.mqtt_models import ALLOWED_COMMANDS, SIDE_EFFECT_COMMANDS, json_bytes

from test_phase7 import EXAMPLE, FakeMqtt, command


def control_payload(**overrides):
    values = {
        "mode": 1, "axis": 0, "direction": 0, "integral": 0,
        "flags": 3, "fault": 0,
        "zero": 100, "measured": 600, "relative": 500, "effective": 500,
        "deadband": 100, "kp": 2000, "ki": 0, "kd": 100,
        "p": 10000, "i": 0, "d": -1000, "output": 9,
        "requested": 1509, "actual": 1508,
        "counters": (1, 100, 0, 0, 0, 0, 0, 0, 2, 3),
    }
    values.update(overrides)
    return struct.pack(
        "<BBBBBB4iH6ihHH10I",
        values["mode"], values["axis"], values["direction"], values["integral"],
        values["flags"], values["fault"], values["zero"], values["measured"],
        values["relative"], values["effective"], values["deadband"],
        values["kp"], values["ki"], values["kd"], values["p"], values["i"],
        values["d"], values["output"], values["requested"], values["actual"],
        *values["counters"])


class FakeControlDevice:
    def __init__(self):
        self.calls = []
        self.attempt_results = []

    def request(self, command_id, payload=b"", *, retry=None):
        self.calls.append((command_id, payload, retry))
        if command_id == commands.CONTROL_GET_STATUS:
            return control_payload()
        if command_id == commands.CONTROL_GET_PID:
            return commands.PidConfig().pack()
        return b""


class Phase9BTests(unittest.TestCase):
    def test_control_status_codec(self):
        value = commands.decode_control_status(control_payload())
        self.assertEqual(value.mode, "PID_ATTITUDE")
        self.assertEqual(value.axis, "ROLL")
        self.assertTrue(value.enabled)
        self.assertTrue(value.active)
        self.assertEqual(value.relative_angle_cdeg, 500)
        self.assertEqual(value.actual_pulse_us, 1508)
        self.assertEqual(value.update_count, 100)

    def test_control_status_wrong_size(self):
        with self.assertRaises(ValueError):
            commands.decode_control_status(b"\0" * 93)

    def test_pid_config_round_trip_and_ranges(self):
        value = commands.PidConfig(2.5, 0.0, 0.1, 20, 0.25, 0, 0.99)
        self.assertEqual(commands.PidConfig.unpack(value.pack()), value)
        self.assertFalse(commands.PidConfig(kp=math.nan).validate())
        self.assertFalse(commands.PidConfig(output_limit_us=51).validate())

    def test_control_cli_surface(self):
        parser = build_parser()
        value = parser.parse_args(["control", "enable", "--port", "COM4",
                                   "--axis", "roll"])
        self.assertEqual(value.control_command, "enable")
        value = parser.parse_args(["control", "pid", "set", "--port", "COM4",
                                   "--kp", "2", "--ki", "0", "--kd", "0.1"])
        self.assertEqual(value.pid_command, "set")
        value = parser.parse_args(["control", "characterize", "--port", "COM4",
                                   "--output", "out"])
        self.assertEqual(value.duration, 60.0)

    def test_mqtt_control_whitelist(self):
        expected = {"control_status", "control_enable", "control_disable",
                    "control_zero", "control_set_axis", "control_set_direction",
                    "control_get_pid", "control_set_pid", "control_set_deadband"}
        self.assertTrue(expected.issubset(ALLOWED_COMMANDS))
        self.assertTrue((expected - {"control_status", "control_get_pid"})
                        .issubset(SIDE_EFFECT_COMMANDS))

    def test_mqtt_enable_uses_owner_and_no_retry(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        device = FakeControlDevice(); gateway._device = device
        gateway._handle_command(json_bytes(command("control_enable",
                                                   params={"axis": "pitch"})), False)
        self.assertEqual(device.calls[0],
                         (commands.CONTROL_ENABLE,
                          bytes((commands.ACTUATOR_OWNER_MQTT, 1)), False))

    def test_mqtt_retained_control_rejected(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        device = FakeControlDevice(); gateway._device = device
        gateway._handle_command(json_bytes(command("control_enable",
                                                   params={"axis": "roll"})), True)
        self.assertEqual(device.calls, [])

    def test_control_topic_not_retained(self):
        gateway = Gateway(load_gateway_config(EXAMPLE), mqtt_factory=FakeMqtt)
        self.assertFalse(gateway.rules["control"].retain)
        self.assertNotIn("closed", gateway.topics.control.lower())

    def test_empty_experiment(self):
        self.assertEqual(summarize_control_rows([])["status"], "NOT_TESTED")

    def test_experiment_metrics(self):
        rows = [
            {"host_monotonic_ns": 0, "actual_pwm_us": 1500,
             "output_us": 0, "relative_angle_deg": 0,
             "saturated": 0, "in_deadband": 1},
            {"host_monotonic_ns": 100_000_000, "actual_pwm_us": 1510,
             "output_us": 10, "relative_angle_deg": 5,
             "saturated": 0, "in_deadband": 0},
        ]
        result = summarize_control_rows(rows)
        self.assertEqual(result["pwm_peak_to_peak_us"], 10)
        self.assertEqual(result["interpretation"], "HUMAN_INPUT_LIMITED")


if __name__ == "__main__":
    unittest.main()
