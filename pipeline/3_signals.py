"""Stage 3: join companies to a per-company host aggregate, write data/gold/signals.parquet (D9.4, D9.5) and the stage report."""
import argparse
import datetime
import importlib.util
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
HOSTS_PATH = ROOT / "data" / "silver" / "hosts.parquet"  # dev input (stage 1 output)
COMPANIES_PATH = ROOT / "data" / "silver" / "companies.parquet"  # dev input (stage 2 output), the spine
OUTPUT_PATH = ROOT / "data" / "gold" / "signals.parquet"
FULL_HOSTS_PATH = ROOT / "data" / "silver" / "hosts_full.parquet"
FULL_COMPANIES_PATH = ROOT / "data" / "silver" / "companies_full.parquet"
FULL_OUTPUT_PATH = ROOT / "data" / "gold" / "signals_full.parquet"
REPORT_DIR = ROOT / "outputs" / "dq"
REPORT_SCRIPT = ROOT / ".claude" / "skills" / "pipeline-stage-build" / "scripts" / "stage_report.py"
STATS_SCRIPT = ROOT / ".claude" / "skills" / "signal-engineering" / "scripts" / "signal_stats.py"

MEMBER_SOURCES = ("org", "cert_o")  # D9.4: only these identity_source values are company members
CDN_TAG = "cdn"  # D6.4 / D9.4: a cert_o host with this tag is not counted for host-borne signals
EOL_TAGS = ("eol-product", "eol-os")
SENSITIVE_TAGS = ("database", "ics", "medical", "iot")  # `ics` has 0 member rows on the sample
LEGACY_TLS_VERSIONS = ("SSLv2", "SSLv3", "TLSv1", "TLSv1.1")  # offered only when there is no leading '-'
RISKY_PORTS = (22, 3389, 445, 3306, 6379, 27017, 9200, 5900, 23, 2375)  # section 3.2; tcp only
SSH_PORT = 22
CERT_SOON_DAYS = 30
CVSS_HIGH = 7.0  # exposed_and_outdated and max_cvss_band 2
CVSS_CRITICAL = 9.0  # max_cvss_band 3
FOOTPRINT_CAP = 50
FOOTPRINT_EDGES = (1, 5, 20)  # distinct_host_ips: 1 -> band 0; 2-5 -> 1; 6-20 -> 2; above 20 -> 3
TERRITORY_COUNTRIES = ("US",)  # PROVISIONAL PLACEHOLDER (D9.4 column 14): the owner supplies the real territory list; not a business decision
# D9.5: DuckDB (RE2) patterns applied to name_norm, copied character for character from the decision record.
OPERATOR_T1_REGEX = (r"(^| )(internet|telekom|communications|hosting|hosted|servers?|broadband|cable|mobile|idc|infrastructure|research"
                     r"|telecom[a-z0-9]*|comunica[a-z0-9]*|network[a-z0-9]*)( |$)|data center|fixed network|(cloud|hosting)( |$)")
OPERATOR_T2_REGEX = (r"(^| )(cloud[a-z0-9]*|host[a-z0-9]*|datacent[a-z0-9]*|rechenzentrum|fiber|fibre|isp|colo|vps|dedicated)( |$)"
                     r"|[a-z0-9]+(telecom|host|hosting|net|servers?)( |$)")
TOP_URGENCY = 15
SPARSE_SHARE = 1.0  # percent: coverage below this is flagged
DENSE_SHARE = 50.0  # percent: coverage above this is flagged

