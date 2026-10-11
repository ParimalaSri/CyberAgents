"""PreToolUse hook: no edits or git history changes on main, dev or prod."""
import os
import re
import sys

from _common import PROTECTED_BRANCHES, block, current_branch, read_event

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
GIT_WRITE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?(commit|merge|rebase|reset|cherry-pick|am|push)\b")
PUSH_TARGET = re.compile(r"\bgit\s+push\b.*\b(main|dev|prod)\b")


def main():
    """Block writes while on a protected branch, and pushes aimed at one."""
    event = read_event()
    tool, args = event.get("tool_name", ""), event.get("tool_input", {})
    cwd = event.get("cwd") or os.getcwd()
    branch = current_branch(cwd)

    if tool in WRITE_TOOLS and branch in PROTECTED_BRANCHES:
        block(f"On protected branch '{branch}'. Create feat/<role>/<task> from dev first.")

    if tool == "Bash":
        cmd = args.get("command", "")
        if GIT_WRITE.search(cmd) and branch in PROTECTED_BRANCHES:
            block(f"git history changes are not allowed on '{branch}'. Use a feature branch.")
        if PUSH_TARGET.search(cmd):
            block("Pushing to main/dev/prod is not allowed. Push a feature branch and open a PR.")
    sys.exit(0)


if __name__ == "__main__":
    main()
