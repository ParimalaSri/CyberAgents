"""PreToolUse hook: never touch .env, never modify data/raw/."""
import re
import sys
from pathlib import PurePath

from _common import block, read_event

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
ENV_IN_COMMAND = re.compile(r"(?<![\w.])\.env(?!\.example)(?![\w])")
RAW = r"data/raw"
# A write counts only when data/raw is the TARGET, on the same line as the verb or redirect.
RAW_WRITE = re.compile(
    rf"(?:\b(?:rm|tee|truncate|touch|sed\s+-i|dd\s+of=)\b[^\n|;&]*{RAW})"
    rf"|(?:>>?\s*\S*{RAW})"
    rf"|(?:\bmv\b\s+\S*{RAW})"
    rf"|(?:\b(?:cp|mv)\b[^\n|;&]*\s\S*{RAW}\S*\s*(?:$|[|;&\n]))"
)


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
        if RAW_WRITE.search(cmd.replace("\\", "/")):
            block("Shell commands may not modify data/raw/.")
    sys.exit(0)


if __name__ == "__main__":
    main()
