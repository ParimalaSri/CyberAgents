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
    cases.append(len(loaded) == len(set(loaded)) and "vpn" in loaded and "telecom" not in loaded)
    cases.append(dm.matches_prefix(norm("Weebly, Inc."), dm.load_prefixes()) == "weebly")
    for number, ok in enumerate(cases, 1):
        check(ok, "case " + str(number))
    return len(cases)


if __name__ == "__main__":
    print(run_tests(), "cases passed")
