"""Independent companies-layer checks: reconciliation with hosts, full recompute of every aggregate, sha256 company_id, company_name denylist."""
import argparse
import hashlib
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[4]
HOSTS_PATH = REPO_ROOT / "data" / "silver" / "hosts.parquet"
COMPANIES_PATH = REPO_ROOT / "data" / "silver" / "companies.parquet"
MEMBER_SOURCES = ("org", "cert_o")  # D8.3: only these hosts identity_source values create companies
NEVER_CREATE = ("noise", "infrastructure_unresolved", "null_org")
RESOLVED_RANGE = (5.0, 20.0)  # D4 / D8.8 rule 7
NOISE_FLAG = 0.5  # D8.6 preview threshold
HASH_LENGTH = 16  # D8.3
SHARE_TOLERANCE = 1e-9
BUCKETS = (("1", 1, 1), ("2", 2, 2), ("3-5", 3, 5), ("6-20", 6, 20), ("21-100", 21, 100), ("over 100", 101, None))
HOST_COLUMNS = "identity_source, name_norm, host_ip, port, country_code, org, org_norm, cert_subject_o, is_noise"
COMPANY_COLUMNS = ("company_id, company_name, name_norm, identity_source, identity_confidence, org_host_count, cert_o_host_count, "
                   "host_count, distinct_host_ips, distinct_port_count, country_code, country_count, noise_host_count, noise_host_share")


def load_matcher():
    """Import the shared denylist matcher from scripts/ and return the module."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import denylist_match
    return denylist_match


def connect(hosts_path, companies_path):
    """Return a DuckDB connection with views hosts and companies over the two parquet files."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW hosts AS SELECT * FROM read_parquet('{Path(hosts_path).as_posix()}')")
    con.execute(f"CREATE VIEW companies AS SELECT * FROM read_parquet('{Path(companies_path).as_posix()}')")
    return con


def fetch_dicts(con, sql):
    """Run a query and return its rows as a list of dicts keyed by column name."""
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def quantile_disc(sorted_values, q):
    """Return the discrete quantile (an actual value) of an ascending list: element ceil(q * n) - 1."""
    return sorted_values[max(math.ceil(q * len(sorted_values)) - 1, 0)]


def display_name(texts, has_org):
    """Pick the D8.4 display name from (source, raw text) pairs: most frequent, then not all upper case, then byte order."""
    wanted = "org" if has_org else "cert_o"
    counts = Counter(text for source, text in texts if source == wanted and text is not None)
    return min(counts, key=lambda t: (-counts[t], t == t.upper(), t.encode("utf-8")))


def reference_companies(host_rows):
    """Recompute every company aggregate from hosts rows (list of dicts) using D8.3 to D8.6 only; return dict name_norm -> dict."""
    groups = defaultdict(list)
    noise = Counter()
    for row in host_rows:
        if row["identity_source"] in MEMBER_SOURCES and row["name_norm"] is not None:
            groups[row["name_norm"]].append(row)
        if row["is_noise"] and row["org_norm"] is not None:
            noise[row["org_norm"]] += 1
    ref = {}
    for name, rows in groups.items():
        org_n = sum(1 for r in rows if r["identity_source"] == "org")
        cert_n = len(rows) - org_n
        countries = Counter(r["country_code"] for r in rows if r["country_code"] is not None)
        top_country = min(countries, key=lambda c: (-countries[c], c)) if countries else None
        texts = [("org", r["org"]) if r["identity_source"] == "org" else ("cert_o", r["cert_subject_o"]) for r in rows]
        noise_n = noise.get(name, 0)
        ref[name] = {
            "company_id": hashlib.sha256(name.encode("utf-8")).hexdigest()[:HASH_LENGTH],
            "company_name": display_name(texts, org_n > 0),
            "identity_source": "org" if org_n > 0 else "cert_o",
            "identity_confidence": "high" if org_n > 0 else "low",
            "org_host_count": org_n, "cert_o_host_count": cert_n, "host_count": len(rows),
            "distinct_host_ips": len({r["host_ip"] for r in rows}), "distinct_port_count": len({r["port"] for r in rows}),
            "country_code": top_country, "country_count": len(countries),
            "noise_host_count": noise_n, "noise_host_share": noise_n / (noise_n + len(rows)),
        }
    return ref


