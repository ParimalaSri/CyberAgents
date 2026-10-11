"""PostToolUse hook: append every file edit and shell command to a local JSONL log."""
import json
import os
import sys
from datetime import datetime, timezone

from _common import current_branch, read_event

LOG_PATH = os.path.join(".claude", "logs", "changes.jsonl")


def main():
    """Write one JSON line describing the tool call that just ran."""
    event = read_event()
    args = event.get("tool_input", {})
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": event.get("session_id"),
        "branch": current_branch(root),
        "tool": event.get("tool_name"),
        "target": args.get("file_path") or args.get("notebook_path") or args.get("command"),
    }
    log_file = os.path.join(root, LOG_PATH)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
