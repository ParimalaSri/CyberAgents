"""Unit tests for scripts/path_guard.py and its use by scripts/build_spread_sample.py (stdlib unittest)."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT_DIR = SCRIPTS.parent
SPEC = importlib.util.spec_from_file_location("path_guard", SCRIPTS / "path_guard.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class ForbiddenPathTests(unittest.TestCase):
    """Which output paths are refused."""

    def test_refused_paths(self):
        """data/raw, the dataset folder, `..` traversal into them and case variants are all refused."""
        refused = [
            ROOT_DIR / "data" / "raw" / "x.parquet",
            ROOT_DIR / "data" / "raw",
            str(ROOT_DIR / "data" / "silver" / ".." / "raw" / "x.parquet"),
            str(ROOT_DIR / "data" / "silver" / ".." / ".." / "data" / "raw" / "deep" / "x"),
            str(ROOT_DIR / "DATA" / "Raw" / "x.parquet"),
            "D:/Cyber_DataSet/x.parquet", "D:\\Cyber_DataSet\\sub\\x.parquet", "d:/cyber_dataset/x.parquet",
            "D:/Cyber_DataSet/other/../x.parquet", "D:/Cyber_DataSet",
        ]
        for path in refused:
            self.assertIsNotNone(GUARD.forbidden_reason(path), str(path))
            with self.assertRaises(SystemExit) as caught:
                GUARD.check_output_path(path)
            self.assertIn("refusing to write", str(caught.exception))

    def test_allowed_paths(self):
        """Normal output folders, names that only look similar, and a `..` that leaves the raw folder are allowed."""
        allowed = [
            ROOT_DIR / "data" / "silver" / "hosts.parquet", ROOT_DIR / "data" / "gold" / "accounts.parquet",
            ROOT_DIR / "data" / "rawish" / "x.parquet", ROOT_DIR / "data" / "raw_copy" / "x.parquet",
            str(ROOT_DIR / "data" / "raw" / ".." / "silver" / "x.parquet"),
            "D:/Cyber_DataSet_copy/x.parquet", "D:/other/x.parquet", Path(tempfile.gettempdir()) / "scratch.parquet",
        ]
        for path in allowed:
            self.assertIsNone(GUARD.forbidden_reason(path), str(path))
            GUARD.check_output_path(path)

    def test_dataset_constant(self):
        """The dataset folder constant is the documented source folder."""
        self.assertEqual(GUARD.DATASET_DIR, "D:/Cyber_DataSet/")


class ReportPathTests(unittest.TestCase):
    """Where the stage report goes."""

    def test_choices(self):
        """--report wins; the default output keeps the committed path; any other output gets a report beside it."""
        default_out, default_report = ROOT_DIR / "data" / "gold" / "x.parquet", ROOT_DIR / "outputs" / "dq" / "x_2026-01-01.md"
        self.assertEqual(GUARD.choose_report_path(default_out, default_out, "my.md", default_report, "x"), Path("my.md"))
        self.assertEqual(GUARD.choose_report_path(str(default_out), default_out, None, default_report, "x"), default_report)
        scratch = Path(tempfile.gettempdir()) / "t" / "o.parquet"
        self.assertEqual(GUARD.choose_report_path(scratch, default_out, None, default_report, "x"), scratch.parent / "x_stage_report.md")


class SpreadSampleTests(unittest.TestCase):
    """build_spread_sample.py refuses the same paths."""

    def test_sample_builder_refuses_raw_output(self):
        """The sample builder exits with a refusal for an output under data/raw (also via ..) and writes nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "src.jsonl")
            src.write_text('{"a": 1}\n' * 50, encoding="utf-8")
            for target in (ROOT_DIR / "data" / "raw" / "qa_sample.jsonl", str(ROOT_DIR / "data" / "silver" / ".." / "raw" / "qa_sample.jsonl"),
                           "D:/Cyber_DataSet/qa_sample.jsonl"):
                result = subprocess.run([sys.executable, str(SCRIPTS / "build_spread_sample.py"), "--src", str(src), "--out", str(target),
                                         "--positions", "2", "--lines", "2"], capture_output=True, text=True, env=dict(os.environ))
                self.assertNotEqual(result.returncode, 0, str(target))
                self.assertIn("refusing to write", result.stderr)
                self.assertFalse(Path(target).exists())

    def test_sample_builder_still_writes_normal_output(self):
        """A normal output path still works."""
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "in", "src.jsonl"), Path(tmp, "out", "s.jsonl")
            src.parent.mkdir()
            src.write_text('{"a": 1}\n' * 50, encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPTS / "build_spread_sample.py"), "--src", str(src), "--out", str(out),
                                     "--positions", "2", "--lines", "2"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
