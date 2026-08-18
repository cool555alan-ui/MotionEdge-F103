import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST))

from motionctl import __version__, commands
from motionctl.cli import build_parser
from motionctl.mqtt_models import ALLOWED_COMMANDS, SIDE_EFFECT_COMMANDS
from phase10_system_acceptance import (counter_delta, counter_deltas,
                                       preflight_failures,
                                       recover_external_observer_failure)


class Phase10Tests(unittest.TestCase):
    def test_acceptance_counter_deltas_handle_uint32_wrap(self):
        self.assertEqual(counter_delta(10, 13), 3)
        self.assertEqual(counter_delta(0xFFFFFFFE, 1), 3)
        self.assertEqual(
            counter_deltas({"errors": 7}, {"errors": 9}, ("errors",)),
            {"errors": 2},
        )

    def test_acceptance_preflight_requires_sensor_and_safe_actuator(self):
        ready = preflight_failures(
            SimpleNamespace(app_state="RUNNING", sensor_state="RUNNING"),
            SimpleNamespace(calibrated=True),
            SimpleNamespace(armed=False, owner="NONE", current_pulse_us=1500),
            SimpleNamespace(enabled=False),
        )
        self.assertEqual(ready, [])
        blocked = preflight_failures(
            SimpleNamespace(app_state="DEGRADED", sensor_state="CALIBRATING"),
            SimpleNamespace(calibrated=False),
            SimpleNamespace(armed=False, owner="NONE", current_pulse_us=1510),
            SimpleNamespace(enabled=False),
        )
        self.assertEqual(
            blocked,
            ["app=DEGRADED", "sensor=CALIBRATING",
             "motion_not_calibrated", "pwm=1510us"],
        )

    def test_acceptance_recovers_only_observer_failures(self):
        failed = {
            "status": "FAIL",
            "checks": {
                "no_reset": "PASS",
                "control_error_delta": "PASS",
                "mqtt_motion": "FAIL",
                "broker_recovery": "FAIL",
                "pid_continues_during_broker_outage": "FAIL",
                "uart_line_error_counter": "WARN",
            },
            "node_red_after": {"motion_received": 10, "health_received": 1},
            "control_before_broker": {"update_count": 100},
            "final_control": {"update_count": 200, "last_fault": "NONE"},
        }
        log = ("mosquitto version 2.1.2 running as motionedge-gateway-01 "
               "/telemetry/motion /telemetry/control")
        recovered = recover_external_observer_failure(failed, log)
        self.assertEqual(recovered["status"], "WARN")
        self.assertEqual(recovered["checks"]["mqtt_motion"], "PASS")
        self.assertEqual(
            recovered["external_observer_recovery"]
                     ["pid_continuity_evidence"]["update_count_delta"],
            100,
        )

    def test_version(self):
        self.assertEqual(__version__, "1.0.0")
        self.assertEqual(Path("VERSION").read_text(encoding="utf-8").strip(), __version__)

    def test_persistence_status_codec(self):
        import struct
        payload = struct.pack("<BBBBI", 2, 1, 2, 1, 9) + bytes((1,)) + struct.pack("<7I", 3, 1, 2, 4, 5, 6, 7)
        status = commands.decode_persistence_status(payload)
        self.assertEqual(status["source"], "SLOT_B")
        self.assertEqual(status["generation"], 9)
        self.assertTrue(status["dirty"])
        self.assertEqual(status["crc_error_count"], 2)

    def test_cli_surface_and_factory_confirmation(self):
        parser = build_parser()
        for action in ("status", "save", "load"):
            args = parser.parse_args(["config", "persist", action, "--port", "COM4"])
            self.assertEqual(args.persist_command, action)
        args = parser.parse_args(["config", "persist", "factory-reset", "--port", "COM4", "--yes"])
        self.assertTrue(args.yes)

    def test_mqtt_safety_contract(self):
        self.assertIn("config_persist_status", ALLOWED_COMMANDS)
        for command in ("config_persist_save", "config_persist_load", "config_factory_reset"):
            self.assertIn(command, SIDE_EFFECT_COMMANDS)

    def test_node_red_non_retained_and_confirmation(self):
        flow = json.loads(Path("node-red/flows/motionedge-phase07.json").read_text(encoding="utf-8"))
        output = next(node for node in flow if node.get("id") == "p7commandmqtt01")
        self.assertEqual(output["retain"], "false")
        html = Path("node-red/public/index.html").read_text(encoding="utf-8")
        self.assertIn("config_factory_reset", html)
        self.assertIn("data-confirm", html)


if __name__ == "__main__":
    unittest.main()
