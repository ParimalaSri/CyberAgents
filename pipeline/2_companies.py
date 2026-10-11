"""Stage 2: group hosts into companies by exact name_norm (D8), write data/silver/companies.parquet and the D8.7 report."""
import argparse
import datetime
import importlib.util
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
HOSTS_PATH = ROOT / "data" / "silver" / "hosts.parquet"  # dev input (stage 1 output)
FULL_HOSTS_PATH = ROOT / "data" / "silver" / "hosts_full.parquet"  # prod input: stage 1 has no separate full file, run it with --full --output this path
OUTPUT_PATH = ROOT / "data" / "silver" / "companies.parquet"
FULL_OUTPUT_PATH = ROOT / "data" / "silver" / "companies_full.parquet"
REPORT_DIR = ROOT / "outputs" / "dq"
GUARD_SCRIPT = ROOT / "scripts" / "path_guard.py"
REPORT_SCRIPT = ROOT / ".claude" / "skills" / "pipeline-stage-build" / "scripts" / "stage_report.py"

MEMBER_SOURCES = ("org", "cert_o")  # D8.3: only these identity_source values create companies
IDENTITY_SOURCES = ("org", "cert_o", "noise", "infrastructure_unresolved", "null_org")
D4_PRECEDENCE = ("noise", "org", "cert_o", "infrastructure_unresolved", "null_org")  # D8.7 section 2: an IP takes the first source it has
INFRA_REASONS = ("cloud_provider", "tag_rule", "ip_pattern", "org_exact", "org_prefix", "org_pattern", "org_keyword")
HASH_LENGTH = 16  # D8.3: first 16 hex characters of sha256(name_norm)
BUCKETS = (("1 (singleton)", 1, 1), ("2", 2, 2), ("3 to 5", 3, 5), ("6 to 20", 6, 20), ("21 to 100", 21, 100), ("over 100", 101, None))
TOP_COMPANIES = 20
TOP_SPELLINGS = 10
NOISE_SHARE_FLAG = 0.5  # D8.6 preview threshold, reported only (M2 calibrates)
RESOLVED_SHARE_RANGE = (5.0, 20.0)  # D8.8 rule 7, reported only
OUTPUT_COLUMNS = (
    ("company_id", "VARCHAR"), ("company_name", "VARCHAR"), ("name_norm", "VARCHAR"), ("identity_source", "VARCHAR"),
    ("identity_confidence", "VARCHAR"), ("org_host_count", "INTEGER"), ("cert_o_host_count", "INTEGER"), ("host_count", "INTEGER"),
    ("distinct_host_ips", "INTEGER"), ("distinct_port_count", "INTEGER"), ("country_code", "VARCHAR"), ("country_count", "INTEGER"),
    ("noise_host_count", "INTEGER"), ("noise_host_share", "DOUBLE"),
)
KEY_COLUMNS = tuple(name for name, _ in OUTPUT_COLUMNS)


