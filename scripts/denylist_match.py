"""Reference matcher for the denylist files in context/ (normaliser, exact, prefix, pattern, keyword, cert defaults)."""
import fnmatch
import ipaddress
import re
import unicodedata
from pathlib import Path

CONTEXT_DIR = Path(__file__).resolve().parent.parent / "context"
LEGAL_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "co", "corp", "corporation", "gmbh", "sa", "sas", "srl", "bv", "ag",
    "plc", "pte", "pty", "lp", "llp", "company", "private", "ltee", "sau", "nv", "ab", "as", "kk", "sp", "zoo",
}
MIN_PREFIX_CHARS = 4


def fold_accents(text):
    """Strip combining accent marks that sit on Latin letters (NFKD); leave every other script unchanged."""
    out = []
    base_is_latin = False
    for char in unicodedata.normalize("NFKD", text):
        if unicodedata.combining(char) and base_is_latin:
            continue
        out.append(char)
        if not unicodedata.combining(char):
            base_is_latin = unicodedata.name(char, "").startswith("LATIN")
    return unicodedata.normalize("NFC", "".join(out))


def normalise(name):
    """Fold Latin accents, lowercase, strip punctuation, collapse spaces, drop trailing legal-suffix words."""
    if name is None:
        return ""
    folded = fold_accents(str(name)).lower().replace("&", " and ")
    text = re.sub(r"[^\w]+", " ", folded, flags=re.UNICODE)
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
    return {n for n in (normalise(e) for e in read_entries(path or CONTEXT_DIR / "denylist.txt")) if n}


def load_prefixes(path=None):
    """Return normalised prefix families, rejecting any shorter than MIN_PREFIX_CHARS."""
    result = [normalise(e) for e in read_entries(path or CONTEXT_DIR / "denylist_prefixes.txt")]
    short = [p for p in result if len(p) < MIN_PREFIX_CHARS]
    if short:
        raise ValueError("prefix entries under 4 characters must be exact-only: " + ", ".join(short))
    return result


KEYWORD_SCOPES = ("org",)
KEYWORD_FIELDS = ("org", "isp")
# D6.7 compound words: a keyword written with a leading "*" (for example "org: *hosting") matches a single TOKEN of the normalised text that ENDS with
# the word and has a non-empty stem (webhosting, egihosting, bisecthosting, ahosting). It is NOT a substring match: the word must close the token, so
# "hostingbazis" is not matched, and a token listed in COMPOUND_EXCLUDE is never matched (ghosting is an English word, not a host).
COMPOUND_EXCLUDE = frozenset({"ghosting"})


class Keyword(str):
    """A normalised keyword phrase (a str) with a field scope: 'org' (org text only) or 'any' (org text, and isp text only in the old "exclude" mode)."""

    scope = "any"
    mode = "word"


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
    mode = "word"
    if text.strip().startswith("*"):
        mode = "suffix"
        text = text.strip()[1:]
    keyword = Keyword(normalise(text))
    if mode == "suffix" and (" " in keyword or not keyword):
        raise ValueError("a compound (*) keyword must be exactly one word in line: " + entry)
    keyword.scope = scope
    keyword.mode = mode
    return keyword


def load_keywords(path=None):
    """Return Keyword phrases (whole-word match rules, optional 'org:' scope), de-duplicated by phrase and scope in file order."""
    result = []
    seen = set()
    for entry in read_entries(path or CONTEXT_DIR / "denylist_keywords.txt"):
        keyword = parse_keyword_entry(entry)
        if keyword and (str(keyword), keyword.scope, keyword.mode) not in seen:
            seen.add((str(keyword), keyword.scope, keyword.mode))
            result.append(keyword)
    return result


def load_cert_defaults(path=None):
    """Return the set of normalised default certificate organisation names."""
    return {n for n in (normalise(e) for e in read_entries(path or CONTEXT_DIR / "cert_default_names.txt")) if n}


def fold_pattern_text(text):
    """Fold Latin accents and lowercase text while keeping the punctuation that CIDR and glob patterns need."""
    return fold_accents(str(text).strip()).lower()


def load_patterns(path=None):
    """Return the CIDR and glob pattern entries, accent-folded and lowercased (punctuation kept)."""
    return [fold_pattern_text(e) for e in read_entries(path or CONTEXT_DIR / "denylist_patterns.txt")]


def matches_prefix(normalised, prefixes):
    """Return the first prefix family that matches at a word boundary, else None."""
    for prefix in prefixes:
        if normalised == prefix or normalised.startswith(prefix + " "):
            return prefix
    return None