CARRIED_COLUMNS = (
    ("company_id", "VARCHAR"), ("company_name", "VARCHAR"), ("name_norm", "VARCHAR"), ("identity_source", "VARCHAR"),
    ("identity_confidence", "VARCHAR"), ("host_count", "INTEGER"), ("distinct_host_ips", "INTEGER"), ("country_code", "VARCHAR"),
    ("noise_host_count", "INTEGER"), ("noise_host_share", "DOUBLE"),
)
SIGNAL_COLUMNS = (
    ("counted_host_count", "INTEGER"), ("host_signals_blind", "BOOLEAN"), ("is_singleton", "BOOLEAN"), ("in_territory", "BOOLEAN"),
    ("named_registrant", "BOOLEAN"), ("footprint_size", "INTEGER"), ("footprint_band", "SMALLINT"), ("sensitive_stack", "BOOLEAN"),
    ("operator_shape_t1", "BOOLEAN"), ("operator_shape_t2", "BOOLEAN"), ("operator_name_shape", "BOOLEAN"),
    ("kev_exposed", "BOOLEAN"), ("kev_host_count", "INTEGER"), ("max_cvss", "DOUBLE"), ("max_cvss_band", "SMALLINT"),
    ("cert_expired_or_soon", "BOOLEAN"), ("cert_issue_host_count", "INTEGER"), ("eol_stack", "BOOLEAN"), ("eol_host_count", "INTEGER"),
    ("legacy_tls", "BOOLEAN"), ("legacy_tls_host_count", "INTEGER"), ("risky_service_exposed", "BOOLEAN"), ("risky_non_ssh_exposed", "BOOLEAN"),
    ("risky_service_host_count", "INTEGER"), ("risky_ports", "INTEGER[]"), ("exposed_and_outdated", "BOOLEAN"),
)
OUTPUT_COLUMNS = CARRIED_COLUMNS + SIGNAL_COLUMNS
KEY_COLUMNS = tuple(name for name, _ in OUTPUT_COLUMNS)
BOOLEAN_SIGNALS = tuple(name for name, typ in OUTPUT_COLUMNS if typ == "BOOLEAN")
URGENCY_SIGNALS = ("kev_exposed", "cert_expired_or_soon", "eol_stack", "legacy_tls", "risky_service_exposed", "exposed_and_outdated")
# D9.4 coverage table (ad hoc queries by the senior engineer): label -> (companies, share percent). Compared with measured values in the report.
D9_COVERAGE = {
    "in_territory": 1346, "named_registrant": 5387, "sensitive_stack": 55, "operator_shape_t1": 1046, "operator_name_shape": 1438,
    "is_singleton": 4169, "host_signals_blind": 180, "kev_exposed": 462, "cert_expired_or_soon": 373, "eol_stack": 352, "legacy_tls": 209,
    "risky_service_exposed": 226, "risky_non_ssh_exposed": 68, "exposed_and_outdated": 48,
}
D9_SPECIAL = {"max_cvss_band = 3": 460, "max_cvss_band = 2": 209, "max_cvss_band = 1": 70, "footprint_band = 1": 1215, "footprint_band = 2": 318,
              "footprint_band = 3": 27, "T2 only (T2 and not T1)": 392, "risky_service_exposed SSH only": 158,
              "any urgency signal": 1294, "strong urgency": 662}


def quote_path(path):
    """Return a path as a forward-slash string with single quotes escaped, for SQL literals."""
    return Path(path).as_posix().replace("'", "''")


def sql_list(values):
    """Render a Python tuple of strings or numbers as a SQL list literal."""
    return "[" + ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in values) + "]"


