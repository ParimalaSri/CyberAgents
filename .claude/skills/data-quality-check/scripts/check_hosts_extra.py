"""Independent hosts-layer checks: denylist on org rows, cert_o assertions, recomputation from the raw sample, open-choice counts."""
import re
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[4]
RAW_PATH = REPO_ROOT / "data" / "sample" / "spread_100k.jsonl"
HOSTS_PATH = REPO_ROOT / "data" / "silver" / "hosts.parquet"
NOISE_TAGS = {"honeypot", "c2", "tor", "compromised"}
NOISE_MODULE_REGEX = re.compile(r"(^|-)rat$|^njrat$|^blackshades$")  # D6.1, written again here on purpose (independent of the stage)
CERT_YEAR_MIN = 1990
CERT_YEAR_MAX = 2100
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


def cert_usable(cert_o, matcher, rules, defaults):
    """Return True when a cert O can name a tenant: non-empty after normalise, not a cert default, hits no shared rule of any type (D6.4)."""
    if cert_o is None or not cert_o.strip():
        return False
    norm = matcher.normalise(cert_o)
    return bool(norm) and norm not in defaults and matcher.match_name(cert_o, "org", rules) is None


def recompute_flags(row, matcher, rules, defaults):
    """Return (infra_reason, is_noise, identity_source, name_norm) for one raw row dict, applying D4/D5/D6 in Python."""
    org = row["org"]
    reason = matcher.infrastructure_reason({"org": org, "cloud_provider": row["cp"], "tags": row["tags"] or [], "ip": row["host_ip"]}, rules)
    noise = bool(NOISE_TAGS & set(row["tags"] or [])) or bool(NOISE_MODULE_REGEX.search((row["module"] or "").lower()))
    norm = matcher.normalise(org) if org else None
    usable = cert_usable(row["cert_o"], matcher, rules, defaults)
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
    name = norm if source == "org" else (matcher.normalise(row["cert_o"]) if source == "cert_o" else None)
    return reason, noise, source, name


def cert_o_default_rows(con, matcher, defaults):
    """Assertion (a): return (name_norm, rows) of cert_o rows whose name_norm or normalised cert O is in the cert defaults; expect none."""
    bad = {}
    rows = con.execute("SELECT name_norm, cert_subject_o, count(*) FROM hosts WHERE identity_source = 'cert_o' GROUP BY 1, 2").fetchall()
    for name_norm, cert_o, n in rows:
        if matcher.normalise(name_norm) in defaults or matcher.normalise(cert_o) in defaults:
            bad[name_norm] = bad.get(name_norm, 0) + n
    return sorted(bad.items(), key=lambda kv: -kv[1])


def cert_o_disagreements(mine, parquet_rows):
    """Assertion (b): compare my cert_o rows (key -> name) with the parquet's; return (only_mine, only_parquet, name_mismatch) lists."""
    theirs = {key: name for key, source, name in parquet_rows if source == "cert_o"}
    only_mine = [k for k in mine if k not in theirs]
    only_theirs = [k for k in theirs if k not in mine]
    names = [k for k in mine if k in theirs and mine[k] != theirs[k]]
    return only_mine, only_theirs, names


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


def load_raw(con, narrow):
    """Create table r (one row per raw line, narrow columns) from a narrow parquet, or from the raw JSON lines when narrow is None."""
    if narrow:
        con.execute("CREATE TABLE r AS SELECT rid, coalesce(nullif(trim(ip_str), ''), nullif(trim(ipv6), '')) AS host_ip, port, transport, "
                    "try_cast(timestamp AS TIMESTAMP) AS ts, nullif(trim(org), '') AS org, tags, cp, module, cert_o, cexp, ciss "
                    f"FROM read_parquet('{Path(narrow).as_posix()}')")
        return None
    con.execute(f"CREATE TABLE raw AS SELECT * FROM read_json('{RAW_PATH.as_posix()}', format='newline_delimited', columns={RAW_COLUMNS}, "
                "maximum_object_size=33554432, ignore_errors=true)")
    con.execute("CREATE TABLE r AS SELECT row_number() OVER () AS rid, coalesce(nullif(trim(ip_str), ''), nullif(trim(ipv6), '')) AS host_ip, "
                "port, transport, try_cast(timestamp AS TIMESTAMP) AS ts, nullif(trim(org), '') AS org, tags, cloud.provider AS cp, "
                "_shodan.module AS module, ssl.cert.subject.O AS cert_o, ssl.cert.expires AS cexp, ssl.cert.issued AS ciss, hostnames FROM raw")
    return sum(1 for _ in open(RAW_PATH, "rb"))


