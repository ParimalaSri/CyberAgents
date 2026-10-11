"""Validate an outreach draft (JSON) for schema, length, banned phrases and grounding in account data."""
import argparse
import json
import sys
from pathlib import Path

REFERENCES = Path(__file__).resolve().parent.parent / "references"
REQUIRED = ("subject", "body", "signals_used", "channel")
CHANNELS = {"email", "linkedin"}
MAX_WORDS = {"email": 120, "linkedin": 60}


def load_banned():
    """Return the banned phrases (lowercase) from references/banned_phrases.txt."""
    lines = (REFERENCES / "banned_phrases.txt").read_text(encoding="utf-8").splitlines()
    return [ln.strip().lower() for ln in lines if ln.strip() and not ln.startswith("#")]


def check_grounding(signals_used, account):
    """Return problems for any signal that is not present in the account data."""
    problems = []
    for item in signals_used:
        key, _, value = str(item).partition("=")
        if key not in account:
            problems.append(f"signal '{item}': column '{key}' not in account data")
        elif value and str(account[key]) != value:
            problems.append(f"signal '{item}': account has {key}={account[key]}")
    return problems


def validate(draft, account):
    """Return a list of problems with the draft (empty means valid)."""
    problems = [f"missing field '{f}'" for f in REQUIRED if f not in draft]
    if problems:
        return problems
    if draft["channel"] not in CHANNELS:
        problems.append(f"channel must be one of {sorted(CHANNELS)}")
    words = len(str(draft["body"]).split())
    limit = MAX_WORDS.get(draft["channel"], 120)
    if words > limit:
        problems.append(f"body has {words} words, limit is {limit}")
    text = f"{draft['subject']} {draft['body']}".lower()
    problems += [f"banned phrase: '{p}'" for p in load_banned() if p in text]
    if not draft["signals_used"]:
        problems.append("signals_used is empty: a draft must cite at least one signal")
    if account:
        problems += check_grounding(draft["signals_used"], account)
    return problems


def main():
    """Read the draft (and optional account JSON), print problems, exit 1 if any."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", help="draft JSON file, or - for stdin")
    parser.add_argument("--account", help="account row as a JSON file, enables grounding checks")
    args = parser.parse_args()

    raw = sys.stdin.read() if args.draft == "-" else Path(args.draft).read_text(encoding="utf-8")
    account = json.loads(Path(args.account).read_text(encoding="utf-8")) if args.account else None
    problems = validate(json.loads(raw), account)
    if problems:
        print("FAIL")
        print("\n".join(f"- {p}" for p in problems))
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