def matches_keyword(normalised, keywords, field="org"):
    """Return the first keyword whose words appear as a whole-word run (or, for a compound "*" keyword, as the end of one token) in the text of `field` ('org' or 'isp'), else None; org-scoped keywords only match field 'org' (the default pipeline mode never passes 'isp')."""
    if field not in KEYWORD_FIELDS:
        raise ValueError("field must be one of " + ", ".join(KEYWORD_FIELDS))
    padded = " " + normalised + " "
    for keyword in keywords:
        if getattr(keyword, "scope", "any") == "org" and field != "org":
            continue
        if getattr(keyword, "mode", "word") == "suffix":
            for token in normalised.split():
                if token.endswith(keyword) and len(token) > len(keyword) and token not in COMPOUND_EXCLUDE:
                    return keyword
        elif " " + keyword + " " in padded:
            return keyword
    return None


def matches_pattern(value, patterns):
    """Return True if value (a name or an IP address) matches a CIDR or glob pattern."""
    if value is None:
        return False
    text = fold_pattern_text(value)
    for pattern in patterns:
        pattern = fold_pattern_text(pattern)
        if text == pattern:
            return True
        if "/" in pattern and re.match(r"^[0-9a-f:.]+/\d+$", pattern):
            try:
                if ipaddress.ip_address(text) in ipaddress.ip_network(pattern, strict=False):
                    return True
            except ValueError:
                continue
        elif fnmatch.fnmatchcase(text, pattern):
            return True
    return False


ISP_MATCHING_MODES = ("ignore", "exclude")
# Decision D5 (docs/ARCHITECTURE.md section 15, RAW-013, outputs/denylist_cleanup_review.md): only 22 of 50 reviewed orgs excluded purely through
# their isp text were infrastructure (44%, gate is 90%), so the isp text NEVER excludes a row by itself. "ignore" is the default and the only mode
# for pipeline use. "exclude" exists ONLY to reproduce the old counts (89,398 infrastructure rows on the spread sample); do not use it in a stage.
DEFAULT_ISP_MATCHING = "ignore"
# The complete set of infra_reason values that infrastructure_reason() returns in the default mode (D4 rule 2). 2_companies is not built yet; this
# set is the contract it must follow. The "isp_*" values exist only in the old "exclude" mode.
INFRA_REASONS = ("cloud_provider", "tag_rule", "ip_pattern", "org_exact", "org_prefix", "org_pattern", "org_keyword")


def load_rules(context_dir=None):
    """Load the exact, prefix, pattern and keyword rule sets from a context directory into one dict."""
    base = Path(context_dir) if context_dir else CONTEXT_DIR
    return {
        "exact": load_exact(base / "denylist.txt"),
        "prefixes": load_prefixes(base / "denylist_prefixes.txt"),
        "patterns": load_patterns(base / "denylist_patterns.txt"),
        "keywords": load_keywords(base / "denylist_keywords.txt"),
    }


def match_name(value, field, rules):
    """Return (rule_type, entry) for the first exact, prefix, pattern or keyword rule matching a name in `field`, else None."""
    if not value:
        return None
    normalised = normalise(value)
    if normalised in rules["exact"]:
        return ("exact", normalised)
    prefix = matches_prefix(normalised, rules["prefixes"])
    if prefix:
        return ("prefix", prefix)
    if matches_pattern(value, rules["patterns"]):
        return ("pattern", fold_pattern_text(value))
    keyword = matches_keyword(normalised, rules["keywords"], field=field)
    if keyword:
        return ("keyword", str(keyword))
    return None


def infrastructure_reason(row, rules, isp_matching=DEFAULT_ISP_MATCHING):
    """Return why a row is infrastructure (D4 rule 2, one of INFRA_REASONS), or None; isp_matching 'ignore' (default, D5) never uses the isp text, 'exclude' only reproduces old counts."""
    if isp_matching not in ISP_MATCHING_MODES:
        raise ValueError("isp_matching must be one of " + ", ".join(ISP_MATCHING_MODES))
    if row.get("cloud_provider"):
        return "cloud_provider"
    tags = row.get("tags") or []
    if "cloud" in tags or "cdn" in tags:
        return "tag_rule"
    if row.get("ip") and matches_pattern(row["ip"], rules["patterns"]):
        return "ip_pattern"
    hit = match_name(row.get("org"), "org", rules)
    if hit:
        return "org_" + hit[0]
    if isp_matching == "exclude":
        hit = match_name(row.get("isp"), "isp", rules)
        if hit:
            return "isp_" + hit[0]
    return None
