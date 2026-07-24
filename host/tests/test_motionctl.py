import csv
import tempfile
import unittest
from pathlib import Path

import importlib.util
import sys

_LEGACY_PATH = Path(__file__).resolve().parents[1] / "motionctl.py"
_SPEC = importlib.util.spec_from_file_location("motionctl_csv", _LEGACY_PATH)
assert _SPEC is not None and _SPEC.loader is not None
motionctl = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = motionctl
_SPEC.loader.exec_module(motionctl)


class MotionCtlTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "motion.csv"

    def tearDown(self):
        self.tempdir.cleanup()

    def write_rows(self, rows):
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(motionctl.COLUMNS)
            writer.writerows(rows)

    def test_normal_csv_parses(self):
        self.write_rows([[10, 1, 0, 1, 0, 0, 1000, 0, 0, 0, 0, 0]])
        self.assertEqual(len(motionctl.validate_file(self.path)), 1)

    def test_corrupt_row_fails(self):
        self.write_rows([[10, 1, 0, 1, "bad"]])
        with self.assertRaises(ValueError):
            motionctl.load_rows(self.path)

    def test_empty_file_fails(self):
        self.path.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            motionctl.load_rows(self.path)

    def test_timestamp_regression_fails(self):
        self.write_rows(
            [
                [20, 1, 0, 1, 0, 0, 1000, 0, 0, 0, 0, 0],
                [10, 2, 0, 1, 0, 0, 1000, 0, 0, 0, 0, 0],
            ]
        )
        with self.assertRaises(ValueError):
            motionctl.load_rows(self.path)

    def test_sequence_gap_fails_validation(self):
        self.write_rows(
            [
                [10, 1, 0, 1, 0, 0, 1000, 0, 0, 0, 0, 0],
                [20, 3, 0, 1, 0, 0, 1000, 0, 0, 0, 0, 0],
            ]
        )
        with self.assertRaises(ValueError):
            motionctl.validate_file(self.path)

    def test_summary_reports_gap_and_ranges(self):
        self.write_rows(
            [
                [10, 1, 0, 1, 0, 0, 1000, 0, 0, 0, -100, 200],
                [30, 3, 4, 1, 0, 0, 1000, 0, 0, 0, 300, -400],
            ]
        )
        summary = motionctl.summarize_rows(
            motionctl.load_rows(self.path, check_sequence=False)
        )
        self.assertEqual(summary["total_frames"], 2)
        self.assertEqual(summary["valid_frames"], 1)
        self.assertEqual(summary["lost_sequences"], 1)
        self.assertEqual(summary["roll_min_cdeg"], -100)
        self.assertEqual(summary["pitch_max_cdeg"], 200)

    def test_simulate_output_validates(self):
        motionctl.simulate(0.2, self.path)
        rows = motionctl.validate_file(self.path)
        self.assertEqual(len(rows), 20)


if __name__ == "__main__":
    unittest.main()