def build_host_flags(con, hosts_path):
    """Create table host_flags: one row per member host row with counted, eol, sensitive, legacy, risky and cert flags (D9.4)."""
    con.execute(f"CREATE OR REPLACE TABLE hosts AS SELECT * FROM read_parquet('{quote_path(hosts_path)}')")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE host_flags AS
        SELECT name_norm, port,
            (identity_source = 'org' OR NOT list_contains(coalesce(tags, []::VARCHAR[]), '{CDN_TAG}')) AS counted,
            list_has_any(coalesce(tags, []::VARCHAR[]), {sql_list(EOL_TAGS)}) AS eol,
            list_has_any(coalesce(tags, []::VARCHAR[]), {sql_list(SENSITIVE_TAGS)}) AS sensitive,
            list_has_any(coalesce(ssl_versions, []::VARCHAR[]), {sql_list(LEGACY_TLS_VERSIONS)}) AS legacy,
            (transport = 'tcp' AND port IN {tuple(RISKY_PORTS)}) AS risky,
            (transport = 'tcp' AND port IN {tuple(p for p in RISKY_PORTS if p != SSH_PORT)}) AS risky_non_ssh,
            coalesce(has_kev, false) AS has_kev,
            max_cvss,
            (coalesce(cert_expired, false)
                OR (cert_expires IS NOT NULL AND cert_expires > timestamp AND cert_expires <= timestamp + INTERVAL {CERT_SOON_DAYS} DAY)) AS cert_issue
        FROM hosts
        WHERE identity_source IN {tuple(MEMBER_SOURCES)} AND name_norm IS NOT NULL
        """
    )


def build_signals(con, companies_path):
    """Create table signals: companies joined to the per-company aggregate of host_flags, one row per company_id (D9.4)."""
    con.execute(f"CREATE OR REPLACE TABLE companies AS SELECT * FROM read_parquet('{quote_path(companies_path)}')")
    e1, e2, e3 = FOOTPRINT_EDGES
    con.execute(
        f"""
        CREATE OR REPLACE TABLE host_agg AS
        SELECT name_norm,
            count(*) FILTER (WHERE counted)::INTEGER AS counted_host_count,
            count(*) FILTER (WHERE counted AND sensitive)::INTEGER AS sensitive_host_count,
            count(*) FILTER (WHERE counted AND has_kev)::INTEGER AS kev_host_count,
            max(max_cvss) FILTER (WHERE counted) AS max_cvss,
            count(*) FILTER (WHERE cert_issue)::INTEGER AS cert_issue_host_count,
            count(*) FILTER (WHERE counted AND eol)::INTEGER AS eol_host_count,
            count(*) FILTER (WHERE counted AND legacy)::INTEGER AS legacy_tls_host_count,
            count(*) FILTER (WHERE counted AND risky)::INTEGER AS risky_service_host_count,
            count(*) FILTER (WHERE counted AND risky_non_ssh)::INTEGER AS risky_non_ssh_host_count,
            coalesce(list_sort(list_distinct(list(port) FILTER (WHERE counted AND risky)))::INTEGER[], []::INTEGER[]) AS risky_ports,
            count(*) FILTER (WHERE counted AND risky AND (eol OR coalesce(max_cvss, 0) >= {CVSS_HIGH}))::INTEGER AS exposed_and_outdated_host_count
        FROM host_flags GROUP BY name_norm
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE signals AS
        SELECT c.company_id, c.company_name, c.name_norm, c.identity_source, c.identity_confidence, c.host_count, c.distinct_host_ips,
            c.country_code, c.noise_host_count, c.noise_host_share,
            coalesce(a.counted_host_count, 0)::INTEGER AS counted_host_count,
            (coalesce(a.counted_host_count, 0) = 0) AS host_signals_blind,
            (c.host_count = 1) AS is_singleton,
            CASE WHEN c.country_code IS NULL THEN NULL ELSE list_contains({sql_list(TERRITORY_COUNTRIES)}, c.country_code) END AS in_territory,
            (c.identity_confidence = 'high') AS named_registrant,
            least(c.distinct_host_ips, {FOOTPRINT_CAP})::INTEGER AS footprint_size,
            (CASE WHEN c.distinct_host_ips <= {e1} THEN 0 WHEN c.distinct_host_ips <= {e2} THEN 1 WHEN c.distinct_host_ips <= {e3} THEN 2 ELSE 3 END)::SMALLINT AS footprint_band,
            (coalesce(a.sensitive_host_count, 0) > 0) AS sensitive_stack,
            regexp_matches(c.name_norm, '{OPERATOR_T1_REGEX}') AS operator_shape_t1,
            regexp_matches(c.name_norm, '{OPERATOR_T2_REGEX}') AS operator_shape_t2,
            (regexp_matches(c.name_norm, '{OPERATOR_T1_REGEX}') OR regexp_matches(c.name_norm, '{OPERATOR_T2_REGEX}')) AS operator_name_shape,
            (coalesce(a.kev_host_count, 0) > 0) AS kev_exposed,
            coalesce(a.kev_host_count, 0)::INTEGER AS kev_host_count,
            a.max_cvss,
            (CASE WHEN a.max_cvss IS NULL THEN 0 WHEN a.max_cvss >= {CVSS_CRITICAL} THEN 3 WHEN a.max_cvss >= {CVSS_HIGH} THEN 2 ELSE 1 END)::SMALLINT AS max_cvss_band,
            (coalesce(a.cert_issue_host_count, 0) > 0) AS cert_expired_or_soon,
            coalesce(a.cert_issue_host_count, 0)::INTEGER AS cert_issue_host_count,
            (coalesce(a.eol_host_count, 0) > 0) AS eol_stack,
            coalesce(a.eol_host_count, 0)::INTEGER AS eol_host_count,
            (coalesce(a.legacy_tls_host_count, 0) > 0) AS legacy_tls,
            coalesce(a.legacy_tls_host_count, 0)::INTEGER AS legacy_tls_host_count,
            (coalesce(a.risky_service_host_count, 0) > 0) AS risky_service_exposed,
            (coalesce(a.risky_non_ssh_host_count, 0) > 0) AS risky_non_ssh_exposed,
            coalesce(a.risky_service_host_count, 0)::INTEGER AS risky_service_host_count,
            coalesce(a.risky_ports, []::INTEGER[]) AS risky_ports,
            (coalesce(a.exposed_and_outdated_host_count, 0) > 0) AS exposed_and_outdated
        FROM companies c LEFT JOIN host_agg a ON a.name_norm = c.name_norm
        ORDER BY c.company_id
        """
    )
    n_comp = con.execute("SELECT count(*) FROM companies").fetchone()[0]
    n_sig = con.execute("SELECT count(*) FROM signals").fetchone()[0]
    uniq = con.execute("SELECT count(DISTINCT company_id) FROM signals").fetchone()[0]
    assert n_sig == n_comp == uniq, f"fan-out or drop: companies {n_comp}, signals {n_sig}, distinct company_id {uniq}"


def write_output(con, output_path):
    """Write table signals to the gold parquet path (zstd, ordered by company_id)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY signals TO '{quote_path(output_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def run_stage(con, hosts_path, companies_path, output_path):
    """Run flags, aggregate, join and write for one hosts and companies pair; return the row counts."""
    build_host_flags(con, hosts_path)
    build_signals(con, companies_path)
    write_output(con, output_path)
    return {"companies_rows": con.execute("SELECT count(*) FROM companies").fetchone()[0],
            "signals_rows": con.execute("SELECT count(*) FROM signals").fetchone()[0],
            "member_rows": con.execute("SELECT count(*) FROM host_flags").fetchone()[0]}


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


