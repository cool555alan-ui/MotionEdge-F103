import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST))

from motionctl import commands  # noqa: E402
from motionctl.capture import TELEMETRY_COLUMNS, capture_session  # noqa: E402
from motionctl.cli import build_parser, main  # noqa: E402
from motionctl.device import DeviceClient  # noqa: E402
from motionctl.errors import ConnectionError, RequestTimeout  # noqa: E402
from motionctl.metrics import command_metrics, motion_metrics  # noqa: E402
from motionctl.models import CaptureMetadata, CommandResult, MotionSample, PortInfo  # noqa: E402
from motionctl.protocol import Frame, FrameParser, decode_frame, encode_frame  # noqa: E402
from motionctl.report import generate_report  # noqa: E402
from motionctl.simulator import SimulatedDevice  # noqa: E402
from motionctl.transport import MemoryTransport, SerialTransport  # noqa: E402
from motionctl.validation import NOT_TESTED, validate_metrics  # noqa: E402


def sample(index=0, sequence=None):
    sequence = sequence if sequence is not None else index * 10
    return MotionSample(index * 100, sequence, 0, True, 0, 0, 1000, 0, 0, 0,
                        float(index), float(-index), index * 100, -index * 100,
                        1_000_000_000 + index * 100_000_000)


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.is_open = True; self.closed = False; self.input_flushed = False
        self.short = kwargs.pop("short", None); self.pending = bytearray(b"abc")

    def write(self, data): return len(data)
    def read(self, size):
        result = bytes(self.pending[:size]); del self.pending[:size]; return result
    def reset_input_buffer(self): self.pending.clear(); self.input_flushed = True
    def close(self): self.is_open = False; self.closed = True


