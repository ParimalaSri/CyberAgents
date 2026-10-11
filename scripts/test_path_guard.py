"""Unit tests for scripts/path_guard.py and its use by scripts/build_spread_sample.py; protected folders are scratch stand-ins (stdlib unittest)."""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
ROOT_DIR = SCRIPTS.parent
SPEC = importlib.util.spec_from_file_location("path_guard", SCRIPTS / "path_guard.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
SUPPORT_SPEC = importlib.util.spec_from_file_location("guard_test_support", SCRIPTS / "guard_test_support.py")
SUPPORT = importlib.util.module_from_spec(SUPPORT_SPEC)
SUPPORT_SPEC.loader.exec_module(SUPPORT)
SAMPLE_SPEC = importlib.util.spec_from_file_location("build_spread_sample", SCRIPTS / "build_spread_sample.py")
SAMPLE = importlib.util.module_from_spec(SAMPLE_SPEC)
SAMPLE_SPEC.loader.exec_module(SAMPLE)

REAL_RAW = ROOT_DIR / "data" / "raw"
RAW_BEFORE = {}


def raw_snapshot():
    """Return the file names and modification time of the real data/raw folder (empty when it does not exist)."""
    if not REAL_RAW.exists():
        return {"names": [], "mtime": None}
    return {"names": sorted(os.listdir(REAL_RAW)), "mtime": REAL_RAW.stat().st_mtime_ns}


RAW_BEFORE.update(raw_snapshot())


def check_raw_unchanged():
    """Fail when the real data/raw folder changed while this module ran (registered as a module cleanup)."""
    assert raw_snapshot() == RAW_BEFORE, "the real data/raw folder changed during the guard tests"


unittest.addModuleCleanup(check_raw_unchanged)


def make_link(link, target):
    """Create a directory symlink, or a junction when symlinks are not allowed; return False when the OS refuses both."""
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    return done.returncode == 0 and Path(link).exists()


class ForbiddenPathTests(unittest.TestCase):
    """Which output paths are refused, with the protected folders replaced by scratch directories."""

    def test_scratch_forms_refused(self):
        """Plain, `..`, upper-case, extended and loopback-UNC forms of both scratch folders are refused by parameter and by patched constants."""
        with SUPPORT.scratch_protected() as scratch:
            unc_extended = "\\\\?\\UNC\\localhost\\" + scratch.dataset.drive[0] + "$" + str(scratch.dataset)[2:].replace("/", "\\") + "\\x"
            raw_unc = "\\\\localhost\\" + scratch.raw.drive[0] + "$" + str(scratch.raw)[2:] + "\\x"
            raw_unc_loop = "\\\\127.0.0.1\\" + scratch.raw.drive[0] + "$" + str(scratch.raw)[2:] + "\\x"
            ds_unc_loop = "\\\\127.0.0.1\\" + scratch.dataset.drive[0] + "$" + str(scratch.dataset)[2:] + "\\x"
            targets = SUPPORT.forbidden_targets(scratch) + [unc_extended, raw_unc, raw_unc_loop, ds_unc_loop, scratch.raw, scratch.dataset]
            for path in targets:
                self.assertIsNotNone(GUARD.forbidden_reason(path, dataset_dir=scratch.dataset, raw_dir=scratch.raw), str(path))
                self.assertIsNotNone(scratch.guard.forbidden_reason(path), str(path))
                with self.assertRaises(SystemExit) as caught:
                    scratch.guard.check_output_path(path)
                self.assertIn("refusing to write", str(caught.exception))

    def test_scratch_neighbours_allowed(self):
        """Names that only look like the scratch folders, normal folders and a `..` that leaves a folder are allowed."""
        with SUPPORT.scratch_protected() as scratch:
            allowed = [scratch.root / "ds_scratch2" / "x", scratch.root / "raw_scratch2" / "x", scratch.root / "silver" / "x.parquet",
                       str(scratch.raw / ".." / "silver" / "x"), str(scratch.dataset / ".." / "out" / "x"), scratch.root / "data" / "raw2" / "x",
                       scratch.root / "data" / "silver" / "x", "\\\\?\\" + str(scratch.root / "ds_scratch2" / "x"),
                       "\\\\localhost\\" + scratch.root.drive[0] + "$" + str(scratch.root)[2:] + "\\ds_scratch2\\x"]
            for path in allowed:
                self.assertIsNone(scratch.guard.forbidden_reason(path), str(path))
                scratch.guard.check_output_path(path)

    def test_data_raw_outside_the_repo_refused(self):
        """Any path with consecutive parts `data` then `raw` is refused even when it is not the repo's raw folder (kills a dropped parts clause)."""
        with SUPPORT.scratch_protected() as scratch:
            for path in (scratch.root / "elsewhere" / "data" / "raw" / "x", scratch.root / "e" / "DATA" / "Raw" / "x", scratch.root / "data" / "raw",
                         "\\\\?\\" + str(scratch.root / "e" / "data" / "raw" / "x"), str(scratch.root / "e" / "data" / "raw ") + "\\x",
                         str(scratch.root / "e" / "data" / "raw.") + "\\x", str(scratch.root / "e" / "data" / "raw::$DATA") + "\\x"):
                self.assertEqual(scratch.guard.forbidden_reason(path), "data/raw/", str(path))

    def test_links_into_protected_folders_refused(self):
        """A symlink or junction that points into a protected folder is refused through its resolved target (kills realpath replaced by abspath)."""
        with SUPPORT.scratch_protected() as scratch:
            for target, label in ((scratch.raw, "raw"), (scratch.dataset, "dataset")):
                link = scratch.root / f"link_to_{label}"
                if not make_link(link, target):
                    self.skipTest("this OS refused to create both a symlink and a junction (needs privileges or a non-NTFS volume)")
                self.assertIsNotNone(scratch.guard.forbidden_reason(link / "x.parquet"), label)
                self.assertIsNotNone(scratch.guard.forbidden_reason(str(link / "sub" / ".." / "x.parquet")), label)
                self.assertEqual(SUPPORT.scratch_files(scratch), [])

    def test_real_defaults_by_string_only(self):
        """With the real constants, the extended, loopback-UNC and plain forms of the dataset folder and of data/raw are refused; look-alikes are allowed (no file is written)."""
        refused = [
            ROOT_DIR / "data" / "raw" / "x.parquet", ROOT_DIR / "data" / "raw", str(ROOT_DIR / "data" / "silver" / ".." / "raw" / "x.parquet"),
            str(ROOT_DIR / "data" / "silver" / ".." / ".." / "data" / "raw" / "deep" / "x"), str(ROOT_DIR / "DATA" / "Raw" / "x.parquet"),
            "\\\\?\\" + str(ROOT_DIR / "data" / "raw" / "x"), "\\\\localhost\\" + str(ROOT_DIR)[0] + "$" + str(ROOT_DIR)[2:] + "\\data\\raw\\x",
            "D:/Cyber_DataSet/x.parquet", "D:\\Cyber_DataSet\\sub\\x.parquet", "d:/cyber_dataset/x.parquet", "D:/Cyber_DataSet/other/../x.parquet",
            "D:/Cyber_DataSet", "\\\\?\\D:\\Cyber_DataSet\\x", "\\\\?\\d:\\cyber_dataset\\x", "\\\\?\\UNC\\localhost\\D$\\Cyber_DataSet\\x",
            "\\\\?\\UNC\\127.0.0.1\\D$\\Cyber_DataSet\\x", "\\\\localhost\\D$\\Cyber_DataSet\\x", "\\\\127.0.0.1\\D$\\Cyber_DataSet\\x",
            "\\\\LOCALHOST\\d$\\cyber_dataset\\sub\\..\\x",
        ]
        for path in refused:
            self.assertIsNotNone(GUARD.forbidden_reason(path), str(path))
        allowed = [
            ROOT_DIR / "data" / "silver" / "hosts.parquet", ROOT_DIR / "data" / "gold" / "accounts.parquet", ROOT_DIR / "data" / "rawish" / "x.parquet",
            ROOT_DIR / "data" / "raw2" / "x.parquet", ROOT_DIR / "data" / "raw_copy" / "x.parquet", str(ROOT_DIR / "data" / "raw" / ".." / "silver" / "x.parquet"),
            "D:/Cyber_DataSet2/x.parquet", "D:/Cyber_DataSet_copy/x.parquet", "D:/other/x.parquet", "\\\\?\\D:\\Cyber_DataSet2\\x",
            "\\\\localhost\\D$\\Cyber_DataSet2\\x", Path(tempfile.gettempdir()) / "scratch.parquet",
        ]
        for path in allowed:
            self.assertIsNone(GUARD.forbidden_reason(path), str(path))

    def test_constants_and_no_switch(self):
        """The constants are the documented folders and the guard offers no environment variable or flag to disable or redirect it."""
        self.assertEqual(GUARD.DATASET_DIR, "D:/Cyber_DataSet/")
        self.assertEqual(GUARD.RAW_DIR, ROOT_DIR / "data" / "raw")
        source = (SCRIPTS / "path_guard.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"environ|getenv|argparse|argv")
        for stage in sorted((ROOT_DIR / "pipeline").glob("*.py")):
            self.assertNotRegex(stage.read_text(encoding="utf-8"), r"DATASET_DIR\s*=|RAW_DIR\s*=|guard\.(DATASET_DIR|RAW_DIR)", stage.name)


class RealFoldersNotTouchedTests(unittest.TestCase):
    """The tests themselves never write into the real protected folders."""

    def test_real_raw_folder_unchanged(self):
        """The real data/raw folder has the same file names and modification time as when this module started."""
        self.assertEqual(raw_snapshot(), RAW_BEFORE)

    def test_no_test_module_writes_to_the_dataset_folder(self):
        """No line of any scripts/test_*.py combines the literal dataset folder name with a write, output, report or run call."""
        name = "cyber_" + "dataset"
        writers = re.compile(r"write_text|write_bytes|\.touch|\bopen\(|mkdir|COPY|--out|--report|run_cli|run_main|run_signals|run_stage|\.main\(|subprocess|shutil|unlink|rmtree")
        for test_file in sorted(SCRIPTS.glob("test_*.py")):
            for number, line in enumerate(test_file.read_text(encoding="utf-8").splitlines(), 1):
                if name in line.lower():
                    self.assertIsNone(writers.search(line), f"{test_file.name}:{number}: {line.strip()}")


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
    """build_spread_sample.py refuses the same paths (run in process against scratch protected folders)."""

    def test_sample_builder_refuses_protected_output(self):
        """The sample builder exits with a refusal for every forbidden form and writes nothing."""
        with SUPPORT.scratch_protected() as scratch:
            src = scratch.root / "srcdir" / "src.jsonl"
            src.parent.mkdir()
            src.write_text('{"a": 1}\n' * 50, encoding="utf-8")
            with mock.patch.object(SAMPLE, "path_guard", scratch.guard):
                for target in SUPPORT.forbidden_targets(scratch, "probe.jsonl"):
                    argv = ["--src", str(src), "--out", str(target), "--positions", "2", "--lines", "2"]
                    with self.assertRaises(SystemExit) as caught:
                        SAMPLE.main(argv)
                    self.assertIn("refusing to write", str(caught.exception), str(target))
                    self.assertEqual(SUPPORT.scratch_files(scratch), [], str(target))

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