def coverage_flag(count, total):
    """Return a flag text when a signal fires on under SPARSE_SHARE or over DENSE_SHARE percent of companies."""
    share = 100 * count / total if total else 0
    if share < SPARSE_SHARE:
        return "below 1%"
    return "above 50%" if share > DENSE_SHARE else ""


def coverage_rows(con):
    """Return (label, measured count, D9 count or None) for every signal, plus derived rows, from table signals."""
    rows = [(name, con.execute(f"SELECT count(*) FROM signals WHERE {name}").fetchone()[0], D9_COVERAGE.get(name)) for name in BOOLEAN_SIGNALS]
    derived = {
        "max_cvss_band = 3": "max_cvss_band = 3", "max_cvss_band = 2": "max_cvss_band = 2", "max_cvss_band = 1": "max_cvss_band = 1",
        "footprint_band = 1": "footprint_band = 1", "footprint_band = 2": "footprint_band = 2", "footprint_band = 3": "footprint_band = 3",
        "T2 only (T2 and not T1)": "operator_shape_t2 AND NOT operator_shape_t1",
        "risky_service_exposed SSH only": "risky_service_exposed AND NOT risky_non_ssh_exposed",
        "any urgency signal": "(" + " OR ".join(URGENCY_SIGNALS[:5]) + " OR max_cvss_band >= 2)",
        "strong urgency": "(kev_exposed OR max_cvss_band = 3 OR exposed_and_outdated)",
    }
    for label, cond in derived.items():
        rows.append((label, con.execute(f"SELECT count(*) FROM signals WHERE {cond}").fetchone()[0], D9_SPECIAL.get(label)))
    return rows