def compare_companies(ref, company_rows):
    """Compare the reference with the stage output; return (missing names, extra names, per-column disagreement counts, examples)."""
    actual = {}
    duplicates = 0
    for row in company_rows:
        duplicates += row["name_norm"] in actual
        actual[row["name_norm"]] = row
    missing = sorted(set(ref) - set(actual))
    extra = sorted(set(actual) - set(ref))
    diffs = Counter()
    examples = {}
    for name in set(ref) & set(actual):
        for column, expected in ref[name].items():
            got = actual[name][column]
            same = abs(got - expected) <= SHARE_TOLERANCE if column == "noise_host_share" and got is not None else got == expected
            if not same:
                diffs[column] += 1
                examples.setdefault(column, (name, got, expected))
    return missing, extra, diffs, examples, duplicates


def check_reconciliation(con, results):
    """Check hosts rows = never-create rows + member rows and that member rows group into exactly the companies' name_norm set."""
    counts = dict(con.execute("SELECT identity_source, count(*) FROM hosts GROUP BY 1").fetchall())
    total = sum(counts.values())
    never = sum(counts.get(s, 0) for s in NEVER_CREATE)
    member = sum(counts.get(s, 0) for s in MEMBER_SOURCES)
    unexpected = {k: v for k, v in counts.items() if k not in NEVER_CREATE + MEMBER_SOURCES}
    sum_host = con.execute("SELECT coalesce(sum(host_count), 0) FROM companies").fetchone()[0]
    n_companies = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    n_names = con.execute("SELECT count(DISTINCT name_norm) FROM hosts WHERE identity_source IN ('org', 'cert_o')").fetchone()[0]
    ok = not unexpected and total == never + member and sum_host == member and n_companies == n_names and n_companies <= total
    evidence = (f"hosts {total:,} = never-create {never:,} + member {member:,}; sum(host_count) {sum_host:,}; companies {n_companies:,} vs "
                f"distinct member name_norm {n_names:,}; unexpected identity_source {unexpected}")
    results.append(("reconciliation hosts = never-create + member; member rows group into companies", ok, evidence))
    return {"total": total, "never": never, "member": member, "counts": counts}


def check_recompute(host_rows, company_rows, results):
    """Compare the stage output with the independent recomputation (every aggregate, company_id, company_name); return the reference."""
    ref = reference_companies(host_rows)
    missing, extra, diffs, examples, duplicates = compare_companies(ref, company_rows)
    total = sum(diffs.values()) + len(missing) + len(extra) + duplicates
    evidence = (f"{len(ref):,} reference companies vs {len(company_rows):,} rows; missing {len(missing)}, extra {len(extra)}, duplicate name_norm {duplicates}; "
                f"column disagreements {dict(diffs)}; examples {list(examples.items())[:3]} {missing[:2]} {extra[:2]}")
    results.append(("independent recompute of every company column from hosts: 0 disagreements", total == 0, evidence))
    id_bad = [(r["name_norm"], r["company_id"]) for r in company_rows
              if r["company_id"] != hashlib.sha256(r["name_norm"].encode("utf-8")).hexdigest()[:HASH_LENGTH]]
    results.append(("company_id equals hashlib sha256(name_norm)[:16] on every row", not id_bad, f"{len(id_bad)} mismatches; e.g. {id_bad[:3]}"))
    return ref


def check_company_name_denylist(company_rows, results):
    """Apply the shared denylist rules to company_name (raw display text) and name_norm; 0 hits expected."""
    matcher = load_matcher()
    rules = matcher.load_rules()
    hits = []
    for row in company_rows:
        for column in ("company_name", "name_norm"):
            hit = matcher.match_name(row[column], "org", rules)
            if hit:
                hits.append((column, row[column], row["host_count"], hit[0], hit[1]))
    shown = "; ".join(f"{h[0]}={h[1]!r} x{h[2]} [{h[3]}: {h[4]}]" for h in hits[:5])
    results.append(("denylist leakage in company_name and name_norm (shared rules, org text)", not hits, f"{len(hits)} hits over {len(company_rows):,} companies; {shown or 'none'}"))


def check_resolved_share(rec, results):
    """Check the resolved share is inside the D4 range and report the headline unresolved share."""
    resolved = 100.0 * rec["member"] / rec["total"]
    unresolved = 100.0 - resolved
    ok = RESOLVED_RANGE[0] <= resolved <= RESOLVED_RANGE[1]
    results.append((f"resolved share {RESOLVED_RANGE[0]}% to {RESOLVED_RANGE[1]}%", ok,
                    f"resolved {rec['member']:,} of {rec['total']:,} = {resolved:.2f}%; headline unresolved {unresolved:.2f}%"))