class Phase6Tests(unittest.TestCase):
    def test_cli_core_commands_parse(self):
        parser = build_parser()
        for argv in (["ports"], ["doctor", "--port", "COM1"], ["config", "get", "--port", "COM1"],
                     ["stream", "start", "--port", "COM1"], ["validate", "x"],
                     ["report", "x", "--output", "y"], ["session", "--port", "COM1", "--output", "x"]):
            self.assertIsNotNone(parser.parse_args(argv).command)

    def test_port_output_model(self):
        self.assertEqual(PortInfo("COM4", "CH340", 0x1A86, 0x7523, None, "usb-ttl").likely_role, "usb-ttl")

    def test_serial_transport_empty_port(self):
        with self.assertRaises(ValueError): SerialTransport("", auto_open=False)

    def test_serial_transport_close_idempotent_and_context(self):
        transport = SerialTransport("COM1", serial_factory=FakeSerial)
        self.assertEqual(transport.read(2), b"ab")
        transport.flush_input(); transport.close(); transport.close()
        self.assertFalse(transport.is_open)

    def test_serial_transport_short_write(self):
        class Short(FakeSerial):
            def write(self, data): return len(data) - 1
        transport = SerialTransport("COM1", serial_factory=Short)
        with self.assertRaises(ConnectionError): transport.write(b"123")

    def test_memory_transport_short_read_and_write(self):
        transport = MemoryTransport(read_chunk=2, short_write=1)
        transport.inject(b"abcd")
        self.assertEqual(transport.read(), b"ab")
        self.assertEqual(transport.write(b"xyz"), 1)

    def test_device_flush_discards_backlog_and_parser_state(self):
        transport = MemoryTransport()
        client = DeviceClient(transport)
        transport.inject(b"stale")
        client.parser.feed(b"noise")
        client.flush_input()
        self.assertEqual(transport.read(), b"")
        self.assertEqual(client.parser.discarded_bytes, 0)

    def test_safe_query_retries(self):
        device = SimulatedDevice(timeout_commands={commands.PING})
        with self.assertRaises(RequestTimeout): DeviceClient(device, timeout=0.001, retries=1).request(commands.PING)
        self.assertEqual(device.request_count, 2)

    def test_side_effect_does_not_retry(self):
        device = SimulatedDevice(timeout_commands={commands.START_CALIBRATION})
        with self.assertRaises(RequestTimeout): DeviceClient(device, timeout=0.001, retries=3).request(commands.START_CALIBRATION)
        self.assertEqual(device.request_count, 1)

    def test_async_telemetry_is_separated_from_response(self):
        def responder(raw):
            request = decode_frame(raw)
            motion = encode_frame(Frame(commands.MOTION_TELEMETRY, 99, SimulatedDevice().motion_payload()))
            payload = bytes((request.type, 0, 0, 0, 0, 0))
            return motion + encode_frame(Frame(commands.COMMAND_RESPONSE, request.sequence, payload))
        client = DeviceClient(MemoryTransport(responder, read_chunk=7), timeout=0.05)
        self.assertEqual(client.request(commands.PING), b"")
        self.assertEqual(len(client.telemetry), 1)

    def test_fixed_sequence_step_ten(self):
        result = motion_metrics([sample(i) for i in range(20)])
        self.assertEqual(result["sequence"]["expected_step"], 10)
        self.assertEqual(result["sequence"]["estimated_lost"], 0)

    def test_sequence_duplicate(self):
        result = motion_metrics([sample(0, 10), sample(1, 10), sample(2, 20)])
        self.assertEqual(result["sequence"]["duplicates"], 1)

    def test_sequence_regression(self):
        result = motion_metrics([sample(0, 20), sample(1, 10)])
        self.assertEqual(result["sequence"]["regressions"], 1)

    def test_sequence_gap(self):
        result = motion_metrics([sample(0, 10), sample(1, 20), sample(2, 40)], expected_step=10)
        self.assertEqual(result["sequence"]["estimated_lost"], 1)

    def test_timestamp_and_frequency_metrics(self):
        result = motion_metrics([sample(i) for i in range(11)])
        self.assertTrue(result["device_timestamp_monotonic"])
        self.assertEqual(result["interval_ms"]["p95"], 100.0)

    def test_command_rtt_percentiles(self):
        rows = [CommandResult("PING", True, float(value), value) for value in range(1, 101)]
        result = command_metrics(rows)
        self.assertEqual(result["success_rate_percent"], 100.0)
        self.assertAlmostEqual(result["rtt_ms"]["p95"], 95.05)

    def test_missing_fields_are_not_tested(self):
        result = validate_metrics({"frame_count": 0})
        statuses = {item.name: item.status for item in result.items}
        self.assertEqual(statuses["device_identity"], NOT_TESTED)
        self.assertEqual(statuses["crc_errors"], NOT_TESTED)

    def test_simulator_disconnect(self):
        client = DeviceClient(SimulatedDevice(disconnect_after=1), timeout=0.01)
        client.request(commands.PING)
        with self.assertRaises(ConnectionError): client.request(commands.GET_STATUS)

    def test_simulator_crc_error(self):
        client = DeviceClient(SimulatedDevice(corrupt_crc=True), timeout=0.002, retries=0)
        with self.assertRaises(RequestTimeout): client.request(commands.PING)
        self.assertGreater(client.parser.crc_errors, 0)

    def test_capture_ctrl_c_finalizes_atomic_files(self):
        class InterruptTransport:
            def read(self, size=256): raise KeyboardInterrupt
        class Client:
            transport = InterruptTransport(); parser = FrameParser(); command_results = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            metadata = CaptureMetadata("0.6.0", "now", 1.0, "SIM", 115200, None, None, None, True)
            result = capture_session(Client(), path, 1.0, metadata)
            self.assertTrue(result["interrupted"])
            self.assertTrue((path / "telemetry.csv").is_file())
            self.assertFalse(any(path.glob("*.tmp")))

    def _write_session(self, path, rows):
        with (path / "telemetry.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=TELEMETRY_COLUMNS, lineterminator="\n"); writer.writeheader()
            for row in rows: writer.writerow(row.__dict__)
        (path / "capture-summary.json").write_text(json.dumps({"requested_duration_s": 1, "parser": {"crc_errors": 0, "length_errors": 0, "version_errors": 0}, "health": []}), encoding="utf-8")
        (path / "session-metadata.json").write_text(json.dumps({"device_info": {"firmware_version": "0.6.0"}, "ping_ok": True, "command_success_rate": 100.0, "fault_seen": False, "degraded_persistent": False}), encoding="utf-8")

    def test_empty_data_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); self._write_session(path, [])
            result = generate_report(path, path / "report")
            self.assertEqual(result["metrics"]["frame_count"], 0)
            self.assertTrue((path / "report/report.md").is_file())
            self.assertEqual(result["charts"], [])

    def test_markdown_json_csv_and_charts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); self._write_session(path, [sample(i) for i in range(11)])
            generate_report(path, path / "report")
            for name in ("report.md", "report.json", "metrics.csv", "attitude.png", "telemetry-timing.png"):
                self.assertGreater((path / "report" / name).stat().st_size, 0)

    def test_cli_exit_code_on_missing_session(self):
        with mock.patch("sys.stderr"):
            self.assertNotEqual(main(["validate", "missing"]), 0)

    def test_simulated_30_minute_metrics_without_waiting(self):
        result = motion_metrics(sample(i) for i in range(18_000))
        self.assertEqual(result["frame_count"], 18_000)
        self.assertEqual(result["sequence"]["estimated_lost"], 0)


if __name__ == "__main__":
    unittest.main()
