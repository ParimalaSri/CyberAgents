"""Test support: scratch protected folders so guard tests can never write into the real data/raw or the source dataset folder."""
import contextlib
import importlib.util
import io
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
GUARD_PATH = SCRIPTS / "path_guard.py"


def load_guard():
    """Import a fresh copy of the path guard module (so patching its constants never leaks to other tests)."""
    spec = importlib.util.spec_from_file_location("path_guard_scratch", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def scratch_protected():
    """Yield scratch stand-ins for the protected folders (guard patched to them) inside a temp directory that is deleted afterwards."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        dataset, raw = root / "ds_scratch", root / "raw_scratch"
        dataset.mkdir()
        raw.mkdir()
        guard = load_guard()
        guard.DATASET_DIR = dataset.as_posix() + "/"
        guard.RAW_DIR = raw
        yield SimpleNamespace(root=root, dataset=dataset, raw=raw, guard=guard)


def scratch_files(scratch):
    """Return every file under the scratch protected folders (a working guard leaves this empty)."""
    return sorted(str(p) for base in (scratch.dataset, scratch.raw) for p in base.rglob("*") if p.is_file())


def forbidden_targets(scratch, name="guard_probe.parquet"):
    """Return output paths that must all be refused: scratch raw and dataset folders in plain, `..`, upper-case, extended and loopback-UNC forms."""
    drive = scratch.dataset.drive
    unc = "\\\\localhost\\" + drive[0] + "$" + str(scratch.dataset)[len(drive):].replace("/", "\\") + "\\" + name
    return [
        scratch.raw / name,
        str(scratch.root / "silver" / ".." / "raw_scratch" / name),
        str(scratch.raw / name).upper(),
        scratch.dataset / name,
        str(scratch.dataset / "sub" / ".." / name),
        str(scratch.dataset / name).upper(),
        "\\\\?\\" + str(scratch.dataset / name),
        "\\\\?\\" + str(scratch.raw / name),
        unc,
    ]


def run_main(stage, argv, guard):
    """Call stage.main(argv) in process with its guard replaced by the scratch guard; return (exit value, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with mock.patch.object(stage, "load_guard", return_value=guard), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            stage.main([str(a) for a in argv])
        except SystemExit as stopped:
            code = stopped.code
    return code, out.getvalue(), err.getvalue()


def assert_stage_refuses(case, stage, input_args, with_report=True, safe_dir=None):
    """Assert the stage refuses every forbidden --output (and --report when it has one), exits with a refusal text and writes nothing anywhere."""
    with scratch_protected() as scratch:
        safe = Path(safe_dir or scratch.root) / "safe_out.parquet"
        for target in forbidden_targets(scratch):
            code, _, _ = run_main(stage, [*input_args, "--output", target], scratch.guard)
            case.assertIsInstance(code, str, str(target))
            case.assertIn("refusing to write", code, str(target))
            case.assertEqual(scratch_files(scratch), [], str(target))
            if with_report:
                code, _, _ = run_main(stage, [*input_args, "--output", safe, "--report", target], scratch.guard)
                case.assertIsInstance(code, str, "report " + str(target))
                case.assertIn("refusing to write", code, "report " + str(target))
                case.assertEqual(scratch_files(scratch), [], "report " + str(target))
                case.assertFalse(safe.exists(), "report " + str(target))
