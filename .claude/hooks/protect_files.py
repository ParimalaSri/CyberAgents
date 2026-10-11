"""PreToolUse hook: never touch .env, never modify data/raw/."""
import re
import sys
from pathlib import PurePath

from _common import block, read_event

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
ENV_IN_COMMAND = re.compile(r"(?<![\w.])\.env(?!\.example)(?![\w])")
RAW_WRITE_VERBS = re.compile(r"\b(rm|mv|cp|tee|truncate|sed\s+-i|dd|touch)\b|>")


def is_env_file(path):
    """Return True for .env and .env.* files, except .env.example."""
    name = PurePath(path.replace("\\", "/")).name
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def in_raw_data(path):
    """Return True if path points inside data/raw/."""
    return "data/raw/" in path.replace("\\", "/") + "/"


def main():
    """Inspect the pending tool call and block protected-path access."""
    event = read_event()
    tool, args = event.get("tool_name", ""), event.get("tool_input", {})
    path = args.get("file_path") or args.get("notebook_path") or ""

    if path and is_env_file(path):
        block(f"{path} is protected. Never read or edit .env files.")
    if path and tool in WRITE_TOOLS and in_raw_data(path):
        block("data/raw/ is read-only. Raw data must never be modified.")

    if tool == "Bash":
        cmd = args.get("command", "")
        if ENV_IN_COMMAND.search(cmd):
            block("Shell commands may not reference .env files.")
        if "data/raw" in cmd.replace("\\", "/") and RAW_WRITE_VERBS.search(cmd):
            block("Shell commands may not modify data/raw/.")
    sys.exit(0)


if __name__ == "__main__":
    main()
