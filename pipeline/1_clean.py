"""Stage 1: read the raw scan JSON, write data/silver/hosts.parquet (typed, deduped, with D4/D5 flags)."""
import argparse
import importlib.util
import ipaddress
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = ROOT / "data" / "sample" / "spread_100k.jsonl"  # dev input (D3 seek-spread sample)
FULL_PATH = "D:/Cyber_DataSet/2026-09-14T10-00-00.json.zst"  # prod input, read in place, never modified
OUTPUT_PATH = ROOT / "data" / "silver" / "hosts.parquet"
REPORT_SCRIPT = ROOT / ".claude" / "skills" / "pipeline-stage-build" / "scripts" / "stage_report.py"
MATCHER_PATH = ROOT / "scripts" / "denylist_match.py"

MAX_OBJECT_SIZE = 33554432  # RAW-009
NOISE_TAGS = ("honeypot", "c2", "tor", "compromised")  # D4 rule 1
INFRA_TAGS = ("cloud", "cdn")  # D4 rule 2
RAT_MODULE_SUFFIX = "rat"  # D4 rule 1: _shodan.module ending in "rat" (darktrack-rat, njrat, ...)
CERT_YEAR_MIN = 1990  # RAW-007: certificate dates outside this window are sentinels
CERT_YEAR_MAX = 2100
CERT_DATE_FORMAT = "%Y%m%d%H%M%SZ"
VULN_COUNT_CAP = 50  # RAW-006: CVE counts are banner-inferred, so the count is capped
IDENTITY_SOURCES = ("noise", "org", "cert_o", "infrastructure_unresolved", "null_org")

# RAW-011: columns are named explicitly, with only the nested fields this stage keeps; everything else in the raw JSON is ignored.
RAW_COLUMNS = {
    "ip_str": "VARCHAR", "ipv6": "VARCHAR", "port": "BIGINT", "transport": "VARCHAR", "timestamp": "VARCHAR",
    "org": "VARCHAR", "isp": "VARCHAR", "asn": "VARCHAR", "product": "VARCHAR", "version": "VARCHAR",
    "os": "VARCHAR", "cpe": "VARCHAR[]", "hostnames": "VARCHAR[]", "domains": "VARCHAR[]", "tags": "VARCHAR[]",
    "location": "STRUCT(country_code VARCHAR)",
    "cloud": "STRUCT(provider VARCHAR)",
    "_shodan": "STRUCT(module VARCHAR)",
    "vulns": "MAP(VARCHAR, STRUCT(cvss DOUBLE, kev BOOLEAN))",
    "ssl": "STRUCT(cert STRUCT(expires VARCHAR, issued VARCHAR, expired BOOLEAN, "
           "subject STRUCT(CN VARCHAR, O VARCHAR)), versions VARCHAR[])",
}

# Columns of hosts.parquet in order (name, type). The first block is typed data, the second block the flags.
OUTPUT_COLUMNS = (
    ("host_ip", "VARCHAR"), ("port", "BIGINT"), ("transport", "VARCHAR"), ("timestamp", "TIMESTAMP"),
    ("org", "VARCHAR"), ("org_norm", "VARCHAR"), ("isp", "VARCHAR"), ("asn", "VARCHAR"),
    ("country_code", "VARCHAR"), ("product", "VARCHAR"), ("version", "VARCHAR"), ("os", "VARCHAR"),
    ("cpe", "VARCHAR[]"), ("tags", "VARCHAR[]"), ("cloud_provider", "VARCHAR"), ("shodan_module", "VARCHAR"),
    ("cert_expires", "TIMESTAMP"), ("cert_issued", "TIMESTAMP"), ("cert_expired", "BOOLEAN"),
    ("cert_subject_o", "VARCHAR"), ("cert_subject_cn", "VARCHAR"), ("ssl_versions", "VARCHAR[]"),
    ("max_cvss", "DOUBLE"), ("has_kev", "BOOLEAN"), ("vuln_count", "INTEGER"),
    ("hostnames", "VARCHAR[]"), ("domains", "VARCHAR[]"), ("hostnames_count", "INTEGER"), ("domains_count", "INTEGER"),
    ("is_noise", "BOOLEAN"), ("is_infrastructure", "BOOLEAN"), ("infra_reason", "VARCHAR"),
    ("identity_source", "VARCHAR"), ("name_norm", "VARCHAR"),
)
KEY_COLUMNS = (
    "host_ip", "port", "transport", "timestamp", "org", "org_norm", "country_code", "product", "cloud_provider",
    "cert_expires", "cert_subject_o", "max_cvss", "is_noise", "is_infrastructure", "infra_reason", "identity_source", "name_norm",
)


