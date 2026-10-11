"""Shared output-path guard: refuse any write target under data/raw/ or the source dataset folder."""
import os
import re
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = "D:/Cyber_DataSet/"  # source dataset folder, read only
RAW_DIR = ROOT / "data" / "raw"  # raw layer, read only
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "[::1]", "0:0:0:0:0:0:0:1")  # UNC host names that mean this machine


def normalise_windows_path(path):
    """Rewrite extended, device and loopback-UNC forms of a path to the plain drive form, and drop NTFS stream suffixes."""
    text = str(path).replace("\\", "/")
    lowered = text.lower()
    if lowered.startswith("//?/unc/") or lowered.startswith("//./unc/"):
        text = "//" + text[8:]
    elif lowered.startswith("//?/") or lowered.startswith("//./"):
        text = text[4:]
    pieces = text.split("/")
    if text.startswith("//") and len(pieces) > 3 and pieces[2] != "":
        host, share = pieces[2].lower(), pieces[3]
        local = LOCAL_HOSTS + (socket.gethostname().lower(),)
        if host in local and len(share) == 2 and share[1] == "$" and share[0].isalpha():
            text = share[0] + ":/" + "/".join(pieces[4:])
    text = re.sub(r"::\$[^/]*", "", text)
    return "/".join(piece if piece in (".", "..") else piece.rstrip(". ") for piece in text.split("/"))


def resolved_parts(path):
    """Return the lower-cased parts of a path after normalising Windows forms, making it absolute and resolving `..` and links."""
    return [part.lower() for part in Path(os.path.realpath(os.path.abspath(normalise_windows_path(path)))).parts]


def is_under(path, folder):
    """Return True when path equals or lies inside folder (case-insensitive, `..` resolved)."""
    target, base = resolved_parts(path), resolved_parts(folder)
    return target[:len(base)] == base


def forbidden_reason(path, dataset_dir=None, raw_dir=None):
    """Return why an output path is forbidden, or None when it is allowed; the folders default to the module constants."""
    dataset_dir = DATASET_DIR if dataset_dir is None else dataset_dir
    raw_dir = RAW_DIR if raw_dir is None else raw_dir
    parts = resolved_parts(path)
    if is_under(path, raw_dir) or any(parts[i] == "data" and parts[i + 1] == "raw" for i in range(len(parts) - 1)):
        return "data/raw/"
    if is_under(path, dataset_dir):
        return "the source dataset folder " + str(dataset_dir)
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
