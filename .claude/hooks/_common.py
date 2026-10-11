"""Shared helpers for Claude Code hook scripts."""
import json
import subprocess
import sys

PROTECTED_BRANCHES = {"main", "dev", "prod"}


def read_event():
    """Parse the hook event JSON that Claude Code sends on stdin."""
    sys.stdin.reconfigure(encoding="utf-8")
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def current_branch(cwd):
    """Return the git branch name for cwd, or '' if not a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def block(message):
    """Block the tool call: message goes to Claude via stderr, exit code 2."""
    print(f"BLOCKED: {message}", file=sys.stderr)
    sys.exit(2)
