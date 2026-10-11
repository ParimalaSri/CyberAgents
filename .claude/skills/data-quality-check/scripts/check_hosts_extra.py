"""Independent hosts-layer checks: denylist on identity_source='org' rows, recomputation from the raw sample, open-choice counts."""
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[4]
RAW_PATH = REPO_ROOT / "data" / "sample" / "spread_100k.jsonl"
HOSTS_PATH = REPO_ROOT / "data" / "silver" / "hosts.parquet"
NOISE_TAGS = {"honeypot", "c2", "tor", "compromised"}
RAW_COLUMNS = (
    "{'ip_str': 'VARCHAR', 'ipv6': 'VARCHAR', 'port': 'BIGINT', 'transport': 'VARCHAR', 'timestamp': 'VARCHAR', 'org': 'VARCHAR', "
    "'tags': 'VARCHAR[]', 'hostnames': 'VARCHAR[]', 'cloud': 'STRUCT(provider VARCHAR)', '_shodan': 'STRUCT(module VARCHAR)', "
    "'vulns': 'MAP(VARCHAR, STRUCT(cvss DOUBLE, kev BOOLEAN))', "
    "'ssl': 'STRUCT(cert STRUCT(expires VARCHAR, issued VARCHAR, subject STRUCT(O VARCHAR)))'}"
)