def cert_invalid(cexp, ciss):
    """Return True when a raw cert date text is present but unparseable or outside CERT_YEAR_MIN..CERT_YEAR_MAX (D6.3)."""
    for text in (cexp, ciss):
        if text is None:
            continue
        match = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})Z$", text)
        if not match:
            return True
        year, month, day, hour, minute, second = (int(g) for g in match.groups())
        valid_clock = 1 <= month <= 12 and 1 <= day <= 31 and hour < 24 and minute < 60 and second < 60
        if not valid_clock or not CERT_YEAR_MIN <= year <= CERT_YEAR_MAX:
            return True
    return False


def cert_o_assertions(con, matcher, defaults, hosts, mine_cert):
    """Print and return the two D6.4 assertions: (a) no cert_o name is a cert default, (b) my cert-O usability agrees with the stage."""
    bad_defaults = cert_o_default_rows(con, matcher, defaults)
    line("## cert_o assertions (D6.4)")
    line(f"- (a) cert_o rows whose name is in the cert defaults: {sum(n for _, n in bad_defaults)} rows over {len(bad_defaults)} names; {bad_defaults[:5]}")
    parquet_rows = [((h[0], h[1], h[2]), h[7], h[8]) for h in hosts]
    only_mine, only_theirs, names = cert_o_disagreements(mine_cert, parquet_rows)
    line(f"- (b) cert_o rows by my recomputation {len(mine_cert):,}, by the stage {sum(1 for r in parquet_rows if r[1] == 'cert_o'):,}; "
         f"only mine {len(only_mine)}, only stage {len(only_theirs)}, name_norm differs {len(names)}; examples {(only_mine + only_theirs + names)[:5]}")
    line()
    return bad_defaults, only_mine, only_theirs, names


def recompute(con, matcher, rules, narrow=None):
    """Recompute rows, dedupe, dup_count, flags, cert_date_invalid and identity_source from the raw sample; return the cert_o assertion failures."""
    raw_lines = load_raw(con, narrow)
    parsed = con.execute("SELECT count(*) FROM r").fetchone()[0]
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
    dup_extra = con.execute("SELECT coalesce(sum(dup_count - 1), 0) FROM hosts").fetchone()[0]
    dup_bad = con.execute("SELECT count(*) FROM hosts h JOIN (SELECT host_ip, port, transport, count(*) AS n FROM r WHERE host_ip IS NOT NULL "
                          "GROUP BY ALL) g USING (host_ip, port, transport) WHERE h.dup_count <> g.n").fetchone()[0]
    line("## Recomputation (author number vs mine)")
    line(f"- raw lines {raw_lines if raw_lines is not None else '(narrow parquet used)'}; parsed rows {parsed:,}; rows with host_ip {with_ip:,}; "
         f"distinct keys {groups:,}; hosts rows {out_rows:,}; removed {with_ip - groups:,}")
    line(f"- duplicate groups {dup_groups[0]:,} covering {dup_groups[1]:,} rows; groups with a single distinct timestamp (true copies) {exact_dup:,}")
    line(f"- raw keys missing from hosts {key_diff}; hosts keys not in raw {key_diff2}; kept row not the latest timestamp {bad_latest}")
    line(f"- sum(dup_count - 1) = {dup_extra:,}; raw rows with host_ip minus hosts rows = {with_ip - out_rows:,}; dup_count differing from my per-key count: {dup_bad}")

    rows = con.execute("SELECT host_ip, port, transport, ts, org, tags, cp, module, cert_o, cexp, ciss FROM r WHERE host_ip IS NOT NULL").fetchall()
    defaults = matcher.load_cert_defaults()
    mine = {}
    mine_invalid = {}
    for host_ip, port, transport, ts, org, tags, cp, module, cert_o, cexp, ciss in rows:
        row = {"host_ip": host_ip, "org": org, "tags": tags, "cp": cp, "module": module, "cert_o": cert_o}
        mine[(host_ip, port, transport, ts)] = recompute_flags(row, matcher, rules, defaults)
        mine_invalid[(host_ip, port, transport, ts)] = cert_invalid(cexp, ciss)
    pre_infra = sum(1 for v in mine.values() if v[0])
    line(f"- infrastructure before dedupe (my matcher run, raw rows with host_ip): {pre_infra:,} of {len(mine):,} = {100 * pre_infra / len(mine):.2f}%")

    hosts = con.execute("SELECT host_ip, port, transport, timestamp, is_infrastructure, infra_reason, is_noise, identity_source, name_norm, "
                        "cert_date_invalid FROM hosts").fetchall()
    mism = {"infra_reason": 0, "is_noise": 0, "identity_source": 0, "name_norm": 0, "cert_date_invalid": 0, "missing": 0}
    examples = []
    mine_cert = {}
    for host_ip, port, transport, ts, infra, reason, noise, source, name_norm, invalid in hosts:
        key = (host_ip, port, transport, ts)
        got = mine.get(key)
        if got is None:
            mism["missing"] += 1
            continue
        if got[2] == "cert_o":
            mine_cert[key[:3]] = got[3]
        for field, mine_value, stage_value in (("infra_reason", got[0], reason), ("is_noise", got[1], noise), ("identity_source", got[2], source),
                                               ("name_norm", got[3], name_norm), ("cert_date_invalid", mine_invalid[key], invalid)):
            if mine_value != stage_value:
                mism[field] += 1
                examples.append((host_ip, port, field, mine_value, stage_value))
    infra_post = sum(1 for h in hosts if h[4])
    line(f"- infrastructure after dedupe (parquet): {infra_post:,} of {len(hosts):,} = {100 * infra_post / len(hosts):.2f}%")
    line(f"- per-row disagreement between my flags (matcher + D4/D6 rules in Python) and the parquet over {len(hosts):,} rows: {mism}; examples {examples[:5]}")
    line(f"- is_noise rows {sum(1 for h in hosts if h[6]):,}; cert_date_invalid rows {sum(1 for h in hosts if h[9]):,} "
         f"(mine: {sum(1 for h in hosts if mine_invalid.get((h[0], h[1], h[2], h[3])))})")
    for column in ("infra_reason", "identity_source"):
        rows = con.execute(f"SELECT coalesce({column}, '(null)'), count(*), round(100.0 * count(*) / sum(count(*)) OVER (), 2) FROM hosts GROUP BY 1 ORDER BY 2 DESC").fetchall()
        line(f"- {column} mix (parquet): {rows}; shares sum {sum(r[2] for r in rows):.2f}")
    line()
    return cert_o_assertions(con, matcher, defaults, hosts, mine_cert), mism


