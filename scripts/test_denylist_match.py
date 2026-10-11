"""Self-test for scripts/denylist_match.py (run: python scripts/test_denylist_match.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import denylist_match as dm


def check(condition, label):
    """Fail loudly with the label when a condition is false."""
    if not condition:
        raise AssertionError(label)


def accent_cases():
    """Return accent-folding assertions: Latin accents fold, other scripts survive, lists share the folded form."""
    norm = dm.normalise
    out = [
        norm("TELEFÔNICA BRASIL") == norm("Telefónica Brasil") == norm("telefonica brasil") == "telefonica brasil",
        norm("São Paulo") == "sao paulo",
        norm("Ação Ltda") == "acao ltda",
        norm("Müller GmbH") == "muller",
        norm("España Ñandú") == "espana nandu",
        norm("Café Société Anonyme") == "cafe societe anonyme",
        norm("Ça va") == "ca va",
        norm("TELEFÔNICA") == norm("telefônica") == norm("TELEFONICA"),
        norm("Telecomunicações") == norm("TELECOMUNICAÇOES") == "telecomunicacoes",
        norm("Ａｃｍｅ") == "acme",
        norm("á") == "a" and norm("école") == norm("école") == "ecole",
        norm("Telefónica") == norm(dm.fold_accents("Telefónica")),
        norm("中国电信集团有限公司") == "中国电信集团有限公司",
        norm("中国电信") != "" and norm("株式会社") != "",
        norm("Яндекс Й") == "яндекс й",
        norm("ООО Ростелеком") == "ооо ростелеком",
        norm("شركة الاتصالات") == "شركة الاتصالات",
        norm("서울 통신") == "서울 통신",
        norm("Salesforce, Inc.") == "salesforce",
        norm(None) == "" and norm("") == "",
    ]
    out.append(dm.matches_keyword(norm("TELEFÔNICA BRASIL S.A"), [dm.parse_keyword_entry("org: telefónica")]) == "telefonica")
    out.append(dm.matches_keyword(norm("Telefónica Celular de Bolivia"), [dm.parse_keyword_entry("org: telefonica")]) == "telefonica")
    out.append(dm.matches_keyword(norm("中国电信集团有限公司"), [dm.parse_keyword_entry("org: telecom")]) is None)
    out.append(dm.matches_prefix(norm("Telefônica Brasil S.A"), [norm("telefónica brasil")]) == "telefonica brasil")
    out.append(dm.matches_pattern("Telefónica-Réseau", ["*telefonica-reseau*"]) and dm.matches_pattern("139.162.1.1", ["139.162.0.0/16"]))
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        files = {
            "e.txt": ["Telefónica Brasil S.A."],
            "p.txt": ["Ação Telecom"],
            "k.txt": ["org: telefônica", "telefonica", "org: telefonica"],
            "c.txt": ["Société Générale"],
            "g.txt": ["*TELEFÓNICA*"],
        }
        for name, lines in files.items():
            (base / name).write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        out.append(dm.load_exact(base / "e.txt") == {"telefonica brasil s a"})
        out.append(dm.load_prefixes(base / "p.txt") == ["acao telecom"])
        out.append([(str(k), k.scope) for k in dm.load_keywords(base / "k.txt")] == [("telefonica", "org"), ("telefonica", "any")])
        out.append(dm.load_cert_defaults(base / "c.txt") == {"societe generale"})
        out.append(dm.load_patterns(base / "g.txt") == ["*telefonica*"])
    out.append("" not in dm.load_exact() and "" not in dm.load_cert_defaults())
    return out


def isp_cases():
    """Return assertions for the isp-matching switch, the website-builder prefixes and the removed generic keywords."""
    rules = dm.load_rules()
    norm = dm.normalise
    abtc = {"org": "ABTC IMOVEIS LTDA ME", "isp": "TELEFONICA BRASIL S.A", "cloud_provider": None, "tags": [], "ip": "200.1.1.1"}
    out = [
        dm.DEFAULT_ISP_MATCHING == "ignore",
        dm.infrastructure_reason(abtc, rules) is None,
        dm.infrastructure_reason(abtc, rules, isp_matching="ignore") is None,
        dm.infrastructure_reason(abtc, rules, isp_matching="exclude") == "isp_exact",
        dm.infrastructure_reason(dict(abtc, org="Google LLC"), rules) == "org_exact",
        dm.infrastructure_reason(dict(abtc, org="Google LLC", isp="x"), rules) == "org_exact",
        dm.infrastructure_reason(dict(abtc, cloud_provider="Oracle Cloud Infrastructure"), rules) == "cloud_provider",
        dm.infrastructure_reason(dict(abtc, tags=["cdn"]), rules) == "tag_rule",
        dm.infrastructure_reason(dict(abtc, tags=["cloud", "eol-os"]), rules) == "tag_rule",
        dm.infrastructure_reason(dict(abtc, ip="139.162.5.5"), rules) == "ip_pattern",
        dm.infrastructure_reason(dict(abtc, org="Krystal Hosting Ltd", isp=None), rules) == "org_keyword",
        dm.infrastructure_reason(dict(abtc, org=None, isp="Google LLC"), rules) is None,
        dm.infrastructure_reason(dict(abtc, org=None, isp="Google LLC"), rules, isp_matching="exclude") == "isp_exact",
        dm.matches_prefix(norm("Automattic, Inc"), rules["prefixes"]) == "automattic",
        dm.matches_prefix(norm("TUMBLR, INC."), rules["prefixes"]) == "tumblr",
        dm.matches_prefix(norm("Automattic Consulting"), rules["prefixes"]) == "automattic",
        dm.matches_prefix(norm("Tumblrfoo Corp"), rules["prefixes"]) is None,
        dm.match_name("Telephone Answering Service Inc", "org", rules) is None,
        dm.match_name("Cable Car Museum", "org", rules) is None,
        dm.match_name("Dedicated Staffing LLC", "org", rules) is None,
        dm.match_name("Acme Fibre Networks", "org", rules) == ("keyword", "fibre"),
        dm.match_name(None, "org", rules) is None,
    ]
    for bad in ("cable", "dedicated", "telephone"):
        out.append(bad not in [str(k) for k in rules["keywords"]])
    try:
        dm.infrastructure_reason(abtc, rules, isp_matching="sometimes")
        out.append(False)
    except ValueError:
        out.append(True)
    return out


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
    cases.extend(accent_cases())
    cases.extend(isp_cases())
    for number, ok in enumerate(cases, 1):
        check(ok, "case " + str(number))
    return len(cases)


if __name__ == "__main__":
    print(run_tests(), "cases passed")
