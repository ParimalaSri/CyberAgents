"""Independent signals-layer checks: recompute every signal column from hosts and companies (D9.4, D9.5), fan-out, carried columns, coverage, blind rule."""
import argparse
import itertools
import math
import re
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[4]
HOSTS_PATH = REPO_ROOT / "data" / "silver" / "hosts.parquet"
COMPANIES_PATH = REPO_ROOT / "data" / "silver" / "companies.parquet"
SIGNALS_PATH = REPO_ROOT / "data" / "gold" / "signals.parquet"
MEMBER_SOURCES = ("org", "cert_o")  # D9.4: only these hosts identity_source values are members
TERRITORY = ("US",)  # PROVISIONAL placeholder (D9.4 column 14); pass --territory when the owner supplies the list
EOL_TAGS = {"eol-product", "eol-os"}
SENSITIVE_TAGS = {"database", "ics", "medical", "iot"}
LEGACY_VERSIONS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"}
RISKY_PORTS = {22, 3389, 445, 3306, 6379, 27017, 9200, 5900, 23, 2375}
CERT_SOON = timedelta(days=30)
# D9.5 T1 and D11.1 T2 (no net suffix branch), copied from the decision text (not from the stage). RE2 and Python re agree on this syntax.
T1 = re.compile(r"(^| )(internet|telekom|communications|hosting|hosted|servers?|broadband|cable|mobile|idc|infrastructure|research"
                r"|telecom[a-z0-9]*|comunica[a-z0-9]*|network[a-z0-9]*)( |$)|data center|fixed network|(cloud|hosting)( |$)")
T2 = re.compile(r"(^| )(cloud[a-z0-9]*|host[a-z0-9]*|datacent[a-z0-9]*|rechenzentrum|fiber|fibre|isp|colo|vps|dedicated)( |$)"
                r"|[a-z0-9]+(telecom|host|hosting|servers?)( |$)")
CARRIED = ("company_id", "company_name", "name_norm", "identity_source", "identity_confidence", "host_count", "distinct_host_ips",
           "country_code", "noise_host_count", "noise_host_share")
SIGNAL_COLUMNS = ("counted_host_count", "host_signals_blind", "is_singleton", "in_territory", "named_registrant", "footprint_size",
                  "footprint_band", "sensitive_stack", "operator_shape_t1", "operator_shape_t2", "operator_name_shape", "kev_exposed",
                  "kev_host_count", "max_cvss", "max_cvss_band", "cert_expired_or_soon", "cert_issue_host_count", "eol_stack", "eol_host_count",
                  "legacy_tls", "legacy_tls_host_count", "risky_service_exposed", "risky_non_ssh_exposed", "risky_service_host_count",
                  "risky_ports", "exposed_and_outdated")
BOOLEANS = ("host_signals_blind", "is_singleton", "in_territory", "named_registrant", "sensitive_stack", "operator_shape_t1", "operator_shape_t2",
            "operator_name_shape", "kev_exposed", "cert_expired_or_soon", "eol_stack", "legacy_tls", "risky_service_exposed", "risky_non_ssh_exposed",
            "exposed_and_outdated")
DOCUMENTED_EXTREMES = ("named_registrant", "sensitive_stack", "exposed_and_outdated", "in_territory", "is_singleton", "footprint_band")  # D9.9 rule 7 list
SPARSE, DENSE = 1.0, 50.0  # percent
PHI_LIMIT = 0.8
# D9.4 coverage table on the sample (5,790 companies): label -> companies firing. Used only by the real-file run.
D9_COUNTS = {"kev_exposed": 462, "max_cvss_band = 3": 460, "max_cvss_band = 2": 209, "max_cvss_band = 1": 70, "cert_expired_or_soon": 373,
             "eol_stack": 352, "legacy_tls": 209, "risky_service_exposed": 226, "risky_service_exposed SSH only": 158, "risky_non_ssh_exposed": 68,
             "exposed_and_outdated": 48, "sensitive_stack": 55, "named_registrant": 5387, "in_territory": 1346, "is_singleton": 4169,
             "host_signals_blind": 180, "operator_shape_t1": 1046, "operator_shape_t2": 309, "operator_name_shape": 1248, "T2 only": 202, "any urgency signal": 1294,
             "strong urgency": 662, "footprint_band = 1": 1215, "footprint_band = 2": 318, "footprint_band = 3": 27, "footprint_band = 0": 4230,
             "any CVSS": 739}
