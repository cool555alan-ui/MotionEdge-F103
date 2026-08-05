import json
import sys
import unittest
from pathlib import Path

HOST = Path(__file__).resolve().parents[1]
ROOT = HOST.parent
sys.path.insert(0, str(HOST))

from motionctl import commands  # noqa: E402
from motionctl.device import DeviceClient, SimulatedDevice, TimeoutError  # noqa: E402
from motionctl.protocol import (  # noqa: E402
    Frame,
    FrameParser,
    crc16_ccitt_false,
    decode_frame,
    encode_frame,
)


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = json.loads(
            (ROOT / "Tests/Fixtures/protocol_vectors.json").read_text(encoding="utf-8")
        )

    def test_crc_known_vector(self):
        self.assertEqual(crc16_ccitt_false(b"123456789"), 0x29B1)
        first = crc16_ccitt_false(b"1234")
        self.assertEqual(crc16_ccitt_false(b"56789", first), 0x29B1)

    def test_shared_golden_vectors(self):
        for vector in self.vectors:
            raw = bytes.fromhex(vector["frame_hex"])
            if not vector["valid"]:
                with self.assertRaises(ValueError, msg=vector["name"]):
                    decode_frame(raw)
                continue
            frame = Frame(
                vector["type"],
                vector["sequence"],
                bytes.fromhex(vector["payload_hex"]),
                vector["flags"],
            )
            self.assertEqual(encode_frame(frame), raw, vector["name"])
            self.assertEqual(decode_frame(raw), frame, vector["name"])

    def test_stream_splits_sticky_noise_and_recovery(self):
        good = bytes.fromhex(self.vectors[0]["frame_hex"])
        bad = bytes.fromhex(self.vectors[-1]["frame_hex"])
        parser = FrameParser()
        frames = []
        stream = b"noise\xA5" + bad + good + good
        for byte in stream:
            frames.extend(parser.feed(bytes((byte,))))
        self.assertEqual([frame.sequence for frame in frames], [4660, 4660])
        self.assertEqual(parser.crc_errors, 1)
        self.assertGreater(parser.discarded_bytes, 0)

    def test_sequence_matching_and_main_commands(self):
        client = DeviceClient(SimulatedDevice(), timeout=0.05)
        self.assertEqual(client.request(commands.PING), b"")
        self.assertEqual(client.request(commands.GET_DEVICE_INFO), bytes((0, 6, 0, 1)))
        config = commands.RuntimeConfig.unpack(client.request(commands.GET_CONFIG))
        changed = commands.RuntimeConfig(
            config.sensor_ms, 250, config.alpha_milli, config.gyro_weight_milli, config.log_level, True
        )
        self.assertEqual(client.request(commands.SET_CONFIG, changed.pack()), b"")
        self.assertEqual(
            commands.RuntimeConfig.unpack(client.request(commands.GET_CONFIG)), changed
        )
        self.assertEqual(client.request(commands.START_CALIBRATION), b"")
        self.assertEqual(client.request(commands.SET_STREAM_STATE, b"\1"), b"")

    def test_wrong_sequence_is_ignored(self):
        class MismatchedThenCorrect:
            def __init__(self):
                self.pending = b""

            def write(self, data):
                request = decode_frame(data)
                payload = bytes((request.type, 0, 0, 0, 0, 0))
                self.pending = (
                    encode_frame(Frame(commands.COMMAND_RESPONSE, request.sequence + 1, payload))
                    + encode_frame(Frame(commands.COMMAND_RESPONSE, request.sequence, payload))
                )

            def read(self, size=256):
                result, self.pending = self.pending[:size], self.pending[size:]
                return result

        self.assertEqual(
            DeviceClient(MismatchedThenCorrect(), timeout=0.05).request(commands.PING),
            b"",
        )

    def test_timeout(self):
        class SilentTransport:
            def write(self, data):
                pass

            def read(self, size=256):
                return b""

        with self.assertRaises(TimeoutError):
            DeviceClient(SilentTransport(), timeout=0.001).request(commands.PING)


if __name__ == "__main__":
    unittest.main()
