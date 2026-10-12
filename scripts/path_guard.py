"""Shared output-path guard: an allowlist that refuses any write target it cannot prove is outside data/raw/ and the source dataset folder.

Policy (nothing in production turns it off; the folder constants are injectable for tests only):
1. A path is accepted only if it is a plain relative path, a rooted path (one leading slash) or a plain `X:/...` drive-letter absolute path.
2. Refused outright, with no stripping or rewriting of spellings: `\\?\`, `\\.\`, `\??\`, `//?/`, `//./` and every other leading double slash (UNC
   `\\host\share`, loopback and IP/IPv6-literal hosts), GLOBALROOT and Volume{...} forms, drive-relative `X:name`, any `:` other than the drive
   colon (alternate data streams such as `D:/folder:evil` or `::$DATA`), NUL and other control characters, the Windows-invalid characters `<>"|?*`, and
   any part ending in a dot, space, no-break space or zero-width / format character.
3. An accepted path is resolved (`..`, junctions and symlinks followed) and refused when it is inside data/raw/ or the source dataset folder
   (case-insensitive compare of resolved parts; any `data/raw` part pair is also refused), or when any existing ancestor of the target is the same
   file-system object as a protected folder (`os.path.samefile`), so an alias with a different spelling is caught.
Network-share and device-namespace outputs are deliberately unsupported: write to a local drive path instead.
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = "D:/Cyber_DataSet/"  # source dataset folder, read only
RAW_DIR = ROOT / "data" / "raw"  # raw layer, read only
UNSUPPORTED = "unsupported path form"  # prefix of every allowlist refusal reason
DRIVE_ABSOLUTE = re.compile(r"^[A-Za-z]:/")
BAD_CHARACTERS = re.compile(r'[\x00-\x1f<>"|?*]')
VOLUME_PART = re.compile(r"^volume\{", re.IGNORECASE)


def part_problem(part):
    """Return why one path part is not allowed (trailing dot, space or invisible character; device names), or None."""
    if part in ("", ".", ".."):
        return None
    if part[-1] in ". " or unicodedata.category(part[-1]) in ("Zs", "Zl", "Zp", "Cf", "Cc"):
        return "a part ends in a dot, space or invisible character: " + repr(part)
    if part.lower() == "globalroot" or VOLUME_PART.match(part):
        return "a device or volume namespace part: " + repr(part)
    return None


def plain_path_problem(path):
    """Return why a path is outside the allowlist (plain relative, rooted or plain drive-letter absolute), or None when it fits."""
    text = str(path).replace("\\", "/")
    if text.startswith("//"):
        return "network share, extended or device namespace (leading double slash)"
    if BAD_CHARACTERS.search(text):
        return "contains a control or Windows-invalid character"
    rest = text
    if len(text) >= 2 and text[1] == ":":
        if not DRIVE_ABSOLUTE.match(text):
            return "drive-relative or malformed drive prefix"
        rest = text[2:]
    if ":" in rest:
        return "contains a colon other than the drive-letter colon (alternate data stream or namespace)"
    for part in rest.split("/"):
        problem = part_problem(part)
        if problem:
            return problem
    return None


def resolved_parts(path):
    """Return the lower-cased parts of a path after making it absolute and resolving `..`, junctions and links."""
    return [part.lower() for part in Path(os.path.realpath(os.path.abspath(str(path)))).parts]


def is_under(path, folder):
    """Return True when path equals or lies inside folder (case-insensitive, resolved)."""
    target, base = resolved_parts(path), resolved_parts(folder)
    return target[:len(base)] == base


def same_object_ancestor(path, folder):
    """Return True when the path or any existing ancestor of it is the same file-system object as folder (alias-proof)."""
    if not os.path.exists(folder):
        return False
    current = Path(os.path.realpath(os.path.abspath(str(path))))
    for candidate in (current, *current.parents):
        try:
            if os.path.exists(candidate) and os.path.samefile(candidate, folder):
                return True
        except OSError:
            continue
    return False


def forbidden_reason(path, dataset_dir=None, raw_dir=None):
    """Return why an output path is refused, or None when it is allowed; the folders default to the module constants."""
    dataset_dir = DATASET_DIR if dataset_dir is None else dataset_dir
    raw_dir = RAW_DIR if raw_dir is None else raw_dir
    problem = plain_path_problem(path)
    if problem:
        return f"{UNSUPPORTED} ({problem})"
    try:
        parts = resolved_parts(path)
        in_raw = is_under(path, raw_dir) or same_object_ancestor(path, raw_dir)
        in_dataset = is_under(path, dataset_dir) or same_object_ancestor(path, dataset_dir)
    except (OSError, ValueError) as error:
        return f"{UNSUPPORTED} (cannot be resolved: {type(error).__name__})"
    if in_raw or any(parts[i] == "data" and parts[i + 1] == "raw" for i in range(len(parts) - 1)):
        return "data/raw/"
    if in_dataset:
        return "the source dataset folder " + str(dataset_dir)
    return None


def check_output_path(path):
    """Exit with a refusal message when the path is outside the allowlist or inside data/raw/ or the source dataset folder."""
    reason = forbidden_reason(path)
    if reason is None:
        return
    if reason.startswith(UNSUPPORTED):
        sys.exit(f"refusing to write to {path}: {reason}")
    sys.exit(f"refusing to write under {reason}: {path}")


def choose_report_path(output_path, default_output, report_arg, default_report, stage):
    """Pick the report file (--report; the committed default for the default output; else beside the scratch output); refuses a bad output path first."""
    check_output_path(output_path)
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
