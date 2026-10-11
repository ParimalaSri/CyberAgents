"""Lint a sales email (subject + body): length, subject style, calls to action, spammy patterns."""
import argparse
import json
import re
import sys
from pathlib import Path

BANNED_FILE = Path(__file__).resolve().parents[2] / "outreach-draft" / "references" / "banned_phrases.txt"
SUBJECT_MAX_WORDS = 8
SUBJECT_MAX_CHARS = 60
LONG_SENTENCE_WORDS = 25
LIMITS = {"first": 120, "followup": 80, "breakup": 50, "reply": 100}


def load_banned():
    """Return banned phrases (lowercase) shared with the outreach-draft skill."""
    if not BANNED_FILE.exists():
        return []
    lines = BANNED_FILE.read_text(encoding="utf-8").splitlines()
    return [ln.strip().lower() for ln in lines if ln.strip() and not ln.startswith("#")]


def check_subject(subject):
    """Return problems with the subject line."""
    problems = []
    if len(subject.split()) > SUBJECT_MAX_WORDS or len(subject) > SUBJECT_MAX_CHARS:
        problems.append(f"subject too long (max {SUBJECT_MAX_WORDS} words / {SUBJECT_MAX_CHARS} chars)")
    if subject.isupper() and len(subject) > 3:
        problems.append("subject is all caps")
    if "!" in subject:
        problems.append("subject contains '!'")
    return problems


def check_body(body, kind):
    """Return problems with the body text for the given email kind."""
    problems = []
    words = body.split()
    limit = LIMITS[kind]
    if len(words) > limit:
        problems.append(f"body has {len(words)} words, limit for '{kind}' is {limit}")
    if body.count("!") > 0:
        problems.append("body contains '!'")
    if len(re.findall(r"https?://", body)) > 1:
        problems.append("more than one link")
    if len(re.findall(r"\b[A-Z]{4,}\b", body)) > 0:
        problems.append("ALL-CAPS word found")
    ctas = body.count("?")
    if ctas == 0:
        problems.append("no question / call to action")
    elif ctas > 2:
        problems.append(f"{ctas} questions: use one clear call to action")
    for sentence in re.split(r"[.?]\s+", body):
        if len(sentence.split()) > LONG_SENTENCE_WORDS:
            problems.append(f"sentence over {LONG_SENTENCE_WORDS} words: '{sentence[:40]}...'")
    lowered = f"{body}".lower()
    problems += [f"banned phrase: '{p}'" for p in load_banned() if p in lowered]
    return problems


def main():
    """Read the email JSON (subject, body), print problems, exit 1 if any."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="JSON file with subject and body, or - for stdin")
    parser.add_argument("--kind", choices=sorted(LIMITS), default="first")
    args = parser.parse_args()

    raw = sys.stdin.read() if args.email == "-" else Path(args.email).read_text(encoding="utf-8")
    email = json.loads(raw)
    problems = check_subject(email.get("subject", "")) + check_body(email.get("body", ""), args.kind)
    if problems:
        print("FAIL")
        print("\n".join(f"- {p}" for p in problems))
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