def load_guard():
    """Import the shared output-path guard from scripts/ by file path (it is not a package)."""
    spec = importlib.util.spec_from_file_location("path_guard", GUARD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quote_path(path):
    """Return a path as a forward-slash string with single quotes escaped, for SQL literals."""
    return Path(path).as_posix().replace("'", "''")


def build_members(con, hosts_path):
    """Create table members (participating host rows with their raw display text) and table noise_by_org."""
    sources = ", ".join(f"'{s}'" for s in MEMBER_SOURCES)
    con.execute(f"CREATE OR REPLACE TABLE hosts AS SELECT * FROM read_parquet('{quote_path(hosts_path)}')")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE members AS
        SELECT name_norm, identity_source, host_ip, port, country_code,
            CASE identity_source WHEN 'org' THEN org ELSE cert_subject_o END AS raw_text
        FROM hosts WHERE identity_source IN ({sources}) AND name_norm IS NOT NULL
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE noise_by_org AS
        SELECT org_norm, count(*)::INTEGER AS noise_rows FROM hosts
        WHERE is_noise AND org_norm IS NOT NULL GROUP BY org_norm
        """
    )


def build_companies(con):
    """Create table companies: one row per name_norm with identity, footprint, display name, country and noise columns (D8.3 to D8.6)."""
    con.execute(
        f"""
        CREATE OR REPLACE TABLE companies AS
        WITH footprint AS (
            SELECT name_norm,
                count(*) FILTER (WHERE identity_source = 'org')::INTEGER AS org_host_count,
                count(*) FILTER (WHERE identity_source = 'cert_o')::INTEGER AS cert_o_host_count,
                count(*)::INTEGER AS host_count,
                count(DISTINCT host_ip)::INTEGER AS distinct_host_ips,
                count(DISTINCT port)::INTEGER AS distinct_port_count,
                count(DISTINCT country_code)::INTEGER AS country_count
            FROM members GROUP BY name_norm
        ), name_pick AS (  -- D8.4: org text if the company has any org host, else cert O text; most frequent, then not-all-upper, then byte order
            SELECT m.name_norm, m.raw_text, count(*) AS n FROM members m
            JOIN footprint f ON f.name_norm = m.name_norm
            WHERE m.identity_source = CASE WHEN f.org_host_count > 0 THEN 'org' ELSE 'cert_o' END AND m.raw_text IS NOT NULL
            GROUP BY m.name_norm, m.raw_text
        ), display AS (
            SELECT name_norm, raw_text AS company_name FROM (
                SELECT *, row_number() OVER (PARTITION BY name_norm ORDER BY n DESC, (raw_text = upper(raw_text)) ASC, raw_text ASC) AS rk
                FROM name_pick
            ) WHERE rk = 1
        ), country_pick AS (  -- majority host country, ties to the smallest code, nulls ignored
            SELECT name_norm, country_code FROM (
                SELECT name_norm, country_code, row_number() OVER (PARTITION BY name_norm ORDER BY count(*) DESC, country_code ASC) AS rk
                FROM members WHERE country_code IS NOT NULL GROUP BY name_norm, country_code
            ) WHERE rk = 1
        )
        SELECT substr(sha256(f.name_norm), 1, {HASH_LENGTH}) AS company_id,
            d.company_name, f.name_norm,
            CASE WHEN f.org_host_count > 0 THEN 'org' ELSE 'cert_o' END AS identity_source,
            CASE WHEN f.org_host_count > 0 THEN 'high' ELSE 'low' END AS identity_confidence,
            f.org_host_count, f.cert_o_host_count, f.host_count, f.distinct_host_ips, f.distinct_port_count,
            c.country_code, f.country_count,
            coalesce(n.noise_rows, 0)::INTEGER AS noise_host_count,
            coalesce(n.noise_rows, 0)::DOUBLE / (coalesce(n.noise_rows, 0) + f.host_count) AS noise_host_share
        FROM footprint f
        JOIN display d ON d.name_norm = f.name_norm
        LEFT JOIN country_pick c ON c.name_norm = f.name_norm
        LEFT JOIN noise_by_org n ON n.org_norm = f.name_norm
        ORDER BY company_id
        """
    )


def check_consistency(con):
    """Exit with a readable message when hosts or companies break a reconciliation rule; runs before any write."""
    total = con.execute("SELECT count(*) FROM hosts").fetchone()[0]
    rows = dict(con.execute("SELECT identity_source, count(*) FROM hosts GROUP BY 1").fetchall())
    unknown = set(rows) - set(IDENTITY_SOURCES)
    if unknown:
        sys.exit(f"companies stage: inconsistent input, nothing written: unexpected identity_source values: {sorted(map(str, unknown))}")
    has_reason = "infra_reason" in {r[0] for r in con.execute("DESCRIBE hosts").fetchall()}
    reasons = {r for (r,) in con.execute("SELECT DISTINCT infra_reason FROM hosts WHERE is_infrastructure").fetchall()} if has_reason else set()
    if reasons - set(INFRA_REASONS):
        sys.exit(f"companies stage: inconsistent input, nothing written: infra_reason values outside the hosts contract set: {sorted(map(str, reasons - set(INFRA_REASONS)))}")
    n = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    if n > total:
        sys.exit(f"companies stage: inconsistent input, nothing written: companies {n} exceed hosts rows {total}")
    member_rows = rows.get("org", 0) + rows.get("cert_o", 0)
    members = con.execute("SELECT coalesce(sum(host_count), 0) FROM companies").fetchone()[0]
    if members != member_rows:
        sys.exit(f"companies stage: inconsistent input, nothing written: sum(host_count) {members} != member rows {member_rows}")


def write_output(con, output_path):
    """Write table companies to the silver parquet path (zstd, ordered by company_id)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY companies TO '{quote_path(output_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def run_stage(con, hosts_path, output_path):
    """Run read, group and write for one hosts file; return the hosts and companies row counts."""
    build_members(con, hosts_path)
    build_companies(con)
    check_consistency(con)
    write_output(con, output_path)
    hosts_rows = con.execute("SELECT count(*) FROM hosts").fetchone()[0]
    company_rows = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    return {"hosts_rows": hosts_rows, "companies_rows": company_rows}


class Report:
    """Collects report lines, prints them as they are added, and saves them as markdown."""

    def __init__(self):
        """Start with no lines."""
        self.lines = []

    def add(self, text=""):
        """Print one line and keep it for the report file."""
        print(text)
        self.lines.append(text)

    def table(self, header, rows):
        """Add a markdown table with a header row and data rows."""
        self.add("| " + " | ".join(header) + " |")
        self.add("|" + "|".join("---" for _ in header) + "|")
        for row in rows:
            self.add("| " + " | ".join(str(cell) for cell in row) + " |")

    def save(self, path):
        """Write the collected lines to a markdown file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def pct(part, whole):
    """Return part as a percentage string of whole with two decimals, safe for a zero denominator."""
    return f"{100 * part / whole:.2f}%" if whole else "n/a"


def section_headline(con, rep, total):
    """Report section 1: the unresolved share and the shares per identity_source (D8.7 items 1 and 2)."""
    rows = dict(con.execute("SELECT identity_source, count(*) FROM hosts GROUP BY 1").fetchall())
    unknown = set(rows) - set(IDENTITY_SOURCES)
    assert not unknown, f"unexpected identity_source values: {unknown}"
    assert sum(rows.values()) == total, "identity_source row counts do not sum to hosts rows"
    resolved = sum(rows.get(s, 0) for s in MEMBER_SOURCES)
    rep.add(f"## 1. Headline\n\n**{pct(total - resolved, total)} of scanned services cannot be attributed to a customer** "
            f"({total - resolved:,} of {total:,} hosts rows are not org or cert_o: infrastructure_unresolved, noise or null_org).")
    rep.add(f"Resolved (org + cert_o): {resolved:,} of {total:,} = {pct(resolved, total)}. Resolved share range check {RESOLVED_SHARE_RANGE[0]}% to "
            f"{RESOLVED_SHARE_RANGE[1]}%: {'inside' if RESOLVED_SHARE_RANGE[0] <= 100 * resolved / max(total, 1) <= RESOLVED_SHARE_RANGE[1] else 'OUTSIDE'}.")
    rep.add("\n## 2. Rows and distinct host_ip per identity_source\n")
    ranks = " ".join(f"WHEN '{s}' THEN {i}" for i, s in enumerate(D4_PRECEDENCE))
    ip_first = dict(con.execute(
        f"SELECT identity_source, count(*) FROM (SELECT host_ip, "
        f"arg_min(identity_source, CASE identity_source {ranks} END) AS identity_source FROM hosts GROUP BY host_ip) GROUP BY 1"
    ).fetchall())
    ip_raw = dict(con.execute("SELECT identity_source, count(DISTINCT host_ip) FROM hosts GROUP BY 1").fetchall())
    total_ips = con.execute("SELECT count(DISTINCT host_ip) FROM hosts").fetchone()[0]
    assert sum(ip_first.values()) == total_ips, "precedence IP counts do not sum to distinct host_ip"
    multi = con.execute("SELECT count(*) FROM (SELECT host_ip FROM hosts GROUP BY host_ip HAVING count(DISTINCT identity_source) > 1)").fetchone()[0]
    rep.table(("identity_source", "rows", "row share", "distinct IPs (D4 precedence)", "IP share", "distinct IPs (raw)"),
              [(s, f"{rows.get(s, 0):,}", pct(rows.get(s, 0), total), f"{ip_first.get(s, 0):,}", pct(ip_first.get(s, 0), total_ips),
                f"{ip_raw.get(s, 0):,}") for s in IDENTITY_SOURCES])
    rep.add(f"\nRow shares sum to {100 * sum(rows.values()) / max(total, 1):.2f}% (asserted); precedence IP shares sum to {100 * sum(ip_first.values()) / max(total_ips, 1):.2f}% "
            f"(asserted). Distinct host_ip overall: {total_ips:,}. IPs present in more than one identity_source: {multi:,}.")
    return rows


def section_infrastructure(con, rep, total):
    """Report section 3: infra_reason breakdown and infrastructure share (D8.7 item 3)."""
    infra = con.execute("SELECT count(*) FROM hosts WHERE is_infrastructure").fetchone()[0]
    rep.add(f"\n## 3. Infrastructure breakdown\n\nInfrastructure rows: {infra:,} of {total:,} = {pct(infra, total)} of all rows.\n")
    reasons = dict(con.execute("SELECT infra_reason, count(*) FROM hosts WHERE is_infrastructure GROUP BY 1").fetchall())
    extra = set(reasons) - set(INFRA_REASONS)
    assert not extra, f"infra_reason values outside the hosts contract set: {extra}"
    assert sum(reasons.values()) == infra, "infra_reason counts do not sum to infrastructure rows"
    rep.table(("infra_reason", "rows", "share of infrastructure rows"),
              [(r, f"{reasons.get(r, 0):,}", pct(reasons.get(r, 0), infra)) for r in INFRA_REASONS])
    rep.add(f"\nip_pattern rows: {reasons.get('ip_pattern', 0):,} (expected 0). Seven values; set equals the hosts contract set (asserted).")


def section_companies(con, rep, total):
    """Report sections 4 to 6: company totals, host_count distribution and raw spellings (D8.7 items 4, 5, 6)."""
    n = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    assert n <= total, "companies exceed hosts rows"
    rep.add(f"\n## 4. Companies\n\nTotal companies: {n:,} (hosts rows {total:,}; companies <= hosts asserted).\n")
    by_source = con.execute("SELECT identity_source, identity_confidence, count(*) FROM companies GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
    rep.table(("identity_source", "identity_confidence", "companies", "share"), [(s, c, f"{k:,}", pct(k, n)) for s, c, k in by_source])
    both = con.execute("SELECT count(*), coalesce(sum(org_host_count), 0), coalesce(sum(cert_o_host_count), 0) FROM companies "
                       "WHERE org_host_count > 0 AND cert_o_host_count > 0").fetchone()
    rep.add(f"\nCompanies named under both sources (merged): {both[0]:,} ({both[1]:,} org rows + {both[2]:,} cert_o rows).")
    members = con.execute("SELECT coalesce(sum(host_count), 0) FROM companies").fetchone()[0]
    rep.add("\n## 5. Host-count distribution per company\n")
    rows = []
    for label, low, high in BUCKETS:
        cond = f"host_count >= {low}" + (f" AND host_count <= {high}" if high else "")
        k, m = con.execute(f"SELECT count(*), coalesce(sum(host_count), 0) FROM companies WHERE {cond}").fetchone()
        rows.append((label, f"{k:,}", pct(k, n), f"{m:,}", pct(m, members)))
    rep.table(("host_count bucket", "companies", "share of companies", "member rows", "share of member rows"), rows)
    median, p90, p99, biggest = con.execute(
        "SELECT quantile_disc(host_count, 0.5), quantile_disc(host_count, 0.9), quantile_disc(host_count, 0.99), max(host_count) FROM companies").fetchone()
    rep.add(f"\nmedian {median}, p90 {p90}, p99 {p99}, max {biggest} (quantile_disc, so values are actual host counts).")
    raw_org = con.execute("SELECT count(DISTINCT raw_text) FROM members WHERE identity_source = 'org'").fetchone()[0]
    raw_cert = con.execute("SELECT count(DISTINCT raw_text) FROM members WHERE identity_source = 'cert_o'").fetchone()[0]
    rep.add(f"\n## 6. Raw spellings\n\nDistinct raw org strings {raw_org:,} + distinct raw cert O strings {raw_cert:,} = {raw_org + raw_cert:,} "
            f"collapse to {n:,} companies ({raw_org + raw_cert - n:,} merges by normalisation).\n\nCompanies with the most raw spellings (merge review list):\n")
    top = con.execute(
        f"""SELECT c.company_name, count(DISTINCT m.raw_text) AS spellings, c.host_count,
               string_agg(DISTINCT m.raw_text, ' | ' ORDER BY m.raw_text) AS texts
        FROM members m JOIN companies c USING (name_norm) GROUP BY c.company_name, c.host_count, c.name_norm
        ORDER BY spellings DESC, c.name_norm LIMIT {TOP_SPELLINGS}"""
    ).fetchall()
    rep.table(("company_name", "raw spellings", "host_count", "spellings"), [(a, b, c, d[:150]) for a, b, c, d in top])
    return members


def section_top(con, rep):
    """Report section 7: the top companies by host_count (ties by name_norm)."""
    rep.add(f"\n## 7. Top {TOP_COMPANIES} companies by host_count\n")
    rows = con.execute(
        f"SELECT company_name, identity_source, identity_confidence, host_count, distinct_host_ips, distinct_port_count, country_code "
        f"FROM companies ORDER BY host_count DESC, name_norm LIMIT {TOP_COMPANIES}"
    ).fetchall()
    rep.table(("company_name", "source", "confidence", "host_count", "distinct IPs", "distinct ports", "country"), rows)


def section_noise(con, rep):
    """Report section 8: noise rows attributed to companies and noise-only org names."""
    attributed, with_noise = con.execute("SELECT coalesce(sum(noise_host_count), 0), count(*) FILTER (WHERE noise_host_count > 0) FROM companies").fetchone()
    flagged = con.execute(f"SELECT count(*) FROM companies WHERE noise_host_share >= {NOISE_SHARE_FLAG}").fetchone()[0]
    noise_total = con.execute("SELECT count(*) FROM hosts WHERE is_noise").fetchone()[0]
    only = con.execute("SELECT count(*), coalesce(sum(noise_rows), 0) FROM noise_by_org WHERE org_norm NOT IN (SELECT name_norm FROM companies)").fetchone()
    rep.add(f"\n## 8. Noise\n\nNoise rows in hosts: {noise_total:,}. Attributed to a company through org_norm: {attributed:,} rows over {with_noise:,} companies; "
            f"{flagged:,} companies have noise_host_share >= {NOISE_SHARE_FLAG}.")
    rep.add(f"org_norm values with noise rows but no company: {only[0]:,} names, {only[1]:,} rows (includes infrastructure names; noise on infrastructure never creates a company).\n")
    rows = con.execute(
        "SELECT company_name, host_count, noise_host_count, round(noise_host_share, 3) FROM companies WHERE noise_host_count > 0 "
        "ORDER BY noise_host_share DESC, name_norm LIMIT 10").fetchall()
    rep.table(("company_name", "host_count", "noise_host_count", "noise_host_share"), rows)


def section_reconciliation(con, rep, total, rows, members):
    """Report section 9: hosts rows to companies, every difference explained; assert the arithmetic."""
    n = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    member_rows = rows.get("org", 0) + rows.get("cert_o", 0)
    never = rows.get("infrastructure_unresolved", 0) + rows.get("noise", 0) + rows.get("null_org", 0)
    assert never + member_rows == total, "hosts rows != never-create rows + member rows"
    assert members == member_rows, f"sum(host_count) {members} != member rows {member_rows}"
    rep.add(f"\n## 9. Row-count reconciliation hosts to companies\n\n{total:,} hosts rows = {rows.get('infrastructure_unresolved', 0):,} infrastructure_unresolved + "
            f"{rows.get('noise', 0):,} noise + {rows.get('null_org', 0):,} null_org ({never:,} rows that never create a company) + {member_rows:,} member rows "
            f"({rows.get('org', 0):,} org + {rows.get('cert_o', 0):,} cert_o).")
    rep.add(f"The {member_rows:,} member rows group into {n:,} companies; {member_rows - n:,} rows are absorbed into an existing company by exact name_norm. "
            f"sum(host_count) = {members:,} equals member rows (asserted). Nothing else differs: companies {n:,} <= hosts {total:,}.")


def section_sample_and_nulls(con, rep, output_path):
    """Report section 10: null rates of every column and 5 random company rows."""
    spec = importlib.util.spec_from_file_location("stage_report", REPORT_SCRIPT)
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    out = Path(output_path).as_posix()
    total = report.count_rows(con, out)
    rep.add(f"\n## 10. Output file\n\nPath: {out}; rows: {total:,}. Previous layer (hosts rows): {con.execute('SELECT count(*) FROM hosts').fetchone()[0]:,}.\n\nNull rates:\n")
    rep.table(("column", "null rate"), [(c, f"{p}%") for c, p in report.null_rates(con, out, KEY_COLUMNS, total)])
    rep.add("\n5 random company rows:\n")
    cur = con.execute(f"SELECT * FROM read_parquet('{quote_path(out)}') USING SAMPLE reservoir(5 ROWS) REPEATABLE (7)")
    names = [d[0] for d in cur.description]
    for i, row in enumerate(cur.fetchall(), 1):
        rep.add(f"- [{i}] " + ", ".join(f"{k}={str(v)[:40]}" for k, v in zip(names, row)))


def print_report(con, output_path, report_path):
    """Print and save the D8.7 stage report; assertions fail the run when the arithmetic breaks."""
    rep = Report()
    total = con.execute("SELECT count(*) FROM hosts").fetchone()[0]
    rep.add(f"# Companies stage report ({datetime.date.today().isoformat()})\n\nInput hosts rows: {total:,}. Output: {Path(output_path).as_posix()}.\n")
    rows = section_headline(con, rep, total)
    section_infrastructure(con, rep, total)
    members = section_companies(con, rep, total)
    section_top(con, rep)
    section_noise(con, rep)
    section_reconciliation(con, rep, total, rows, members)
    section_sample_and_nulls(con, rep, output_path)
    rep.save(report_path)
    print(f"\nreport saved to {Path(report_path).as_posix()}")


def main(argv=None):
    """Run the stage on the sample hosts file (default) or the full-run hosts file (--full)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="read the full-run hosts file (not for dev)")
    parser.add_argument("--input", help="override the input hosts parquet path")
    parser.add_argument("--output", help="override the output companies parquet path")
    parser.add_argument("--report", help="report markdown path (default: outputs/dq for the default output, else next to --output)")
    args = parser.parse_args(argv)
    guard = load_guard()
    guard.use_utf8_output()
    hosts_path = args.input or (FULL_HOSTS_PATH if args.full else HOSTS_PATH)
    output_path = args.output or (FULL_OUTPUT_PATH if args.full else OUTPUT_PATH)
    report_name = f"companies_stage_{'full_' if args.full else ''}{datetime.date.today().isoformat()}.md"
    default_output = FULL_OUTPUT_PATH if args.full else OUTPUT_PATH
    report_path = guard.choose_report_path(output_path, default_output, args.report, REPORT_DIR / report_name, "companies")
    guard.check_output_path(output_path)
    guard.check_output_path(report_path)
    con = duckdb.connect()
    run_stage(con, hosts_path, output_path)
    print_report(con, output_path, report_path)


if __name__ == "__main__":
    sys.exit(main())