def section_coverage(con, rep, total):
    """Report section 2: company-level coverage of every signal and the comparison with the D9.4 table."""
    rep.add("\n## 2. Company-level coverage (share of all companies) and comparison with the D9.4 table\n")
    rows = []
    for label, count, d9 in coverage_rows(con):
        diff = "" if d9 is None else f"{count - d9:+d}"
        rows.append((label, f"{count:,}", pct(count, total), "" if d9 is None else f"{d9:,}", diff, coverage_flag(count, total)))
    rep.table(("signal", "companies firing", "share", "D9.4 count", "difference", "flag"), rows)
    any_cvss = con.execute("SELECT count(*) FROM signals WHERE max_cvss_band >= 1").fetchone()[0]
    rep.add(f"\nCompanies with any CVSS value: {any_cvss:,} (D9.4: 739). footprint_band 0 (one IP): "
            f"{con.execute('SELECT count(*) FROM signals WHERE footprint_band = 0').fetchone()[0]:,} (D9.4: 4,230). "
            f"in_territory is a PLACEHOLDER ({', '.join(TERRITORY_COUNTRIES)} only) until the owner supplies the territory list; T2 is computed, not yet part of any penalty.")
    nulls = con.execute("SELECT count(*) FROM signals WHERE in_territory IS NULL").fetchone()[0]
    rep.add(f"in_territory null (country_code null): {nulls:,}.")
    rep.add("\n## 3. Counted-host reconciliation (D6.4)\n")
    members, counted, blind, with_non = con.execute(
        "SELECT (SELECT count(*) FROM host_flags), (SELECT count(*) FROM host_flags WHERE counted), "
        "(SELECT count(*) FROM signals WHERE host_signals_blind), (SELECT count(*) FROM signals WHERE counted_host_count < host_count)").fetchone()
    assert con.execute("SELECT sum(counted_host_count) FROM signals").fetchone()[0] == counted, "sum(counted_host_count) != counted member host rows"
    sum_host = con.execute("SELECT sum(host_count) FROM signals").fetchone()[0]
    assert sum_host == members, f"sum(host_count) {sum_host} != member host rows {members}"
    rep.add(f"Member host rows {members:,} = counted {counted:,} + non-counted (CDN-tagged cert_o) {members - counted:,}; sum(host_count) = {sum_host:,} "
            f"equals member host rows (asserted); sum(counted_host_count) equals counted (asserted). Companies with at least one non-counted host: "
            f"{with_non:,} (D9.4: 192); host-blind companies: {blind:,} (D9.4: 180).")
    cert_expired, cert_soon = con.execute(
        f"SELECT count(*) FILTER (WHERE coalesce(cert_expired, false)), "
        f"count(*) FILTER (WHERE NOT coalesce(cert_expired, false) AND cert_expires > timestamp AND cert_expires <= timestamp + INTERVAL {CERT_SOON_DAYS} DAY) "
        f"FROM hosts WHERE identity_source IN {tuple(MEMBER_SOURCES)} AND name_norm IS NOT NULL").fetchone()
    rep.add(f"Member host rows with the certificate condition by branch: expired boolean {cert_expired:,}, expiring within {CERT_SOON_DAYS} days (boolean false) {cert_soon:,} "
            f"(D9.4 text: 286 expired and 150 expiring; it did not say whether the 150 are exclusive of the 286).")