def open_choices(con, have_raw):
    """Print the numbers for the author's open choices (RAT rule, cert_o, vuln cap, cert-date nulling, hostnames lost on dedupe)."""
    line("## Open choices, measured")
    rat = con.execute("SELECT count(*) FROM r WHERE host_ip IS NOT NULL AND regexp_matches(lower(module), '(^|-)rat$|^njrat$|^blackshades$')").fetchone()[0]
    rat_out = con.execute("SELECT count(*) FROM hosts WHERE regexp_matches(lower(shodan_module), '(^|-)rat$|^njrat$|^blackshades$')").fetchone()[0]
    rat_noise = con.execute("SELECT count(*) FROM hosts WHERE regexp_matches(lower(shodan_module), '(^|-)rat$|^njrat$|^blackshades$') AND is_noise").fetchone()[0]
    line(f"- RAT module (D6.1 pattern): raw rows {rat}; hosts rows {rat_out}; flagged is_noise {rat_noise}")
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
    if have_raw:
        raw_ge50 = con.execute("SELECT count(*) FROM raw WHERE (coalesce(ip_str, ipv6) IS NOT NULL) AND coalesce(cardinality(vulns), 0) >= 50").fetchone()[0]
        line(f"- vuln_count == 50 in hosts: {capped[0]} (max {capped[1]}); raw rows with >= 50 CVEs {raw_ge50} (before dedupe)")
    else:
        line(f"- vuln_count == 50 in hosts: {capped[0]} (max {capped[1]}); raw CVE count not in the narrow parquet")
    parse = "year(try_strptime({c}, '%Y%m%d%H%M%SZ'))"
    lost = con.execute(f"SELECT count(*) FROM r WHERE cexp IS NOT NULL AND coalesce({parse.format(c='cexp')}, 0) NOT BETWEEN 1990 AND 2100").fetchone()[0]
    lost2 = con.execute(f"SELECT count(*) FROM r WHERE ciss IS NOT NULL AND coalesce({parse.format(c='ciss')}, 0) NOT BETWEEN 1990 AND 2100").fetchone()[0]
    epoch = con.execute("SELECT count(*) FROM r WHERE ciss LIKE '1970%'").fetchone()[0]
    line(f"- raw cert dates outside 1990..2100 or unparseable (before dedupe): expires {lost}, issued {lost2} (of which 1970 epoch placeholders {epoch})")
    in_out = con.execute("SELECT count(*) FROM hosts WHERE cert_expires IS NULL AND cert_expired IS NOT NULL").fetchone()[0]
    line(f"  hosts rows with cert_expires null but cert_expired (boolean) present: {in_out}")
    line()


def main():
    """Run the extra checks against the hosts parquet and the raw sample (or --narrow parquet), print markdown, exit 1 on any failure."""
    narrow = sys.argv[sys.argv.index("--narrow") + 1] if "--narrow" in sys.argv else None
    matcher = load_matcher()
    rules = matcher.load_rules()
    con = duckdb.connect()
    con.execute(f"CREATE VIEW hosts AS SELECT * FROM read_parquet('{HOSTS_PATH.as_posix()}')")
    hits = org_subset_denylist(con, matcher, rules)
    (cert_failures, mism) = recompute(con, matcher, rules, narrow)
    open_choices(con, narrow is None)
    bad_defaults, only_mine, only_theirs, names = cert_failures
    failed = bool(hits or bad_defaults or only_mine or only_theirs or names or any(mism.values()))
    print("RESULT: " + ("FAIL" if failed else "PASS"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
