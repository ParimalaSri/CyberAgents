"""Reference matcher for the denylist files in context/ (normaliser, exact, prefix, pattern, keyword, cert defaults)."""
import fnmatch
import ipaddress
import re
from pathlib import Path

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context"
LEGAL_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "co", "corp", "corporation", "gmbh", "sa", "sas", "srl", "bv", "ag",
    "plc", "pte", "pty", "lp", "llp", "company", "private", "ltee", "sau", "nv", "ab", "as", "kk", "sp", "zoo",
}
MIN_PREFIX_CHARS = 4


def normalise(name):
    """Lowercase, strip punctuation, collapse spaces, drop trailing legal-suffix words."""
    if name is None:
        return ""
    text = re.sub(r"[^\w]+", " ", str(name).lower().replace("&", " and "), flags=re.UNICODE)
    text = text.replace("_", " ")
    words = text.split()
    while len(words) > 1 and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def read_entries(path):
    """Return the non-comment, non-blank lines of a rules file."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def load_exact(path=None):
    """Return the set of normalised exact-match denylist names."""
    return {normalise(e) for e in read_entries(path or CONTEXT_DIR / "denylist.txt")}


def load_prefixes(path=None):
    """Return normalised prefix families, rejecting any shorter than MIN_PREFIX_CHARS."""
    result = [normalise(e) for e in read_entries(path or CONTEXT_DIR / "denylist_prefixes.txt")]
    short = [p for p in result if len(p) < MIN_PREFIX_CHARS]
    if short:
        raise ValueError("prefix entries under 4 characters must be exact-only: " + ", ".join(short))
    return result


KEYWORD_SCOPES = ("org",)
KEYWORD_FIELDS = ("org", "isp")


class Keyword(str):
    """A normalised keyword phrase (a str) that also carries its field scope: 'any' (org or isp) or 'org' (org text only)."""

    scope = "any"


def parse_keyword_entry(entry):
    """Parse one keyword line, 'phrase' or 'scope: phrase', into a Keyword; reject unknown scopes."""
    scope = "any"
    text = entry
    if ":" in entry:
        head, _, rest = entry.partition(":")
        scope = head.strip().lower()
        text = rest
        if scope not in KEYWORD_SCOPES:
            raise ValueError("unknown keyword scope " + repr(scope) + " in line: " + entry)
    keyword = Keyword(normalise(text))
    keyword.scope = scope
    return keyword


def load_keywords(path=None):
    """Return Keyword phrases (whole-word match rules, optional 'org:' scope), de-duplicated by phrase and scope in file order."""
    result = []
    seen = set()
    for entry in read_entries(path or CONTEXT_DIR / "denylist_keywords.txt"):
        keyword = parse_keyword_entry(entry)
        if keyword and (str(keyword), keyword.scope) not in seen:
            seen.add((str(keyword), keyword.scope))
            result.append(keyword)
    return result


def load_cert_defaults(path=None):
    """Return the set of normalised default certificate organisation names."""
    return {normalise(e) for e in read_entries(path or CONTEXT_DIR / "cert_default_names.txt")}


def matches_prefix(normalised, prefixes):
    """Return the first prefix family that matches at a word boundary, else None."""
    for prefix in prefixes:
        if normalised == prefix or normalised.startswith(prefix + " "):
            return prefix
    return None


def matches_keyword(normalised, keywords, field="org"):
    """Return the first keyword whose words appear as a whole-word run in the text of `field` ('org' or 'isp'), else None; org-scoped keywords only match field 'org'."""
    if field not in KEYWORD_FIELDS:
        raise ValueError("field must be one of " + ", ".join(KEYWORD_FIELDS))
    padded = " " + normalised + " "
    for keyword in keywords:
        if getattr(keyword, "scope", "any") == "org" and field != "org":
            continue
        if " " + keyword + " " in padded:
            return keyword
    return None


def matches_pattern(value, patterns):
    """Return True if value (a name or an IP address) matches a CIDR or glob pattern."""
    if value is None:
        return False
    text = str(value).strip().lower()
    for pattern in patterns:
        if text == pattern.lower():
            return True
        if "/" in pattern and re.match(r"^[0-9a-f:.]+/\d+$", pattern):
            try:
                if ipaddress.ip_address(text) in ipaddress.ip_network(pattern, strict=False):
                    return True
            except ValueError:
                continue
        elif fnmatch.fnmatchcase(text, pattern.lower()):
            return True
    return False
