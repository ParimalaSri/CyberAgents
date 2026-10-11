"""Self-test for scripts/denylist_match.py (run: python scripts/test_denylist_match.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import denylist_match as dm


def check(condition, label):
    """Fail loudly with the label when a condition is false."""
    if not condition:
        raise AssertionError(label)


def run_tests():
    """Run all matcher cases and return how many passed."""
    kw = ["hosting", "vpn", "internet service provider", "chinanet"]
    norm = dm.normalise
    cases = [
        (matches := dm.matches_keyword)(norm("Krystal Hosting Ltd"), kw) == "hosting",
        matches(norm("WHG Hosting Services Ltd"), kw) == "hosting",
        matches(norm("Mullvad VPN AB"), kw) == "vpn",
        matches(norm("CHINANET-ZJ Taizhou node network"), kw) == "chinanet",
        matches(norm("Internet Service Provider in Sri Lanka."), kw) == "internet service provider",
        matches(norm("webhosting servers"), kw) is None,
        matches(norm("vpnsoft Inc"), kw) is None,
        matches(norm("Internet Provider Service"), kw) is None,
        matches(norm("Salesforce, Inc."), kw) is None,
        matches("", kw) is None,
        matches(norm(None), kw) is None,
        dm.normalise("Hosting.de GmbH") == "hosting de",
        matches(norm("Hosting.de GmbH"), kw) == "hosting",
    ]
    loaded = dm.load_keywords()
    cases.append(len(loaded) == len(set(loaded)) and "vpn" in loaded and not [k for k in loaded if k == "telecom" and k.scope == "any"])
    cases.append(dm.matches_prefix(norm("Weebly, Inc."), dm.load_prefixes()) == "weebly")
    scoped = [dm.parse_keyword_entry("org: telecom"), dm.parse_keyword_entry("hosting")]
    cases.append(scoped[0] == "telecom" and scoped[0].scope == "org" and scoped[1].scope == "any")
    cases.append(matches(norm("Bretagne Telecom"), scoped) == "telecom")
    cases.append(matches(norm("Bretagne Telecom"), scoped, field="org") == "telecom")
    cases.append(matches(norm("A1 Telekom Telecom Austria"), scoped, field="isp") is None)
    cases.append(matches(norm("Krystal Hosting Ltd"), scoped, field="isp") == "hosting")
    cases.append(matches(norm("Krystal Hosting Ltd"), scoped, field="org") == "hosting")
    cases.append(matches(norm("Acme Telecommunications"), scoped) is None)
    cases.append(matches(norm("Plain Telecom"), ["telecom"], field="isp") == "telecom")
    cases.append(dm.parse_keyword_entry("ORG:  Tele Com ") == "tele com")
    try:
        dm.parse_keyword_entry("isp: telecom")
        cases.append(False)
    except ValueError:
        cases.append(True)
    try:
        matches("x", kw, field="cert")
        cases.append(False)
    except ValueError:
        cases.append(True)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "kw.txt"
        path.write_text("# c\nhosting\norg: telecom\norg: telecom\ntelecom\n", encoding="utf-8")
        loaded_tmp = dm.load_keywords(path)
        cases.append([(str(k), k.scope) for k in loaded_tmp] == [("hosting", "any"), ("telecom", "org"), ("telecom", "any")])
        path.write_text("bogus: telecom\n", encoding="utf-8")
        try:
            dm.load_keywords(path)
            cases.append(False)
        except ValueError:
            cases.append(True)
    for number, ok in enumerate(cases, 1):
        check(ok, "case " + str(number))
    return len(cases)


if __name__ == "__main__":
    print(run_tests(), "cases passed")
