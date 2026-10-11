"""Shared output-path guard: refuse any write target under data/raw/ or the source dataset folder."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = "D:/Cyber_DataSet/"  # source dataset folder, read only


def resolved_parts(path):
    """Return the lower-cased parts of a path after making it absolute and resolving `..`."""
    return [part.lower() for part in Path(os.path.realpath(os.path.abspath(str(path)))).parts]


def is_under(path, folder):
    """Return True when path equals or lies inside folder (case-insensitive, `..` resolved)."""
    target, base = resolved_parts(path), resolved_parts(folder)
    return target[:len(base)] == base


def forbidden_reason(path):
    """Return why an output path is forbidden, or None when it is allowed."""
    parts = resolved_parts(path)
    if is_under(path, ROOT / "data" / "raw") or any(parts[i] == "data" and parts[i + 1] == "raw" for i in range(len(parts) - 1)):
        return "data/raw/"
    if is_under(path, DATASET_DIR):
        return "the source dataset folder " + DATASET_DIR
    return None


def check_output_path(path):
    """Exit with a message when path is under data/raw/ or the source dataset folder."""
    reason = forbidden_reason(path)
    if reason:
        sys.exit(f"refusing to write under {reason}: {path}")


def choose_report_path(output_path, default_output, report_arg, default_report, stage):
    """Pick the report file: --report if given; the committed default when output is the default; else next to the scratch output."""
    if report_arg:
        return Path(report_arg)
    if Path(os.path.abspath(str(output_path))).resolve() == Path(os.path.abspath(str(default_output))).resolve():
        return Path(default_report)
    return Path(os.path.abspath(str(output_path))).parent / f"{stage}_stage_report.md"


def use_utf8_output():
    """Switch stdout and stderr to UTF-8 with replacement so a report never fails on a non-ASCII name."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
