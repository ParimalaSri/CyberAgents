"""Tests for protect_files.py: real writes to data/raw stay blocked, harmless mentions pass."""
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "protect_files.py"

# (description, shell command, should be blocked)
BASH_CASES = [
    ("script body lists the protected path", "cat > scripts/b.py <<'EOF'\nPROTECTED = ['data/raw']\nEOF\npython scripts/b.py --out data/sample/s.jsonl", False),
    ("heredoc comment mentions cp", "cat > scripts/a.py <<'EOF'\n# cp is unused; data/raw is read only\nEOF", False),
    ("plain read", "ls data/raw && head -n 3 data/raw/sample_100k.jsonl", False),
    ("cp out of raw", "cp data/raw/a.jsonl /tmp/a.jsonl", False),
    ("arrow in a message", "python q.py data/raw/x.jsonl --note 'a -> b'", False),
    ("rm in raw", "rm data/raw/sample_100k.jsonl", True),
    ("redirect into raw", "echo x > data/raw/new.txt", True),
    ("append into raw", "echo x >> data/raw/new.txt", True),
    ("touch in raw", "touch data/raw/new.txt", True),
    ("mv from raw", "mv data/raw/a.jsonl /tmp/", True),
    ("cp into raw", "cp /tmp/a.jsonl data/raw/", True),
    ("tee into raw", "cat x | tee data/raw/y.txt", True),
    ("sed -i in raw", "sed -i s/a/b/ data/raw/y.txt", True),
    ("windows slashes rm", "rm data\\raw\\a.jsonl", True),
    ("cat env", "cat .env", True),
    ("env example ok", "cat .env.example", False),
]

TOOL_CASES = [
    ("write tool into raw", "Write", "D:/CyberAgents/data/raw/x.csv", True),
    ("read tool in raw", "Read", "D:/CyberAgents/data/raw/x.csv", False),
    ("write tool into sample", "Write", "D:/CyberAgents/data/sample/x.jsonl", False),
    ("read tool on env", "Read", "D:/CyberAgents/.env", True),
]


def run_hook(event):
    """Send an event to the hook and return its exit code (2 means blocked)."""
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True)
    return result.returncode


def main():
    """Run all cases, print any mismatch, and exit 1 if any failed."""
    failures = 0
    for name, cmd, should_block in BASH_CASES:
        blocked = run_hook({"tool_name": "Bash", "tool_input": {"command": cmd}}) == 2
        if blocked != should_block:
            failures += 1
            print(f"FAIL bash: {name}: blocked={blocked}, expected {should_block}")
    for name, tool, path, should_block in TOOL_CASES:
        blocked = run_hook({"tool_name": tool, "tool_input": {"file_path": path}}) == 2
        if blocked != should_block:
            failures += 1
            print(f"FAIL tool: {name}: blocked={blocked}, expected {should_block}")
    total = len(BASH_CASES) + len(TOOL_CASES)
    print(f"{total - failures}/{total} cases passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