def load_matcher():
    """Import the shared matcher from scripts/ and return the module."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import denylist_match
    return denylist_match


def line(text=""):
    """Print one markdown line."""
    print(text)


def org_subset_denylist(con, matcher, rules):
    """Apply the shared rules to org and name_norm of identity_source='org' rows; return the hit list."""
    hits = []
    rows = con.execute("SELECT org, name_norm, count(*) FROM hosts WHERE identity_source = 'org' GROUP BY 1, 2").fetchall()
    for org, name_norm, n in rows:
        for column, value in (("org", org), ("name_norm", name_norm)):
            hit = matcher.match_name(value, "org", rules)
            if hit:
                hits.append((column, value, n, hit[0], hit[1]))
    line("## Denylist on identity_source = 'org' rows (org and name_norm, shared rules)")
    line(f"- distinct (org, name_norm) pairs checked: {len(rows):,}; hits: {len(hits)}")
    for hit in sorted(hits, key=lambda h: -h[2])[:10]:
        line(f"  - {hit}")
    line()
    return hits


def recompute(con, matcher, rules):
    """Recompute row counts, dedupe, infrastructure and noise flags and identity_source from the raw sample; print a table."""
    raw_lines = sum(1 for _ in open(RAW_PATH, "rb"))
    con.execute(f"CREATE TABLE raw AS SELECT * FROM read_json('{RAW_PATH.as_posix()}', format='newline_delimited', columns={RAW_COLUMNS}, "
                "maximum_object_size=33554432, ignore_errors=true)")
    parsed = con.execute("SELECT count(*) FROM raw").fetchone()[0]
    con.execute("CREATE TABLE r AS SELECT row_number() OVER () AS rid, coalesce(nullif(trim(ip_str), ''), nullif(trim(ipv6), '')) AS host_ip, "
                "port, transport, try_cast(timestamp AS TIMESTAMP) AS ts, nullif(trim(org), '') AS org, tags, cloud.provider AS cp, "
                "_shodan.module AS module, ssl.cert.subject.O AS cert_o, hostnames FROM raw")
    with_ip = con.execute("SELECT count(*) FROM r WHERE host_ip IS NOT NULL").fetchone()[0]
    groups = con.execute("SELECT count(*) FROM (SELECT 1 FROM r WHERE host_ip IS NOT NULL GROUP BY host_ip, port, transport)").fetchone()[0]
    out_rows = con.execute("SELECT count(*) FROM hosts").fetchone()[0]
    key_diff = con.execute("SELECT count(*) FROM (SELECT host_ip, port, transport FROM r WHERE host_ip IS NOT NULL EXCEPT "
                           "SELECT host_ip, port, transport FROM hosts) ").fetchone()[0]
    key_diff2 = con.execute("SELECT count(*) FROM (SELECT host_ip, port, transport FROM hosts EXCEPT "
                            "SELECT host_ip, port, transport FROM r WHERE host_ip IS NOT NULL)").fetchone()[0]
    bad_latest = con.execute("SELECT count(*) FROM hosts h JOIN (SELECT host_ip, port, transport, max(ts) AS mx FROM r GROUP BY ALL) g "
                             "USING (host_ip, port, transport) WHERE h.timestamp IS DISTINCT FROM g.mx").fetchone()[0]
    dup_groups = con.execute("SELECT count(*), sum(n) FROM (SELECT count(*) AS n FROM r WHERE host_ip IS NOT NULL GROUP BY host_ip, port, transport "
                             "HAVING count(*) > 1)").fetchone()
    exact_dup = con.execute("SELECT count(*) FROM (SELECT 1 FROM r WHERE host_ip IS NOT NULL GROUP BY host_ip, port, transport "
                            "HAVING count(*) > 1 AND count(DISTINCT ts) = 1)").fetchone()[0]
    line("## Recomputation (author number vs mine)")
    line(f"- raw lines {raw_lines:,}; parsed rows {parsed:,}; rows with host_ip {with_ip:,}; distinct keys {groups:,}; hosts rows {out_rows:,}; removed {with_ip - groups:,}")
    line(f"- duplicate groups {dup_groups[0]:,} covering {dup_groups[1]:,} rows; groups with a single distinct timestamp (true copies) {exact_dup:,}")
    line(f"- raw keys missing from hosts {key_diff}; hosts keys not in raw {key_diff2}; kept row not the latest timestamp {bad_latest}")

    rows = con.execute("SELECT rid, host_ip, port, transport, ts, org, tags, cp, module, cert_o FROM r WHERE host_ip IS NOT NULL").fetchall()
    defaults = matcher.load_cert_defaults()
    mine = {}
    for rid, host_ip, port, transport, ts, org, tags, cp, module, cert_o in rows:
        reason = matcher.infrastructure_reason({"org": org, "cloud_provider": cp, "tags": tags or [], "ip": host_ip}, rules)
        noise = bool(NOISE_TAGS & set(tags or [])) or (module or "").lower().endswith("rat")
        norm = matcher.normalise(org) if org else None
        cert_norm = matcher.normalise(cert_o) if cert_o and cert_o.strip() else None
        hit = matcher.match_name(cert_o, "org", rules) if cert_o else None
        usable = bool(cert_norm) and cert_norm not in defaults and not (hit and hit[0] != "keyword")
        if noise:
            source = "noise"
        elif reason is None and norm:
            source = "org"
        elif (reason is not None or org is None) and usable:
            source = "cert_o"
        elif reason is not None:
            source = "infrastructure_unresolved"
        else:
            source = "null_org"
        mine[(host_ip, port, transport, ts)] = (reason, noise, source)
    pre_infra = sum(1 for v in mine.values() if v[0])
    line(f"- infrastructure before dedupe (my matcher run, raw rows with host_ip): {pre_infra:,} of {len(mine):,} = {100 * pre_infra / len(mine):.2f}%")

    hosts = con.execute("SELECT host_ip, port, transport, timestamp, is_infrastructure, infra_reason, is_noise, identity_source FROM hosts").fetchall()
    mism = {"infra_reason": 0, "is_noise": 0, "identity_source": 0, "missing": 0}
    examples = []
    for host_ip, port, transport, ts, infra, reason, noise, source in hosts:
        got = mine.get((host_ip, port, transport, ts))
        if got is None:
            mism["missing"] += 1
            continue
        if got[0] != reason:
            mism["infra_reason"] += 1
            examples.append((host_ip, port, "infra_reason", got[0], reason))
        if got[1] != noise:
            mism["is_noise"] += 1
        if got[2] != source:
            mism["identity_source"] += 1
            examples.append((host_ip, port, "identity_source", got[2], source))
    infra_post = sum(1 for h in hosts if h[4])
    line(f"- infrastructure after dedupe (parquet): {infra_post:,} of {len(hosts):,} = {100 * infra_post / len(hosts):.2f}%")
    line(f"- per-row disagreement between my flags (matcher + D4 rules applied in Python) and the parquet: {mism}; examples {examples[:5]}")
    for column in ("infra_reason", "identity_source"):
        rows = con.execute(f"SELECT coalesce({column}, '(null)'), count(*), round(100.0 * count(*) / sum(count(*)) OVER (), 2) FROM hosts GROUP BY 1 ORDER BY 2 DESC").fetchall()
        line(f"- {column} mix (parquet): {rows}; shares sum {sum(r[2] for r in rows):.2f}")
    line()


def open_choices(con):
    """Print the numbers for the author's open choices (RAT rule, cert_o, vuln cap, cert-date nulling, hostnames lost on dedupe)."""
    line("## Open choices, measured")
    rat = con.execute("SELECT count(*) FROM r WHERE host_ip IS NOT NULL AND lower(module) LIKE '%rat'").fetchone()[0]
    rat_out = con.execute("SELECT count(*) FROM hosts WHERE lower(shodan_module) LIKE '%rat'").fetchone()[0]
    rat_noise = con.execute("SELECT count(*) FROM hosts WHERE lower(shodan_module) LIKE '%rat' AND is_noise").fetchone()[0]
    line(f"- RAT module (ends 'rat'): raw rows {rat}; hosts rows {rat_out}; flagged is_noise {rat_noise}")
    rows = con.execute("SELECT shodan_module, count(*), sum(is_noise::INT) FROM hosts WHERE lower(shodan_module) LIKE '%rat' OR lower(shodan_module) LIKE '%backdoor%' "
                       "OR lower(shodan_module) LIKE '%njrat%' GROUP BY 1 ORDER BY 2 DESC").fetchall()
    line(f"  modules (module, rows, noise rows): {rows}")
    rows = con.execute("SELECT shodan_module, count(*) FROM hosts WHERE NOT is_noise AND (lower(shodan_module) LIKE '%rat%' OR lower(shodan_module) LIKE '%c2%' "
                       "OR lower(shodan_module) LIKE '%backdoor%' OR lower(shodan_module) LIKE '%trojan%') GROUP BY 1 ORDER BY 2 DESC").fetchall()
    line(f"  not-noise rows whose module name contains rat/c2/backdoor/trojan: {rows}")
    rows = con.execute("SELECT identity_source, count(*), sum((org IS NULL)::INT), sum(is_infrastructure::INT) FROM hosts WHERE cert_subject_o IS NOT NULL GROUP BY 1 ORDER BY 2 DESC").fetchall()
    line(f"- cert O present, by identity_source (source, rows, org null, infrastructure): {rows}")
    rows = con.execute("SELECT count(*) FROM hosts WHERE identity_source = 'org' AND cert_subject_o IS NOT NULL").fetchone()[0]
    line(f"  org rows that also carry a cert O (kept as evidence only per D4): {rows}")
    capped = con.execute("SELECT count(*), max(vuln_count) FROM hosts WHERE vuln_count = 50").fetchone()
    raw_ge50 = con.execute("SELECT count(*) FROM raw WHERE (coalesce(ip_str, ipv6) IS NOT NULL) AND coalesce(cardinality(vulns), 0) >= 50").fetchone()[0]
    line(f"- vuln_count == 50 in hosts: {capped[0]} (max {capped[1]}); raw rows with >= 50 CVEs {raw_ge50} (before dedupe)")
    lost = con.execute("SELECT count(*) FROM raw WHERE (ssl.cert.expires IS NOT NULL) AND coalesce(year(try_strptime(ssl.cert.expires, '%Y%m%d%H%M%SZ')), 0) NOT BETWEEN 1990 AND 2100").fetchone()[0]
    lost2 = con.execute("SELECT count(*) FROM raw WHERE (ssl.cert.issued IS NOT NULL) AND coalesce(year(try_strptime(ssl.cert.issued, '%Y%m%d%H%M%SZ')), 0) NOT BETWEEN 1990 AND 2100").fetchone()[0]
    epoch = con.execute("SELECT count(*) FROM raw WHERE ssl.cert.issued LIKE '1970%'").fetchone()[0]
    line(f"- raw cert dates outside 1990..2100 or unparseable (before dedupe): expires {lost}, issued {lost2} (of which 1970 epoch placeholders {epoch})")
    in_out = con.execute("SELECT count(*) FROM hosts WHERE cert_expires IS NULL AND cert_expired IS NOT NULL").fetchone()[0]
    line(f"  hosts rows with cert_expires null but cert_expired (boolean) present: {in_out}")
    hn = con.execute("SELECT count(*), sum(extra) FROM (SELECT count(DISTINCT cast(hostnames AS VARCHAR)) - 1 AS extra FROM r WHERE host_ip IS NOT NULL "
                     "GROUP BY host_ip, port, transport HAVING count(*) > 1) WHERE extra > 0").fetchone()
    line(f"- dedupe: groups whose copies carry different hostnames arrays {hn[0]}, extra distinct arrays dropped {hn[1]}")
    line()


def main():
    """Run the extra checks against the hosts parquet and the raw sample, print markdown."""
    matcher = load_matcher()
    rules = matcher.load_rules()
    con = duckdb.connect()
    con.execute(f"CREATE VIEW hosts AS SELECT * FROM read_parquet('{HOSTS_PATH.as_posix()}')")
    hits = org_subset_denylist(con, matcher, rules)
    recompute(con, matcher, rules)
    open_choices(con)
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
