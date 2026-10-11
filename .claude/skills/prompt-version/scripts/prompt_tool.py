"""Manage versioned prompts: list versions, create the next version (never overwrite), diff two versions."""
import argparse
import difflib
import re
import sys
from datetime import date
from pathlib import Path

PROMPTS_DIR = Path("prompts")
VERSION_FILE = re.compile(r"^v(\d+)\.md$")
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def list_versions(feature):
    """Return the existing version numbers of a feature, ascending."""
    folder = PROMPTS_DIR / feature
    if not folder.is_dir():
        return []
    nums = [int(m.group(1)) for p in folder.iterdir() if (m := VERSION_FILE.match(p.name))]
    return sorted(nums)


def body_of(path):
    """Return a prompt file's text without its front matter."""
    return FRONT_MATTER.sub("", path.read_text(encoding="utf-8"), count=1)


def cmd_list(args):
    """Print the versions of a feature."""
    versions = list_versions(args.feature)
    print(f"{args.feature}: " + (", ".join(f"v{n}" for n in versions) or "no versions yet"))


def cmd_new(args):
    """Create the next version file, copying the chosen parent's body; refuses to overwrite."""
    versions = list_versions(args.feature)
    nxt = (versions[-1] + 1) if versions else 1
    parent = args.parent or (versions[-1] if versions else None)
    body = "TODO: write the prompt here.\n"
    if parent is not None:
        body = body_of(PROMPTS_DIR / args.feature / f"v{parent}.md")
    header = (
        f"---\nversion: v{nxt}\nfeature: {args.feature}\nparent: {'v' + str(parent) if parent else 'none'}\n"
        f"date: {date.today()}\nchange: {args.change}\n---\n"
    )
    target = PROMPTS_DIR / args.feature / f"v{nxt}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(target, "x", encoding="utf-8") as handle:
            handle.write(header + body)
    except FileExistsError:
        sys.exit(f"{target} already exists; prompts are never overwritten.")
    print(f"created {target} (parent: {parent})")


def cmd_diff(args):
    """Print a unified diff between two versions of a feature's prompt."""
    a = (PROMPTS_DIR / args.feature / f"{args.a}.md").read_text(encoding="utf-8").splitlines()
    b = (PROMPTS_DIR / args.feature / f"{args.b}.md").read_text(encoding="utf-8").splitlines()
    diff = list(difflib.unified_diff(a, b, args.a, args.b, lineterm=""))
    print("\n".join(diff) if diff else "no differences")


def main():
    """Parse the subcommand and dispatch."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list")
    p_list.add_argument("feature")
    p_list.set_defaults(func=cmd_list)
    p_new = sub.add_parser("new")
    p_new.add_argument("feature")
    p_new.add_argument("--change", required=True, help="one line: what changed and why")
    p_new.add_argument("--parent", type=int, help="version number to copy from (default: latest)")
    p_new.set_defaults(func=cmd_new)
    p_diff = sub.add_parser("diff")
    p_diff.add_argument("feature")
    p_diff.add_argument("a", help="e.g. v1")
    p_diff.add_argument("b", help="e.g. v2")
    p_diff.set_defaults(func=cmd_diff)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