def metrics(ref, host_rows, rec):
    """Return the recomputed report numbers (distribution, confidence, noise, spellings) as an ordered list of (label, value)."""
    counts = sorted(r["host_count"] for r in ref.values())
    out = [("companies", len(ref)), ("member rows", sum(counts)), ("singletons", counts.count(1))]
    for label, low, high in BUCKETS[1:]:
        out.append((f"host_count {label}", sum(1 for c in counts if c >= low and (high is None or c <= high))))
    out += [("median", quantile_disc(counts, 0.5)), ("p90", quantile_disc(counts, 0.9)), ("p99", quantile_disc(counts, 0.99)), ("max", counts[-1])]
    out += [("confidence high", sum(1 for r in ref.values() if r["identity_confidence"] == "high")),
            ("confidence low", sum(1 for r in ref.values() if r["identity_confidence"] == "low")),
            ("named under both sources", sum(1 for r in ref.values() if r["org_host_count"] and r["cert_o_host_count"])),
            ("cert_o-only singletons", sum(1 for r in ref.values() if r["host_count"] == 1 and r["identity_source"] == "cert_o"))]
    noisy = [r for r in ref.values() if r["noise_host_count"]]
    noise_rows = Counter(r["org_norm"] for r in host_rows if r["is_noise"] and r["org_norm"] is not None)
    only = {n: c for n, c in noise_rows.items() if n not in ref}
    out += [("companies with noise", len(noisy)), ("noise rows attributed", sum(r["noise_host_count"] for r in noisy)),
            ("companies noise share >= 0.5", sum(1 for r in noisy if r["noise_host_share"] >= NOISE_FLAG)),
            ("noise-only names", len(only)), ("noise-only rows", sum(only.values()))]
    org_raw = {r["org"] for r in host_rows if r["identity_source"] == "org" and r["org"] is not None}
    cert_raw = {r["cert_subject_o"] for r in host_rows if r["identity_source"] == "cert_o" and r["cert_subject_o"] is not None}
    out += [("raw org spellings", len(org_raw)), ("raw cert O spellings", len(cert_raw)),
            ("distinct host_ip all", len({r["host_ip"] for r in host_rows})),
            ("distinct host_ip members", len({r["host_ip"] for r in host_rows if r["identity_source"] in MEMBER_SOURCES}))]
    return out


def spelling_review(host_rows, top):
    """Return the companies with the most distinct raw spellings as (name_norm, spelling count, host_count, sorted spellings)."""
    spell = defaultdict(set)
    size = Counter()
    for r in host_rows:
        if r["identity_source"] in MEMBER_SOURCES and r["name_norm"] is not None:
            spell[r["name_norm"]].add(r["org"] if r["identity_source"] == "org" else r["cert_subject_o"])
            size[r["name_norm"]] += 1
    ranked = sorted(spell, key=lambda n: (-len(spell[n]), -size[n], n))[:top]
    return [(n, len(spell[n]), size[n], sorted(s for s in spell[n] if s)) for n in ranked]


def run_checks(hosts_path, companies_path):
    """Run every extra check; return (results, reference, host_rows, company_rows, reconciliation)."""
    con = connect(hosts_path, companies_path)
    host_rows = fetch_dicts(con, f"SELECT {HOST_COLUMNS} FROM hosts")
    company_rows = fetch_dicts(con, f"SELECT {COMPANY_COLUMNS} FROM companies")
    results = []
    rec = check_reconciliation(con, results)
    ref = check_recompute(host_rows, company_rows, results)
    check_company_name_denylist(company_rows, results)
    check_resolved_share(rec, results)
    return results, ref, host_rows, company_rows, rec


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
    parser.add_argument("--spellings", type=int, default=20, help="how many companies to list in the raw-spelling review")
    args = parser.parse_args()
    results, ref, host_rows, _company_rows, rec = run_checks(args.hosts, args.companies)
    print("\n".join(render(results)))
    print("\n## Recomputed numbers (mine)")
    for label, value in metrics(ref, host_rows, rec):
        print(f"- {label}: {value:,}" if isinstance(value, int) else f"- {label}: {value}")
    print(f"\n## Raw spellings: top {args.spellings} companies by distinct spellings")
    for name, n, size, spellings in spelling_review(host_rows, args.spellings):
        print(f"- {name} ({n} spellings, {size} hosts): {spellings}")
    sys.exit(1 if any(not r[1] for r in results) else 0)


if __name__ == "__main__":
    main()