def load_matcher():
    """Import the shared denylist matcher from scripts/ by file path (it is not a package)."""
    spec = importlib.util.spec_from_file_location("denylist_match", MATCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_raw(con, input_path, compressed):
    """Load the named raw columns of the input JSON lines into the DuckDB table raw (RAW-009 options, RAW-011 names)."""
    columns = ", ".join(f"'{name}': '{kind}'" for name, kind in RAW_COLUMNS.items())
    compression = "'zstd'" if compressed else "'auto_detect'"
    path = str(input_path).replace("'", "''")
    con.execute(
        f"CREATE OR REPLACE TABLE raw AS SELECT * FROM read_json('{path}', format='newline_delimited', "
        f"columns={{{columns}}}, compression={compression}, maximum_object_size={MAX_OBJECT_SIZE}, ignore_errors=true)"
    )
    return con.execute("SELECT count(*) FROM raw").fetchone()[0]


def ipv4_ranges(patterns):
    """Return (low, high) integer bounds of every IPv4 CIDR entry in the pattern list."""
    ranges = []
    for pattern in patterns:
        if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", pattern):
            net = ipaddress.ip_network(pattern, strict=False)
            ranges.append((int(net.network_address), int(net.broadcast_address)))
    return ranges


def insert_rows(con, table, width, rows):
    """Insert tuples into a table, doing nothing for an empty list (executemany rejects it)."""
    if rows:
        con.executemany(f"INSERT INTO {table} VALUES ({', '.join(['?'] * width)})", rows)


def build_lookup_tables(con, matcher, rules):
    """Apply the name rules once per DISTINCT org, cert O and IPv6 value and register the results as lookup tables."""
    orgs = [r[0] for r in con.execute("SELECT DISTINCT org FROM raw WHERE org IS NOT NULL").fetchall()]
    org_rows = []
    for org in orgs:
        reason = matcher.infrastructure_reason({"org": org}, rules)
        org_rows.append((org, matcher.normalise(org), reason))
    con.execute("CREATE OR REPLACE TABLE org_lookup(org VARCHAR, org_norm VARCHAR, org_reason VARCHAR)")
    insert_rows(con, "org_lookup", 3, org_rows)

    defaults = matcher.load_cert_defaults()
    cert_rows = []
    for (cert_o,) in con.execute("SELECT DISTINCT ssl.cert.subject.O FROM raw WHERE ssl.cert.subject.O IS NOT NULL").fetchall():
        norm = matcher.normalise(cert_o)
        hit = matcher.match_name(cert_o, "org", rules)  # cert_default_names.txt: denylist exact, prefix and pattern rules, not keywords
        vendor = bool(hit) and hit[0] != "keyword"
        cert_rows.append((cert_o, norm, bool(norm) and norm not in defaults and not vendor))
    con.execute("CREATE OR REPLACE TABLE cert_lookup(cert_o VARCHAR, cert_norm VARCHAR, cert_usable BOOLEAN)")
    insert_rows(con, "cert_lookup", 3, cert_rows)

    v6 = [r[0] for r in con.execute("SELECT DISTINCT ipv6 FROM raw WHERE ip_str IS NULL AND ipv6 IS NOT NULL").fetchall()]
    v6_hits = [(ip,) for ip in v6 if matcher.matches_pattern(ip, rules["patterns"])]
    con.execute("CREATE OR REPLACE TABLE ipv6_pattern_hits(host_ip VARCHAR)")
    insert_rows(con, "ipv6_pattern_hits", 1, v6_hits)


def ip_pattern_sql(rules):
    """Return a SQL boolean expression that is true when host_ip matches a CIDR pattern (IPv4 in SQL, IPv6 from the lookup)."""
    clauses = ["host_ip IN (SELECT host_ip FROM ipv6_pattern_hits)"]
    for low, high in ipv4_ranges(rules["patterns"]):
        clauses.append(f"(ip4 BETWEEN {low} AND {high})")
    return "(" + " OR ".join(clauses) + ")"


def build_flagged(con, rules):
    """Build table flagged: typed columns and D4/D5 flags for every raw row that has a host_ip (before dedupe)."""
    noise_tags = ", ".join(f"'{t}'" for t in NOISE_TAGS)
    infra_tags = ", ".join(f"'{t}'" for t in INFRA_TAGS)
    cert_date = lambda col: (  # noqa: E731
        f"CASE WHEN year(try_strptime({col}, '{CERT_DATE_FORMAT}')) BETWEEN {CERT_YEAR_MIN} AND {CERT_YEAR_MAX} "
        f"THEN try_strptime({col}, '{CERT_DATE_FORMAT}') END"
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE typed AS
        SELECT
            coalesce(nullif(trim(ip_str), ''), nullif(trim(ipv6), '')) AS host_ip,
            port, transport, try_cast(timestamp AS TIMESTAMP) AS timestamp,
            nullif(trim(org), '') AS org, isp, asn,
            location.country_code AS country_code, product, version, os, cpe, tags,
            cloud.provider AS cloud_provider, _shodan.module AS shodan_module,
            {cert_date('ssl.cert.expires')} AS cert_expires,
            {cert_date('ssl.cert.issued')} AS cert_issued,
            ssl.cert.expired AS cert_expired,
            nullif(trim(ssl.cert.subject.O), '') AS cert_subject_o,
            nullif(trim(ssl.cert.subject.CN), '') AS cert_subject_cn,
            ssl.versions AS ssl_versions,
            list_max(list_transform(map_values(vulns), x -> x.cvss)) AS max_cvss,
            coalesce(list_bool_or(list_transform(map_values(vulns), x -> coalesce(x.kev, false))), false) AS has_kev,
            least(coalesce(cardinality(vulns), 0), {VULN_COUNT_CAP})::INTEGER AS vuln_count,
            hostnames, domains,
            coalesce(len(hostnames), 0)::INTEGER AS hostnames_count,
            coalesce(len(domains), 0)::INTEGER AS domains_count,
            coalesce(list_has_any(tags, [{noise_tags}]), false) AS tag_noise,
            coalesce(list_has_any(tags, [{infra_tags}]), false) AS tag_infra,
            CASE WHEN regexp_matches(coalesce(ip_str, ''), '^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+$') THEN
                split_part(ip_str, '.', 1)::BIGINT * 16777216 + split_part(ip_str, '.', 2)::BIGINT * 65536
                + split_part(ip_str, '.', 3)::BIGINT * 256 + split_part(ip_str, '.', 4)::BIGINT END AS ip4
        FROM raw
        """
    )
    pattern_sql = ip_pattern_sql(rules)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE flagged AS
        WITH joined AS (
            SELECT t.*, o.org_norm, o.org_reason, c.cert_norm, coalesce(c.cert_usable, false) AS cert_usable
            FROM typed t
            LEFT JOIN org_lookup o ON t.org = o.org
            LEFT JOIN cert_lookup c ON t.cert_subject_o = c.cert_o
            WHERE t.host_ip IS NOT NULL
        ), reasoned AS (
            SELECT *,
                coalesce(lower(shodan_module) LIKE '%{RAT_MODULE_SUFFIX}', false) OR tag_noise AS is_noise,
                CASE WHEN cloud_provider IS NOT NULL AND cloud_provider <> '' THEN 'cloud_provider'
                     WHEN tag_infra THEN 'tag_rule'
                     WHEN {pattern_sql} THEN 'ip_pattern'
                     ELSE org_reason END AS infra_reason
            FROM joined
        )
        SELECT *, infra_reason IS NOT NULL AS is_infrastructure,
            CASE WHEN is_noise THEN 'noise'
                 WHEN infra_reason IS NULL AND org_norm <> '' THEN 'org'
                 WHEN (infra_reason IS NOT NULL OR org IS NULL) AND cert_usable THEN 'cert_o'
                 WHEN infra_reason IS NOT NULL THEN 'infrastructure_unresolved'
                 ELSE 'null_org' END AS identity_source
        FROM reasoned
        """
    )


def dedupe_and_select(con):
    """Build table out: one row per (host_ip, port, transport), latest timestamp kept, ties broken by a row hash."""
    names = ", ".join(name for name, _ in OUTPUT_COLUMNS if name not in ("name_norm",))
    con.execute(
        f"""
        CREATE OR REPLACE TABLE out AS
        SELECT {names},
            CASE identity_source WHEN 'org' THEN org_norm WHEN 'cert_o' THEN cert_norm END AS name_norm
        FROM (
            SELECT *, row_number() OVER (
                PARTITION BY host_ip, port, transport
                ORDER BY timestamp DESC NULLS LAST, hash(org, isp, product, version, shodan_module, cert_subject_o, cast(tags AS VARCHAR)) DESC
            ) AS rn
            FROM flagged
        ) WHERE rn = 1
        ORDER BY host_ip, port, transport
        """
    )


def write_output(con, output_path):
    """Write table out to the silver parquet path."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    safe = str(output_path).replace("'", "''")
    con.execute(f"COPY out TO '{safe}' (FORMAT PARQUET)")


def run_stage(con, input_path, output_path, compressed=False):
    """Run read, flag, dedupe and write for one input; return the raw and intermediate row counts."""
    matcher = load_matcher()
    rules = matcher.load_rules()
    raw_rows = read_raw(con, input_path, compressed)
    build_lookup_tables(con, matcher, rules)
    build_flagged(con, rules)
    dedupe_and_select(con)
    write_output(con, output_path)
    flagged_rows = con.execute("SELECT count(*) FROM flagged").fetchone()[0]
    out_rows = con.execute("SELECT count(*) FROM out").fetchone()[0]
    return {"raw_rows": raw_rows, "no_host_ip": raw_rows - flagged_rows, "flagged_rows": flagged_rows, "out_rows": out_rows}


def share_table(con, table, column, total):
    """Return (value, rows, percent) triples for a categorical column of a table, largest first."""
    rows = con.execute(f"SELECT coalesce({column}, '(none)'), count(*) FROM {table} GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()
    return [(value, n, 100 * n / total) for value, n in rows]


def print_flag_report(con, counts):
    """Print infrastructure share, infra_reason mix before and after dedupe, and identity_source shares."""
    total = counts["out_rows"]
    pre = counts["flagged_rows"]
    infra = con.execute("SELECT count(*) FROM out WHERE is_infrastructure").fetchone()[0]
    infra_pre = con.execute("SELECT count(*) FROM flagged WHERE is_infrastructure").fetchone()[0]
    print(f"\ninfrastructure rows: {infra:,} of {total:,} = {100 * infra / total:.2f}% (before dedupe {infra_pre:,} of {pre:,} = {100 * infra_pre / pre:.2f}%)")
    print(f"surviving (not infrastructure): {total - infra:,} = {100 * (total - infra) / total:.2f}%")
    print("\ninfra_reason (after dedupe | before dedupe):")
    before = {v: n for v, n, _ in share_table(con, "flagged", "infra_reason", pre)}
    for value, n, pct in share_table(con, "out", "infra_reason", total):
        print(f"  {value:<16} {n:>8,} {pct:>6.2f}%  | {before.get(value, 0):>8,}")
    print("\nidentity_source (rows):")
    shares = share_table(con, "out", "identity_source", total)
    for value, n, pct in shares:
        print(f"  {value:<26} {n:>8,} {pct:>6.2f}%")
    print(f"  sum of shares: {sum(pct for _, _, pct in shares):.2f}%")
    noise = con.execute("SELECT count(*) FROM out WHERE is_noise").fetchone()[0]
    print(f"is_noise rows: {noise:,} ({100 * noise / total:.2f}%)")


def print_report(con, counts, input_path, output_path, compressed):
    """Print the mandatory stage report: rows, difference vs raw, null rates, 5 random rows, flag shares."""
    spec = importlib.util.spec_from_file_location("stage_report", REPORT_SCRIPT)
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    out_path = str(output_path)
    total = report.count_rows(con, out_path)
    print(f"== Stage report: {out_path}")
    print(f"rows: {total:,}")
    removed = counts["flagged_rows"] - counts["out_rows"]
    print(f"previous layer (raw input rows parsed): {counts['raw_rows']:,} | change: {total - counts['raw_rows']:+,}")
    print(f"  explained: {counts['no_host_ip']:,} rows without ip_str or ipv6 dropped; {removed:,} duplicate (host_ip, port, transport) rows removed")
    if not compressed:
        with open(input_path, "rb") as handle:
            lines = sum(1 for _ in handle)
        print(f"  input file lines: {lines:,}; lines not parsed (ignore_errors): {lines - counts['raw_rows']:,}")
    print("\nnull rates of key columns (worst first):")
    for name, pct in report.null_rates(con, out_path, KEY_COLUMNS, total):
        print(f"  {name:<30} {pct:>6}%")
    print("\n5 random rows:")
    cur = con.execute(f"SELECT * FROM read_parquet('{out_path}') USING SAMPLE reservoir(5 ROWS)")
    names = [d[0] for d in cur.description]
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  [{i}] " + ", ".join(f"{n}={str(v)[:40]}" for n, v in zip(names, row)))
    print_flag_report(con, counts)
    for field in ("expires", "issued"):
        nulled = con.execute(
            f"SELECT count(*) FROM raw WHERE ssl.cert.{field} IS NOT NULL AND coalesce(year(try_strptime(ssl.cert.{field}, '{CERT_DATE_FORMAT}')), 0) "
            "NOT BETWEEN ? AND ?", [CERT_YEAR_MIN, CERT_YEAR_MAX]
        ).fetchone()[0]
        print(f"raw cert {field} values nulled (unparseable or outside {CERT_YEAR_MIN}..{CERT_YEAR_MAX}), before dedupe: {nulled:,}")


def main():
    """Run the stage end to end on the sample (default) or the full compressed source (--full)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="read the compressed full source in place (not for dev)")
    parser.add_argument("--input", help="override the input JSON lines path")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="output parquet path")
    args = parser.parse_args()
    input_path = args.input or (FULL_PATH if args.full else str(SAMPLE_PATH))
    compressed = args.full or str(input_path).endswith(".zst")
    con = duckdb.connect()
    counts = run_stage(con, input_path, args.output, compressed)
    print_report(con, counts, input_path, args.output, compressed)


if __name__ == "__main__":
    sys.exit(main())