def section_top_urgency(con, rep):
    """Report section 4: the top companies by the number of firing urgency signals."""
    cond = " + ".join(f"{s}::INTEGER" for s in URGENCY_SIGNALS)
    rep.add(f"\n## 4. Top {TOP_URGENCY} companies by number of firing urgency signals ({', '.join(URGENCY_SIGNALS)}; ties by host_count then company_id)\n")
    rows = con.execute(
        f"SELECT company_name, ({cond}) AS firing, host_count, counted_host_count, kev_host_count, max_cvss, risky_ports::VARCHAR, operator_name_shape "
        f"FROM signals ORDER BY firing DESC, host_count DESC, company_id LIMIT {TOP_URGENCY}").fetchall()
    rep.table(("company_name", "urgency signals firing", "host_count", "counted", "kev hosts", "max_cvss", "risky_ports", "operator shape"), rows)


def section_output(con, rep, output_path, companies_rows):
    """Report section 5: output file, row equality, null rates and 5 random rows."""
    spec = importlib.util.spec_from_file_location("stage_report", REPORT_SCRIPT)
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    out = Path(output_path).as_posix()
    total = report.count_rows(con, out)
    assert total == companies_rows, "signals rows != companies rows"
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{quote_path(out)}')").fetchall()]
    assert tuple(cols) == KEY_COLUMNS and len(cols) == 36, "output columns differ from D9.4"
    rep.add(f"\n## 5. Output file\n\nPath: {out}; rows: {total:,}; columns: {len(cols)}. Previous layer (companies rows): {companies_rows:,}; difference 0 (asserted: "
            f"one row per company, company_id unique, no fan-out).\n\nNull rates (all columns, worst first):\n")
    rep.table(("column", "null rate"), [(c, f"{p}%") for c, p in report.null_rates(con, out, KEY_COLUMNS, total)])
    rep.add("\n5 random rows:\n")
    cur = con.execute(f"SELECT * FROM read_parquet('{quote_path(out)}') USING SAMPLE reservoir(5 ROWS) REPEATABLE (7)")
    names = [d[0] for d in cur.description]
    for i, row in enumerate(cur.fetchall(), 1):
        rep.add(f"- [{i}] " + ", ".join(f"{k}={str(v)[:40]}" for k, v in zip(names, row)))


def print_report(con, run, output_path, report_path):
    """Print and save the stage report; assertions fail the run when the arithmetic breaks."""
    rep = Report()
    total = run["signals_rows"]
    rep.add(f"# Signals stage report ({datetime.date.today().isoformat()})\n\nInput companies rows: {run['companies_rows']:,}; member host rows aggregated: "
            f"{run['member_rows']:,}. Output: {Path(output_path).as_posix()}. Signal list per D9.4 (PROVISIONAL until the owner approves).\n")
    rep.add("## 1. Row counts\n")
    rep.add(f"companies {run['companies_rows']:,} = signals {total:,} (asserted; company_id unique).")
    section_coverage(con, rep, total)
    section_top_urgency(con, rep)
    section_output(con, rep, output_path, run["companies_rows"])
    rep.save(report_path)
    print(f"\nreport saved to {Path(report_path).as_posix()}")
    print(f"redundancy and coverage diagnostics: python {STATS_SCRIPT.relative_to(ROOT).as_posix()} {Path(output_path).relative_to(ROOT).as_posix() if Path(output_path).is_relative_to(ROOT) else output_path}")


def main():
    """Run the stage on the sample files (default) or the full-run files (--full)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="read hosts_full and companies_full, write signals_full (not for dev)")
    parser.add_argument("--hosts", help="override the hosts parquet path")
    parser.add_argument("--companies", help="override the companies parquet path")
    parser.add_argument("--output", help="override the output parquet path")
    args = parser.parse_args()
    hosts_path = args.hosts or (FULL_HOSTS_PATH if args.full else HOSTS_PATH)
    companies_path = args.companies or (FULL_COMPANIES_PATH if args.full else COMPANIES_PATH)
    output_path = args.output or (FULL_OUTPUT_PATH if args.full else OUTPUT_PATH)
    report_name = f"signals_stage_{'full_' if args.full else ''}{datetime.date.today().isoformat()}.md"
    con = duckdb.connect()
    run = run_stage(con, hosts_path, companies_path, output_path)
    print_report(con, run, output_path, REPORT_DIR / report_name)


if __name__ == "__main__":
    sys.exit(main())
