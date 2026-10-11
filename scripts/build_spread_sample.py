"""Build a seek-spread sample: N evenly spaced byte positions, K complete lines after each."""
import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import path_guard  # noqa: E402


def is_under(path, folder):
    """Return True when path is inside folder (both resolved)."""
    path = Path(os.path.abspath(path)).resolve()
    folder = Path(os.path.abspath(folder)).resolve()
    return folder == path or folder in path.parents


def check_out_path(src, out):
    """Refuse output paths under data/raw/ or under the source dataset folder."""
    out_abs = Path(os.path.abspath(out)).resolve()
    parts = [p.lower() for p in out_abs.parts]
    for i in range(len(parts) - 1):
        if parts[i] == "data" and parts[i + 1] == "raw":
            sys.exit("refusing to write under data/raw/: " + str(out_abs))
    if is_under(out_abs, Path(src).resolve().parent):
        sys.exit("refusing to write under the source dataset folder: " + str(out_abs))


def make_positions(size, positions, seed):
    """Return evenly spaced offsets, each jittered inside the first half of its stride (first is 0)."""
    rng = random.Random(seed)
    stride = size // positions
    offsets = []
    for i in range(positions):
        jitter = 0 if i == 0 else rng.randrange(0, stride // 2)
        offsets.append(i * stride + jitter)
    return offsets


def read_lines_at(handle, offset, lines):
    """Seek to offset, skip to the next newline (unless at 0), and return up to `lines` complete lines."""
    handle.seek(offset)
    if offset > 0:
        handle.readline()
    result = []
    while len(result) < lines:
        line = handle.readline()
        if not line:
            break
        if not line.endswith(b"\n"):
            break
        result.append(line)
    return result


def main():
    """Parse arguments, build the sample, and print a summary."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--positions", type=int, default=1000)
    ap.add_argument("--lines", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    check_out_path(args.src, args.out)
    path_guard.check_output_path(args.out)
    size = os.path.getsize(args.src)
    offsets = make_positions(size, args.positions, args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with open(args.src, "rb") as src, open(args.out, "wb") as out:
        for offset in offsets:
            got = read_lines_at(src, offset, args.lines)
            for line in got:
                out.write(line)
            total += len(got)
    meta = {"src_bytes": size, "positions": args.positions, "lines": args.lines,
            "seed": args.seed, "rows": total, "first_offset": offsets[0], "last_offset": offsets[-1]}
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