HOST_COLUMNS = "identity_source, name_norm, host_ip, port, transport, timestamp, tags, ssl_versions, cert_expires, cert_expired, max_cvss, has_kev"


def load_matcher():
    """Import the shared denylist matcher from scripts/ and return the module."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import denylist_match
    return denylist_match


def fetch_dicts(con, sql):
    """Run a query and return its rows as a list of dicts keyed by column name."""
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def host_flags(row):
    """Return the per-host flags (counted, eol, sensitive, legacy, risky, risky_non_ssh, cert_issue) from one hosts row, using D9.4 only."""
    tags = row["tags"] or []
    versions = row["ssl_versions"] or []
    expires, stamp = row["cert_expires"], row["timestamp"]
    soon = expires is not None and stamp is not None and stamp < expires <= stamp + CERT_SOON
    risky = row["transport"] == "tcp" and row["port"] in RISKY_PORTS
    return {
        "counted": row["identity_source"] == "org" or "cdn" not in tags,
        "eol": any(t in EOL_TAGS for t in tags),
        "sensitive": any(t in SENSITIVE_TAGS for t in tags),
        "legacy": any(v in LEGACY_VERSIONS for v in versions if v is not None and not v.startswith("-")),
        "risky": risky,
        "risky_non_ssh": risky and row["port"] != 22,
        "cert_issue": row["cert_expired"] is True or soon,
    }


def cvss_band(value):
    """Return the D9.4 max_cvss_band: 0 no CVSS, 1 below 7.0, 2 from 7.0 to 8.9, 3 from 9.0."""
    if value is None:
        return 0
    return 3 if value >= 9.0 else 2 if value >= 7.0 else 1


def footprint_band(ips):
    """Return the D9.4 footprint band: 0 for one IP, 1 for 2 to 5, 2 for 6 to 20, 3 above 20."""
    return 0 if ips <= 1 else 1 if ips <= 5 else 2 if ips <= 20 else 3


def reference_signals(host_rows, company_rows, territory=TERRITORY):
    """Recompute every signal column per company from hosts and companies rows; return dict company_id -> dict (plus host recount fields)."""
    groups = defaultdict(list)
    for row in host_rows:
        if row["identity_source"] in MEMBER_SOURCES and row["name_norm"] is not None:
            groups[row["name_norm"]].append(row)
    ref = {}
    for comp in company_rows:
        rows = groups.get(comp["name_norm"], [])
        flagged = [(r, host_flags(r)) for r in rows]
        counted = [(r, f) for r, f in flagged if f["counted"]]
        cvss = [r["max_cvss"] for r, _ in counted if r["max_cvss"] is not None]
        top = max(cvss) if cvss else None
        risky_ports = sorted({r["port"] for r, f in counted if f["risky"]})
        out = {
            "counted_host_count": len(counted), "host_signals_blind": not counted, "is_singleton": comp["host_count"] == 1,
            "in_territory": None if comp["country_code"] is None else comp["country_code"] in territory,
            "named_registrant": comp["identity_confidence"] == "high", "footprint_size": min(comp["distinct_host_ips"], 50),
            "footprint_band": footprint_band(comp["distinct_host_ips"]), "sensitive_stack": any(f["sensitive"] for _, f in counted),
            "operator_shape_t1": T1.search(comp["name_norm"]) is not None, "operator_shape_t2": T2.search(comp["name_norm"]) is not None,
            "kev_exposed": any(r["has_kev"] is True for r, _ in counted), "kev_host_count": sum(1 for r, _ in counted if r["has_kev"] is True),
            "max_cvss": top, "max_cvss_band": cvss_band(top),
            "cert_expired_or_soon": any(f["cert_issue"] for _, f in flagged), "cert_issue_host_count": sum(1 for _, f in flagged if f["cert_issue"]),
            "eol_stack": any(f["eol"] for _, f in counted), "eol_host_count": sum(1 for _, f in counted if f["eol"]),
            "legacy_tls": any(f["legacy"] for _, f in counted), "legacy_tls_host_count": sum(1 for _, f in counted if f["legacy"]),
            "risky_service_exposed": any(f["risky"] for _, f in counted), "risky_non_ssh_exposed": any(f["risky_non_ssh"] for _, f in counted),
            "risky_service_host_count": sum(1 for _, f in counted if f["risky"]), "risky_ports": risky_ports,
            "exposed_and_outdated": any(f["risky"] and (f["eol"] or (r["max_cvss"] is not None and r["max_cvss"] >= 7.0)) for r, f in counted),
            "_member_rows": len(rows), "_member_ips": len({r["host_ip"] for r in rows}), "_cdn_rows": len(rows) - len(counted),
        }
        out["operator_name_shape"] = out["operator_shape_t1"] or out["operator_shape_t2"]
        ref[comp["company_id"]] = out
    return ref


def compare_signals(ref, signal_rows):
    """Compare the reference with the stage output; return (missing ids, extra ids, duplicate rows, per-column disagreement counts, examples)."""
    seen = {}
    duplicates = 0
    for row in signal_rows:
        duplicates += row["company_id"] in seen
        seen[row["company_id"]] = row
    missing, extra = sorted(set(ref) - set(seen)), sorted(set(seen) - set(ref))
    diffs, examples = {}, {}
    for cid in set(ref) & set(seen):
        for column in SIGNAL_COLUMNS:
            if ref[cid][column] != seen[cid][column]:
                diffs[column] = diffs.get(column, 0) + 1
                examples.setdefault(column, (seen[cid]["name_norm"], seen[cid][column], ref[cid][column]))
    return missing, extra, duplicates, diffs, examples


def compare_carried(company_rows, signal_rows):
    """Return per-column counts of carried-column differences between signals and companies, joined on company_id."""
    comp = {c["company_id"]: c for c in company_rows}
    diffs = {}
    for row in signal_rows:
        other = comp.get(row["company_id"])
        if other is None:
            continue
        for column in CARRIED:
            if row[column] != other[column]:
                diffs[column] = diffs.get(column, 0) + 1
    return diffs


def coverage_counts(ref):
    """Return label -> companies firing, computed from the reference (my own recomputation), including the derived rows of D9.4."""
    rows = list(ref.values())
    counts = {name: sum(1 for r in rows if r[name]) for name in BOOLEANS}
    for band in (1, 2, 3):
        counts[f"max_cvss_band = {band}"] = sum(1 for r in rows if r["max_cvss_band"] == band)
    for band in (0, 1, 2, 3):
        counts[f"footprint_band = {band}"] = sum(1 for r in rows if r["footprint_band"] == band)
    counts["any CVSS"] = sum(1 for r in rows if r["max_cvss"] is not None)
    counts["T2 only"] = sum(1 for r in rows if r["operator_shape_t2"] and not r["operator_shape_t1"])
    counts["risky_service_exposed SSH only"] = sum(1 for r in rows if r["risky_service_exposed"] and not r["risky_non_ssh_exposed"])
    counts["any urgency signal"] = sum(1 for r in rows if r["kev_exposed"] or r["max_cvss_band"] >= 2 or r["eol_stack"] or r["legacy_tls"]
                                       or r["risky_service_exposed"] or r["cert_expired_or_soon"])
    counts["strong urgency"] = sum(1 for r in rows if r["kev_exposed"] or r["max_cvss_band"] == 3 or r["exposed_and_outdated"])
    return counts


def phi(pairs):
    """Return the phi coefficient of two boolean series given as (a, b) pairs; 0.0 when either is constant."""
    n11 = sum(1 for a, b in pairs if a and b)
    n10 = sum(1 for a, b in pairs if a and not b)
    n01 = sum(1 for a, b in pairs if not a and b)
    n00 = len(pairs) - n11 - n10 - n01
    denom = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    return 0.0 if denom == 0 else (n11 * n00 - n10 * n01) / denom


def phi_pairs(signal_rows):
    """Return (name a, name b, phi) for every pair of boolean signals (plus max_cvss >= 7 and band 3) with |phi| >= PHI_LIMIT, largest first."""
    series = {name: [bool(r[name]) for r in signal_rows] for name in BOOLEANS}
    series["max_cvss >= 7"] = [r["max_cvss"] is not None and r["max_cvss"] >= 7.0 for r in signal_rows]
    series["max_cvss_band = 3"] = [r["max_cvss_band"] == 3 for r in signal_rows]
    found = []
    for a, b in itertools.combinations(series, 2):
        value = phi(list(zip(series[a], series[b])))
        if abs(value) >= PHI_LIMIT:
            found.append((a, b, round(value, 3)))
    return sorted(found, key=lambda p: -abs(p[2]))


def check_fanout(company_rows, signal_rows, results):
    """Check rows equal, company_id unique and the id sets equal in both directions (join fan-out guard)."""
    c_ids = {c["company_id"] for c in company_rows}
    s_ids = [s["company_id"] for s in signal_rows]
    dup = len(s_ids) - len(set(s_ids))
    ok = len(signal_rows) == len(company_rows) and dup == 0 and set(s_ids) == c_ids
    results.append(("signals rows == companies rows, company_id unique, id sets equal both ways", ok,
                    f"signals {len(signal_rows):,}, companies {len(company_rows):,}, duplicate ids {dup}, only in signals {len(set(s_ids) - c_ids)}, only in companies {len(c_ids - set(s_ids))}"))


def check_recompute(ref, signal_rows, results):
    """Compare every signal column with the independent recomputation; 0 disagreements expected."""
    missing, extra, dup, diffs, examples = compare_signals(ref, signal_rows)
    total = sum(diffs.values()) + len(missing) + len(extra) + dup
    results.append(("independent recompute of all 26 signal columns from hosts + companies: 0 disagreements", total == 0,
                    f"{len(ref):,} companies; missing {len(missing)}, extra {len(extra)}, duplicate {dup}; column disagreements {diffs}; examples {list(examples.items())[:3]}"))
    results.append(("regexes recomputed in Python: operator_shape_t1, operator_shape_t2 and the union", not any(
        diffs.get(c) for c in ("operator_shape_t1", "operator_shape_t2", "operator_name_shape")), f"disagreements {({c: diffs.get(c, 0) for c in ('operator_shape_t1', 'operator_shape_t2', 'operator_name_shape')})}"))
    results.append(("max_cvss_band edges (null=0, below 7.0=1, 7.0 to 8.9=2, 9.0 up=3) recomputed", not diffs.get("max_cvss_band") and not diffs.get("max_cvss"),
                    f"band disagreements {diffs.get('max_cvss_band', 0)}, max_cvss disagreements {diffs.get('max_cvss', 0)}"))


def check_carried(company_rows, signal_rows, results):
    """Check all 10 carried columns equal companies on every row."""
    diffs = compare_carried(company_rows, signal_rows)
    results.append(("the 10 carried columns equal companies on every row", not diffs, f"column differences {diffs or 'none'}"))


def check_join_recount(ref, signal_rows, results):
    """Check my recount of member rows and distinct IPs per company from hosts equals host_count and distinct_host_ips (D8.5)."""
    bad = [(r["name_norm"], r["host_count"], ref[r["company_id"]]["_member_rows"], r["distinct_host_ips"], ref[r["company_id"]]["_member_ips"])
           for r in signal_rows if r["company_id"] in ref and (r["host_count"] != ref[r["company_id"]]["_member_rows"]
                                                              or r["distinct_host_ips"] != ref[r["company_id"]]["_member_ips"])]
    results.append(("join recount from hosts equals host_count and distinct_host_ips on every row", not bad, f"{len(bad)} rows differ; e.g. {bad[:3]}"))


def check_blind(ref, signal_rows, results):
    """Check host_signals_blind companies are exactly the cert_o-only companies whose every member host is cdn-tagged."""
    mine = {cid for cid, r in ref.items() if r["_member_rows"] > 0 and r["_cdn_rows"] == r["_member_rows"]}
    stage = {r["company_id"] for r in signal_rows if r["host_signals_blind"]}
    cert_only = {r["company_id"] for r in signal_rows if r["identity_source"] == "cert_o"}
    results.append(("host_signals_blind companies = exactly the companies whose every member host is cdn-tagged (all of them cert_o only)", mine == stage and stage <= cert_only,
                    f"stage blind {len(stage)}, mine {len(mine)}, only stage {len(stage - mine)}, only mine {len(mine - stage)}, blind but not cert_o {len(stage - cert_only)}"))


def check_denylist(signal_rows, results):
    """Apply the shared denylist rules to company_name and name_norm; 0 hits expected."""
    matcher = load_matcher()
    rules = matcher.load_rules()
    hits = []
    for row in signal_rows:
        for column in ("company_name", "name_norm"):
            hit = matcher.match_name(row[column], "org", rules)
            if hit:
                hits.append((column, row[column], row["host_count"], hit[0], hit[1]))
    shown = "; ".join(f"{h[0]}={h[1]!r} x{h[2]} [{h[3]}: {h[4]}]" for h in hits[:5])
    results.append(("denylist leakage in company_name and name_norm (shared rules, org text)", not hits, f"{len(hits)} hits over {len(signal_rows):,} companies; {shown or 'none'}"))


def check_coverage(ref, signal_rows, results, warnings, d9):
    """Check no boolean is constant, list sparse or dense booleans as warnings, and compare the recomputed counts with the D9.4 table when given."""
    total = len(signal_rows)
    constant = [n for n in BOOLEANS if len({r[n] for r in signal_rows}) < 2]
    results.append(("no boolean signal is constant", not constant, f"constant: {constant or 'none'}"))
    for name in BOOLEANS:
        share = 100.0 * sum(1 for r in signal_rows if r[name]) / total if total else 0.0
        if (share < SPARSE or share > DENSE) and name not in DOCUMENTED_EXTREMES:
            warnings.append(f"WARN {name} fires on {share:.2f}% of companies (outside {SPARSE}% to {DENSE}%, not on the documented list)")
    if d9:
        mine = coverage_counts(ref)
        off = {k: (mine.get(k), v) for k, v in d9.items() if mine.get(k) != v}
        results.append(("company-level coverage recomputed equals the D9.4 sample table (mine, D9)", not off, f"{len(d9)} figures compared; differences {off or 'none'}"))
    for a, b, value in phi_pairs(signal_rows):
        warnings.append(f"phi pair |phi|>=0.8: {a} with {b} = {value} (needs an explanation in the report)")


def run_checks(hosts_path, companies_path, signals_path, territory=TERRITORY, d9=None):
    """Run every extra check; return (results, warnings, reference, host_rows, company_rows, signal_rows)."""
    con = duckdb.connect()
    host_rows = fetch_dicts(con, f"SELECT {HOST_COLUMNS} FROM read_parquet('{Path(hosts_path).as_posix()}')")
    company_rows = fetch_dicts(con, f"SELECT {', '.join(CARRIED)} FROM read_parquet('{Path(companies_path).as_posix()}')")
    signal_rows = fetch_dicts(con, f"SELECT {', '.join(CARRIED + SIGNAL_COLUMNS)} FROM read_parquet('{Path(signals_path).as_posix()}')")
    ref = reference_signals(host_rows, company_rows, territory)
    results, warnings = [], []
    check_fanout(company_rows, signal_rows, results)
    check_recompute(ref, signal_rows, results)
    check_carried(company_rows, signal_rows, results)
    check_join_recount(ref, signal_rows, results)
    check_blind(ref, signal_rows, results)
    check_denylist(signal_rows, results)
    check_coverage(ref, signal_rows, results, warnings, d9)
    return results, warnings, ref, host_rows, company_rows, signal_rows


def reconciliation(host_rows, ref):
    """Return the recomputed headline numbers (member and counted rows, certificate branches, edge cases) as (label, value) pairs."""
    members = [r for r in host_rows if r["identity_source"] in MEMBER_SOURCES and r["name_norm"] is not None]
    flags = [(r, host_flags(r)) for r in members]
    expired = sum(1 for r, _ in flags if r["cert_expired"] is True)
    soon_only = sum(1 for r, f in flags if f["cert_issue"] and r["cert_expired"] is not True)
    zero_cvss = sum(1 for r in members if r["max_cvss"] == 0)
    edge_exact = sum(1 for r in members if r["cert_expires"] is not None and r["timestamp"] is not None and r["cert_expires"] == r["timestamp"] + CERT_SOON)
    edge_now = sum(1 for r in members if r["cert_expires"] is not None and r["timestamp"] is not None and r["cert_expires"] == r["timestamp"])
    return [("member host rows", len(members)), ("counted member rows", sum(1 for _, f in flags if f["counted"])),
            ("non-counted member rows (cdn-tagged cert_o)", sum(1 for _, f in flags if not f["counted"])),
            ("companies with at least one non-counted host", sum(1 for r in ref.values() if r["_cdn_rows"] > 0)),
            ("member rows meeting the cert condition via the boolean", expired), ("member rows meeting it only via the 30-day window", soon_only),
            ("member rows with max_cvss exactly 0.0 (band 1, not band 0; edge)", zero_cvss),
            ("member rows with cert_expires == timestamp + 30 days exactly (counted, upper edge inclusive)", edge_exact),
            ("member rows with cert_expires == timestamp (not counted, lower edge exclusive)", edge_now)]


def render(results):
    """Return the results as markdown table lines."""
    failed = [r for r in results if not r[1]]
    lines = [f"**{'FAIL' if failed else 'PASS'}**: {len(results) - len(failed)}/{len(results)} extra checks passed", "",
             "| result | check | evidence |", "|---|---|---|"]
    lines += [f"| {'PASS' if ok else 'FAIL'} | {name} | {evidence} |" for name, ok, evidence in results]
    return lines


def main():
    """Run the extra checks on the real files, print markdown with the recomputed numbers, exit 1 on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hosts", default=str(HOSTS_PATH))
    parser.add_argument("--companies", default=str(COMPANIES_PATH))
    parser.add_argument("--signals", default=str(SIGNALS_PATH))
    parser.add_argument("--territory", default=",".join(TERRITORY), help="comma separated country codes of the territory constant")
    parser.add_argument("--no-d9", action="store_true", help="skip the comparison with the D9.4 sample table (use on the full run)")
    args = parser.parse_args()
    results, warnings, ref, host_rows, _companies, _signals = run_checks(
        args.hosts, args.companies, args.signals, tuple(args.territory.split(",")), None if args.no_d9 else D9_COUNTS)
    print("\n".join(render(results)))
    print("\n## Warnings")
    print("\n".join(f"- {w}" for w in warnings) or "- none")
    print("\n## Recomputed coverage (mine)")
    for label, value in coverage_counts(ref).items():
        print(f"- {label}: {value:,}")
    print("\n## Recomputed reconciliation (mine)")
    for label, value in reconciliation(host_rows, ref):
        print(f"- {label}: {value:,}")
    sys.exit(1 if any(not r[1] for r in results) else 0)


if __name__ == "__main__":
    main()
