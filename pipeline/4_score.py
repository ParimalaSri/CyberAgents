"""Stage 4: score signals into fit, urgency and contact scores, bands, caps and a rule-based why; write data/gold/accounts.parquet (D9.6 to D9.8)."""
import argparse
import contextlib
import datetime
import importlib.util
import io
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "data" / "gold" / "signals.parquet"
OUTPUT_PATH = ROOT / "data" / "gold" / "accounts.parquet"
FULL_INPUT_PATH = ROOT / "data" / "gold" / "signals_full.parquet"
FULL_OUTPUT_PATH = ROOT / "data" / "gold" / "accounts_full.parquet"
REPORT_DIR = ROOT / "outputs" / "dq"
REPORT_SCRIPT = ROOT / ".claude" / "skills" / "pipeline-stage-build" / "scripts" / "stage_report.py"
DISTRIBUTION_SCRIPT = ROOT / ".claude" / "skills" / "scoring-calibration" / "scripts" / "score_distribution.py"

# ======================================================================================================================
# PROVISIONAL CONSTANTS: not calibrated, not owner-approved (D9.7, ARCHITECTURE.md section 15). They exist only so that
# this stage can be built and exercised. The owner approves or amends them at calibration, and the approved values are then
# recorded in ARCHITECTURE.md section 3.4. Nobody should read the bands they produce as decisions.
# ======================================================================================================================
PTS_KEV = 50  # urgency, vulnerability: kev_exposed
PTS_CVSS = {0: 0, 1: 10, 2: 25, 3: 40}  # urgency, vulnerability: by max_cvss_band; the vulnerability component is the LARGER of KEV and CVSS, never the sum
PTS_EXPOSED_OUTDATED = 30  # urgency, exposure: highest applicable of the next three
PTS_RISKY_NON_SSH = 15
PTS_RISKY_SSH_ONLY = 5  # risky_service_exposed without risky_non_ssh_exposed
PTS_EOL = 10  # urgency, hygiene: the three are summed
PTS_CERT = 5
PTS_LEGACY_TLS = 5
IN_TERRITORY_POINTS = 0  # fit: in_territory; D11.5 sets 0 (neutral) until the owner supplies the territory list, then 35 (D9.7); the stage 3 column stays a US-only placeholder and is not scored
PTS_FOOTPRINT_PER_BAND = 15  # fit: footprint_band x 15
PTS_SENSITIVE = 20  # fit: sensitive_stack
PENALTY_OPERATOR = 30  # fit: subtracted when operator_name_shape (the T1-or-T2 union) is true; D10, provisional until the data-analyst T2 gate (D9.5)
FLOOR_PCT = 50  # contact form (b): FLOOR = 0.50, kept as a whole percent so the arithmetic is exact in integers
CONTACT_FORM = "b"  # "b" urgency gated by fit (recommended in D9.6 item 4); "a" weighted sum, kept only for the calibration comparison
W_F_PCT = 30  # form (a) only: weight of fit in percent; D9 gives no value, so this is a placeholder invented only to exercise form (a)
THRESHOLD_CONTACT = 40  # X
THRESHOLD_REVIEW = 20  # Y; since D11.2 it is the FLOOR of the top-N review band (REVIEW_FLOOR) and the band_uncapped review edge
REVIEW_N = 200  # D11.2: total accounts in review (every would-be contact plus the best remaining by the stage sort); placeholder N = ceil(C / r), C = 50 per week, r = 0.25, owner supplies C
# ======================================================================================================================
# End of PROVISIONAL block. The constants below are decided (D9.3, D9.6) or are display tables, not weights.
# ======================================================================================================================
NOISE_MIN_HOSTS = 2  # D9.3 (decided): exclude needs at least this many noise hosts ...
NOISE_MIN_SHARE = 0.5  # ... and at least this noise share
CAP_SINGLETON = "singleton"
CAP_LOW_CONFIDENCE = "low_confidence"
CAP_OPERATOR = "operator_name_shape"
CAP_UNVERIFIED = "operator_unverified"  # D10: every would-be contact is held in review until an adjudicator or ASN reference checks it
UNVERIFIED_CLAUSE = "Not yet checked that this is an end-user organisation, not a network operator."  # D10 text, appended last for every would-be contact
OPERATOR_CLAUSE = "Name looks like a network operator."  # D10 cap clause; D11.3 also puts it on any other review row with operator_name_shape
SKIP_CLAUSE = "Below the review cut-off."  # D11.3: replaces "Exposure is limited."; a statement about the score and the cut, not a risk judgement
SKIP_CLAUSE_SIGNAL = "Ranked below this run's review list; a rank, not a judgement of risk."  # D12.2: skip rows whose kept top signals include kev_exposed or max_cvss_band
SKIP_SIGNAL_NAMES = ("kev_exposed", "max_cvss_band")  # D12.2: the signals whose sentence makes the plain skip clause read as a dismissal
EXPOSED_OUTDATED_TEXT = "on software that is end-of-life or whose version matches a CVSS 7+ vulnerability"  # D12.3: true for both ways the signal fires (EOL tag or version-matched CVSS 7+)
STAGE_ORDER_TEXT = "urgency_score, operator_name_shape (false first), kev_host_count, host_count, account_id"  # D12.1 tie description printed at the cut
KEV_PHRASE = "running software whose version matches the CISA known-exploited list"  # D11.3 (RAW-006): the CVE is inferred from a banner version, never stated as fact
CVSS_PHRASE = "worst version-matched vulnerability scores CVSS"  # D11.3 (RAW-006)
CAP_CLAUSES = (  # priority order for the single cap clause in the why
    (CAP_OPERATOR, OPERATOR_CLAUSE),
    (CAP_SINGLETON, "Only one host seen."),
    (CAP_LOW_CONFIDENCE, "Named only by a TLS certificate."),
)
WHY_MAX_WORDS = 40  # D9.6 item 7
PORT_NAMES = {22: "SSH", 3389: "RDP", 445: "SMB", 3306: "MySQL", 6379: "Redis", 27017: "MongoDB", 9200: "Elasticsearch", 5900: "VNC",
              23: "Telnet", 2375: "Docker"}
PORTS_SHOWN = 2  # at most this many ports are named in a why
SSH_PORT = 22
BANDS = ("contact", "review", "skip", "exclude")
D11_EXPECTED = {"contact": "0", "review": "200 (N), or the would-be contacts if more", "skip": "5,589 (the rest)", "exclude": "1"}  # senior's D11 expectation at N = 200 on the sample
PREVIOUS_RUN = {"contact": 0, "review": 664, "skip": 5125, "exclude": 1}  # the D10 run (threshold-only review at Y = 20, territory 35, T2 with the net branch), 40 / 20
D11_EXPECTED_WOULD_BE = 51  # D11.5: about 51 would-be contacts after territory 0 (ablation); the stage prints the measured count
D11_EXPECTED_TIE = (30, 142)  # D12.1: cut score and tie size measured by the senior on the D11 output (7 kept, 135 to skip)
D12_EXPECTED_KEPT = "Alta Gracia Project Holding, Provider Ktechnology, Brainoza OU, SugarHosts, Seiko Electric, Free Way Tecnologia, Owl Limited (0 flagged, 5 singletons)"  # D12.1 simulation of the 7 kept
D12_EXPECTED_SKIP_SIGNAL = 537  # D12.2: 303 KEV + 234 CVSS skip rows
COMPARE_PAIRS = ((45, 25), (40, 20), (35, 15))
TOP_N = 25
HISTOGRAM_BUCKETS = 10

OUTPUT_COLUMNS = (
    ("account_id", "VARCHAR"), ("company_name", "VARCHAR"), ("country_code", "VARCHAR"), ("host_count", "INTEGER"),
    ("identity_source", "VARCHAR"), ("identity_confidence", "VARCHAR"), ("fit_score", "INTEGER"), ("urgency_score", "INTEGER"),
    ("contact_score", "INTEGER"), ("top_signals", "VARCHAR"), ("band_uncapped", "VARCHAR"), ("cap_reasons", "VARCHAR"), ("band", "VARCHAR"),
    ("why", "VARCHAR"), ("decision", "VARCHAR"), ("prompt_version", "VARCHAR"), ("final_band", "VARCHAR"),
)
KEY_COLUMNS = tuple(name for name, _ in OUTPUT_COLUMNS)
POINT_COLUMNS = ("p_vuln", "p_expo", "p_eol", "p_cert", "p_legacy", "p_footprint", "p_territory", "p_sensitive")


def stage_order_sql(id_col="account_id", score="contact_score", scored="", flags=""):
    """Return the D12.1 total-order ORDER BY list: score DESC, urgency DESC, operator_name_shape ASC, coalesce(kev_host_count, 0) DESC, host_count DESC, id ASC; scored and flags are column prefixes."""
    return (f"{score} DESC, {scored}urgency_score DESC, {flags}operator_name_shape ASC, coalesce({flags}kev_host_count, 0) DESC, "
            f"{scored}host_count DESC, {id_col} ASC")


def quote_path(path):
    """Return a path as a forward-slash string with single quotes escaped, for SQL literals."""
    return Path(path).as_posix().replace("'", "''")


def load_module(name, path):
    """Import a helper script by file path and return the module."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cvss_points_sql():
    """Return a SQL CASE expression turning max_cvss_band into the CVSS points of PTS_CVSS."""
    whens = " ".join(f"WHEN {band} THEN {pts}" for band, pts in PTS_CVSS.items())
    return f"CASE max_cvss_band {whens} ELSE 0 END"


def band_sql(contact, review, review_n):
    """Return a SQL CASE expression for the band: exclude, then every would-be contact held in review (D10), then the top review_n by review_rank with contact_score >= review (D11.2), else skip."""
    exclude = f"(noise_host_count >= {NOISE_MIN_HOSTS} AND noise_host_share >= {NOISE_MIN_SHARE})"
    return (f"CASE WHEN {exclude} THEN 'exclude' WHEN contact_score >= {contact} THEN 'review' "
            f"WHEN review_rank <= {review_n} AND contact_score >= {review} THEN 'review' ELSE 'skip' END")


def contact_expr_sql(fit_col):
    """Return the SQL integer expression of contact_score for the active CONTACT_FORM from urgency_score and the given fit column."""
    if CONTACT_FORM == "b":
        return f"(urgency_score * ({FLOOR_PCT * 100} + {100 - FLOOR_PCT} * {fit_col}) + 5000) // 10000"
    return f"({W_F_PCT} * {fit_col} + {100 - W_F_PCT} * urgency_score + 50) // 100"


def build_scored(con, input_path, contact, review, review_n=REVIEW_N):
    """Create table scored: the signals plus point columns, the three scores, band_uncapped, cap_reasons and band (D9.6 items 2 to 5)."""
    con.execute(f"CREATE OR REPLACE TABLE signals AS SELECT * FROM read_parquet('{quote_path(input_path)}')")
    cvss = cvss_points_sql()
    # D10: the fit penalty and the cap both use operator_name_shape, the union of operator_shape_t1 and operator_shape_t2 (D9.5). The union is
    # provisional: the data-analyst's fresh-sample T2 gate (D9.5) is still pending and may reduce it to T1 or to the clean T2 sub-patterns.
    contact_expr = contact_expr_sql("fit_score")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE pts AS
        SELECT *,
            greatest(CASE WHEN kev_exposed THEN {PTS_KEV} ELSE 0 END, {cvss})::INTEGER AS p_vuln,
            (CASE WHEN kev_exposed AND {PTS_KEV} >= {cvss} THEN 'kev_exposed' WHEN {cvss} > 0 THEN 'max_cvss_band' ELSE NULL END) AS vuln_signal,
            (CASE WHEN exposed_and_outdated THEN {PTS_EXPOSED_OUTDATED} WHEN risky_non_ssh_exposed THEN {PTS_RISKY_NON_SSH}
                  WHEN risky_service_exposed THEN {PTS_RISKY_SSH_ONLY} ELSE 0 END)::INTEGER AS p_expo,
            (CASE WHEN exposed_and_outdated THEN 'exposed_and_outdated' WHEN risky_non_ssh_exposed THEN 'risky_non_ssh_exposed'
                  WHEN risky_service_exposed THEN 'risky_service_exposed' ELSE NULL END) AS expo_signal,
            (CASE WHEN eol_stack THEN {PTS_EOL} ELSE 0 END)::INTEGER AS p_eol,
            (CASE WHEN cert_expired_or_soon THEN {PTS_CERT} ELSE 0 END)::INTEGER AS p_cert,
            (CASE WHEN legacy_tls THEN {PTS_LEGACY_TLS} ELSE 0 END)::INTEGER AS p_legacy,
            (footprint_band * {PTS_FOOTPRINT_PER_BAND})::INTEGER AS p_footprint,
            (CASE WHEN coalesce(in_territory, false) THEN {IN_TERRITORY_POINTS} ELSE 0 END)::INTEGER AS p_territory,
            (CASE WHEN sensitive_stack THEN {PTS_SENSITIVE} ELSE 0 END)::INTEGER AS p_sensitive,
            (CASE WHEN operator_name_shape THEN {PENALTY_OPERATOR} ELSE 0 END)::INTEGER AS p_penalty
        FROM signals
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE scored AS
        SELECT *, ({contact_expr})::INTEGER AS contact_score FROM (
            SELECT *, greatest(0, least(100, p_vuln + p_expo + p_eol + p_cert + p_legacy))::INTEGER AS urgency_score,
                greatest(0, least(100, p_territory + p_footprint + p_sensitive - p_penalty))::INTEGER AS fit_score
            FROM pts)
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE scored AS
        SELECT *,
            (CASE WHEN (noise_host_count >= {NOISE_MIN_HOSTS} AND noise_host_share >= {NOISE_MIN_SHARE}) THEN 'exclude'
                  WHEN contact_score >= {contact} THEN 'contact' WHEN contact_score >= {review} THEN 'review' ELSE 'skip' END) AS band_uncapped,
            (CASE WHEN contact_score >= {contact} AND NOT (noise_host_count >= {NOISE_MIN_HOSTS} AND noise_host_share >= {NOISE_MIN_SHARE})
                  THEN nullif(concat_ws(',', CASE WHEN identity_confidence = 'low' THEN '{CAP_LOW_CONFIDENCE}' END,
                                             CASE WHEN operator_name_shape THEN '{CAP_OPERATOR}' END,
                                             '{CAP_UNVERIFIED}',
                                             CASE WHEN is_singleton THEN '{CAP_SINGLETON}' END), '')
                  ELSE NULL END) AS cap_reasons
        FROM scored
        """
    )
    # D11.2, D12.1: rank over non-excluded accounts in the STAGE_ORDER total order (account_id is unique, so the order is total); excluded accounts get a null rank.
    con.execute(
        f"""
        CREATE OR REPLACE TABLE scored AS
        SELECT s.*, r.review_rank FROM scored s LEFT JOIN (
            SELECT company_id, (row_number() OVER (ORDER BY {stage_order_sql('company_id')}))::INTEGER AS review_rank
            FROM scored WHERE NOT (noise_host_count >= {NOISE_MIN_HOSTS} AND noise_host_share >= {NOISE_MIN_SHARE})) r USING (company_id)
        """
    )
    con.execute(f"CREATE OR REPLACE TABLE scored AS SELECT *, ({band_sql(contact, review, review_n)}) AS band FROM scored")


def plural_hosts(count):
    """Return '1 host' or 'N hosts'."""
    return f"{count} host" if count == 1 else f"{count} hosts"


def port_text(ports, skip_ssh=False):
    """Return up to PORTS_SHOWN named ports such as 'RDP 3389, MySQL 3306' from a sorted port list."""
    shown = [p for p in ports if not (skip_ssh and p == SSH_PORT)][:PORTS_SHOWN]
    return ", ".join(f"{PORT_NAMES.get(p, 'port')} {p}" for p in shown)


def signal_candidates(row):
    """Return the scored signals of one account as (points, group rank, order, signal name, phrase) tuples; zero-point signals are left out."""
    ports = list(row["risky_ports"] or [])
    out = []
    if row["p_vuln"] > 0:
        if row["vuln_signal"] == "kev_exposed":
            phrase = f"{plural_hosts(row['kev_host_count'])} {KEV_PHRASE}"
        else:
            phrase = f"{CVSS_PHRASE} {row['max_cvss']:.1f}"
        out.append((row["p_vuln"], 0, 0, row["vuln_signal"], phrase))
    if row["p_expo"] > 0:
        sig = row["expo_signal"]
        if sig == "exposed_and_outdated":
            phrase = f"an exposed admin or database service ({port_text(ports)}) {EXPOSED_OUTDATED_TEXT}"
        elif sig == "risky_non_ssh_exposed":
            phrase = f"remote-admin or database services exposed ({port_text(ports, skip_ssh=True)})"
        else:
            phrase = "SSH (port 22) open to the internet"
        out.append((row["p_expo"], 1, 0, sig, phrase))
    out.append((row["p_eol"], 2, 0, "eol_stack", f"{plural_hosts(row['eol_host_count'])} on end-of-life software"))
    out.append((row["p_cert"], 2, 1, "cert_expired_or_soon", f"{plural_hosts(row['cert_issue_host_count'])} with expired or soon-expiring certificates"))
    out.append((row["p_legacy"], 2, 2, "legacy_tls", f"{plural_hosts(row['legacy_tls_host_count'])} still offering old TLS versions"))
    out.append((row["p_footprint"], 3, 0, "footprint_band", f"{row['distinct_host_ips']} IPs in the footprint"))
    out.append((row["p_territory"], 3, 1, "in_territory", f"hosts located in {row['country_code']}"))
    out.append((row["p_sensitive"], 3, 2, "sensitive_stack", "database, medical or IoT systems in the stack"))
    return [c for c in out if c[0] > 0]


def cap_clause(cap_reasons):
    """Return the single cap clause for the first applicable reason in CAP_CLAUSES priority order, or an empty string."""
    reasons = set((cap_reasons or "").split(","))
    return next((text for reason, text in CAP_CLAUSES if reason in reasons), "")


def build_why(row):
    """Return (top_signals, why) for one account: exclude text, no-signal text, or the top two signals plus one cap or operator clause, the skip clause, and the D10 clause."""
    if row["band"] == "exclude":
        return None, f"Mostly honeypot or attacker-infrastructure hosts ({row['noise_host_count']} of {row['host_count'] + row['noise_host_count']})."
    clause = cap_clause(row["cap_reasons"])
    if not clause and row["band"] == "review" and row["operator_name_shape"]:
        clause = OPERATOR_CLAUSE  # D11.3: a review row reached by the top-N rule or the floor still shows the name flag
    if row["urgency_score"] == 0:
        return None, " ".join(x for x in (f"No exposure signal found in the scan ({plural_hosts(row['host_count'])} seen).", clause) if x)  # never a would-be contact
    ranked = sorted(signal_candidates(row), key=lambda c: (-c[0], c[1], c[2]))
    unverified = UNVERIFIED_CLAUSE if CAP_UNVERIFIED in (row["cap_reasons"] or "").split(",") else ""
    for keep in (2, 1):
        top = ranked[:keep]
        body = "; ".join(c[4] for c in top)
        tail = clause
        if not tail and row["band"] == "skip":  # D12.2: judged on the signals actually kept
            tail = SKIP_CLAUSE_SIGNAL if any(c[3] in SKIP_SIGNAL_NAMES for c in top) else SKIP_CLAUSE
        why = " ".join(x for x in (body[0].upper() + body[1:] + ".", tail, unverified) if x)
        if len(why.split()) <= WHY_MAX_WORDS:
            return ",".join(c[3] for c in top), why
    raise AssertionError(f"why too long even with one signal: {why}")


def build_accounts(con):
    """Create table accounts: the 17 output columns, with the rule-based why and top_signals filled per account, sorted per D9.6 item 8."""
    cur = con.execute("SELECT * FROM scored")
    names = [d[0] for d in cur.description]
    why_rows = []
    for values in cur.fetchall():
        row = dict(zip(names, values))
        top, why = build_why(row)
        why_rows.append((row["company_id"], top, why))
    con.execute("CREATE OR REPLACE TABLE why_tbl (company_id VARCHAR, top_signals VARCHAR, why VARCHAR)")
    if why_rows:
        con.executemany("INSERT INTO why_tbl VALUES (?, ?, ?)", why_rows)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE accounts AS
        SELECT s.company_id::VARCHAR AS account_id, s.company_name::VARCHAR AS company_name, s.country_code::VARCHAR AS country_code,
            s.host_count::INTEGER AS host_count, s.identity_source::VARCHAR AS identity_source, s.identity_confidence::VARCHAR AS identity_confidence,
            s.fit_score::INTEGER AS fit_score, s.urgency_score::INTEGER AS urgency_score, s.contact_score::INTEGER AS contact_score,
            w.top_signals::VARCHAR AS top_signals, s.band_uncapped::VARCHAR AS band_uncapped, s.cap_reasons::VARCHAR AS cap_reasons,
            s.band::VARCHAR AS band, w.why::VARCHAR AS why, NULL::VARCHAR AS decision, NULL::VARCHAR AS prompt_version,
            s.band::VARCHAR AS final_band
        FROM scored s JOIN why_tbl w USING (company_id)
        ORDER BY {stage_order_sql('account_id')}
        """
    )
    n_sig = con.execute("SELECT count(*) FROM signals").fetchone()[0]
    n_acc = con.execute("SELECT count(*) FROM accounts").fetchone()[0]
    uniq = con.execute("SELECT count(DISTINCT account_id) FROM accounts").fetchone()[0]
    assert n_sig == n_acc == uniq, f"fan-out or drop: signals {n_sig}, accounts {n_acc}, distinct account_id {uniq}"
    empty = con.execute("SELECT count(*) FROM accounts WHERE why IS NULL OR trim(why) = ''").fetchone()[0]
    assert empty == 0, f"{empty} accounts with an empty why"


def write_output(con, output_path):
    """Write table accounts to the gold parquet path (zstd)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY accounts TO '{quote_path(output_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def run_stage(con, input_path, output_path, contact=THRESHOLD_CONTACT, review=THRESHOLD_REVIEW, review_n=REVIEW_N):
    """Score, band, explain and write one signals file; return the row counts."""
    assert review < contact, "review threshold must be below the contact threshold"
    assert review_n >= 0, "review_n must not be negative"
    build_scored(con, input_path, contact, review, review_n)
    build_accounts(con)
    write_output(con, output_path)
    return {"signals_rows": con.execute("SELECT count(*) FROM signals").fetchone()[0],
            "accounts_rows": con.execute("SELECT count(*) FROM accounts").fetchone()[0]}


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


def band_counts(con, contact, review, review_n):
    """Return {band: count} at the given thresholds, computed from table scored with caps applied."""
    rows = con.execute(f"SELECT {band_sql(contact, review, review_n)} AS b, count(*) FROM scored GROUP BY 1").fetchall()
    counts = dict(rows)
    return {b: counts.get(b, 0) for b in BANDS}


def section_distributions(con, rep, output_path, total):
    """Report the quantiles and ASCII histogram of the three scores using the scoring-calibration helper."""
    rep.add("\n## 2. Score distributions (score_distribution.py)\n")
    helper = load_module("score_distribution", DISTRIBUTION_SCRIPT)
    out = Path(output_path).as_posix()
    helper_con = duckdb.connect()
    helper_con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{quote_path(out)}')")
    for score in ("fit_score", "urgency_score", "contact_score"):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            helper.print_summary(helper_con, score)
            helper.print_histogram(helper_con, score, HISTOGRAM_BUCKETS)
        rep.add("```\n" + buf.getvalue().rstrip() + "\n```")
    nonzero = con.execute("SELECT count(*) FILTER (WHERE contact_score > 0), count(*) FILTER (WHERE urgency_score > 0), "
                          "count(*) FILTER (WHERE fit_score > 0) FROM accounts").fetchone()
    rep.add(f"Accounts scoring above 0: contact {nonzero[0]:,} ({pct(nonzero[0], total)}), urgency {nonzero[1]:,} ({pct(nonzero[1], total)}), "
            f"fit {nonzero[2]:,} ({pct(nonzero[2], total)}).")


def section_bands(con, rep, contact, review, review_n, total):
    """Report band counts at the run settings, the D11 comparison, the review cut and tie, threshold previews, cap effects, review composition and the skip exposure."""
    rep.add(f"\n## 3. Bands at contact >= {contact}, review = would-be contacts plus the top {review_n} with contact_score >= {review} (PROVISIONAL)\n")
    counts = dict(con.execute("SELECT band, count(*) FROM accounts GROUP BY 1").fetchall())
    rep.table(("band", "accounts", "share"), [(b, f"{counts.get(b, 0):,}", pct(counts.get(b, 0), total)) for b in BANDS])
    rep.add(f"\n### Previous run (D10, threshold-only review) and the senior's D11 expectation (X = {contact}, Y = {review}, N = {review_n})\n")
    rows = [(b, f"{PREVIOUS_RUN[b]:,}", D11_EXPECTED[b], f"{counts.get(b, 0):,}") for b in BANDS]
    rep.table(("band", "previous run (D10)", "senior's D11 expectation", "this run"), rows)
    section_cut(con, rep, contact, review, review_n)
    rep.add("\n### Threshold previews (every would-be contact is held in review by operator_unverified; the top-N rule applies at each pair)\n")
    rows = []
    for pair in COMPARE_PAIRS:
        mine = band_counts(con, pair[0], pair[1], review_n)
        would = con.execute(f"SELECT count(*) FROM scored WHERE contact_score >= {pair[0]} AND NOT (noise_host_count >= {NOISE_MIN_HOSTS} AND noise_host_share >= {NOISE_MIN_SHARE})").fetchone()[0]
        rows.append((f"{pair[0]} / {pair[1]}", " / ".join(f"{mine[b]:,}" for b in BANDS), f"{would:,}"))
    rep.table(("contact / review thresholds", "this stage: contact / review / skip / exclude", "would-be contacts (now in review)"), rows)
    rep.add(f"\n### Cap effects (at {contact} / {review})\n")
    would = con.execute("SELECT count(*) FROM scored WHERE band_uncapped = 'contact'").fetchone()[0]
    moved = con.execute("SELECT count(*) FROM accounts WHERE cap_reasons IS NOT NULL").fetchone()[0]
    rep.add(f"Would-be contacts (band_uncapped = contact, not excluded): {would:,} (D11.5 expected about {D11_EXPECTED_WOULD_BE}); moved to review by a cap: {moved:,}; remain contact: {would - moved:,} (D10: none; only adjudication may set final_band = contact).\n")
    rows = [(reason, con.execute(f"SELECT count(*) FROM accounts WHERE list_contains(string_split(coalesce(cap_reasons, ''), ','), '{reason}')").fetchone()[0])
            for reason in [r for r, _ in CAP_CLAUSES] + [CAP_UNVERIFIED]]
    only = dict(con.execute("SELECT cap_reasons, count(*) FROM accounts WHERE cap_reasons IS NOT NULL GROUP BY 1 ORDER BY 2 DESC").fetchall())
    rep.table(("cap reason (accounts carrying it; some carry two or three)", "accounts"), rows)
    rep.add("\nBy exact reason set: " + "; ".join(f"{k} = {v}" for k, v in only.items()) + ".")
    rep.add(f"\n### Review band composition (at {contact} / {review} / N = {review_n})\n")
    rv, capped, thr, single, op, op_nocap, low, us = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE a.cap_reasons IS NOT NULL), count(*) FILTER (WHERE a.cap_reasons IS NULL), "
        "count(*) FILTER (WHERE s.is_singleton), count(*) FILTER (WHERE s.operator_name_shape), "
        "count(*) FILTER (WHERE s.operator_name_shape AND a.cap_reasons IS NULL), "
        "count(*) FILTER (WHERE s.identity_confidence = 'low'), count(*) FILTER (WHERE s.country_code = 'US') "
        "FROM accounts a JOIN scored s ON s.company_id = a.account_id WHERE a.band = 'review'").fetchone()
    rep.table(("review accounts", "value"), [
        ("total", f"{rv:,}"), ("reached by a cap (was contact)", f"{capped:,}"), ("reached by the top-N rule alone", f"{thr:,}"),
        ("singletons", f"{single:,}"), ("operator-shaped (T1 or T2)", f"{op:,}"), ("operator-shaped among the top-N-only rows (get the D11.3 clause)", f"{op_nocap:,}"),
        ("low identity confidence", f"{low:,}"), ("country US", f"{us:,}")])
    excl = con.execute("SELECT company_name, host_count, noise_host_count, noise_host_share FROM scored WHERE band = 'exclude'").fetchall()
    rep.add(f"\nExclude band (D9.3 rule, noise_host_count >= {NOISE_MIN_HOSTS} AND noise_host_share >= {NOISE_MIN_SHARE}): {len(excl)} account(s): "
            + "; ".join(f"{n} ({h} hosts, {k} noise rows, share {s:.2f})" for n, h, k, s in excl) + ".")
    section_skip_exposure(con, rep, review)


def section_cut(con, rep, contact, review, review_n):
    """Report where the top-N cut falls: the score at the cut, the tie size there and how many of the tie are kept (D11.2)."""
    rep.add(f"\n### Review cut (N = {review_n}, floor {review})\n")
    would = con.execute(f"SELECT count(*) FROM scored WHERE band <> 'exclude' AND contact_score >= {contact}").fetchone()[0]
    if would >= review_n:
        rep.add(f"Would-be contacts ({would:,}) reach or exceed N = {review_n:,}: the band is the would-be contacts only; no top-N cut.")
        return
    cut = con.execute(f"SELECT contact_score FROM scored WHERE review_rank = {review_n}").fetchone()
    if cut is None or cut[0] < review:
        rep.add(f"The floor ({review}) binds before N: fewer than {review_n:,} non-excluded accounts score at {review} or more; no tie at the cut.")
        return
    score = cut[0]
    tied, kept = con.execute(f"SELECT count(*), count(*) FILTER (WHERE review_rank <= {review_n}) FROM scored WHERE contact_score = {score} AND review_rank IS NOT NULL").fetchone()
    rep.add(f"The cut falls at contact_score {score}: {tied:,} non-excluded accounts are tied at {score}, {kept:,} are kept in review and {tied - kept:,} go to skip "
            f"(tie broken by {STAGE_ORDER_TEXT}; D12.1 measured score {D11_EXPECTED_TIE[0]} with a tie of {D11_EXPECTED_TIE[1]} on the D11 output). "
            f"Accounts above the cut score: {review_n - kept:,}.")
    names = con.execute(f"SELECT company_name, operator_name_shape, is_singleton, coalesce(kev_host_count, 0), host_count FROM scored WHERE contact_score = {score} AND review_rank <= {review_n} ORDER BY review_rank").fetchall()
    rep.add("Kept at the cut: " + "; ".join(f"{n} ({'flagged' if f else 'unflagged'}, {'singleton' if s else f'{h} hosts'}, {k} KEV hosts)" for n, f, s, k, h in names) + f". D12.1 simulation: {D12_EXPECTED_KEPT}.")


def section_skip_exposure(con, rep, review=THRESHOLD_REVIEW):
    """Report skip accounts with urgency above 0 and, split at the floor, those with a non-SSH admin or database port or CVSS 7 or more (D11.3 measured 42 + 32 = 74 below the floor)."""
    rows = con.execute(
        "SELECT a.contact_score < ?, count(*), count(*) FILTER (WHERE s.risky_non_ssh_exposed), count(*) FILTER (WHERE s.max_cvss_band >= 2), "
        "count(*) FILTER (WHERE s.risky_non_ssh_exposed AND s.max_cvss_band >= 2), count(*) FILTER (WHERE s.risky_non_ssh_exposed OR s.max_cvss_band >= 2) "
        "FROM accounts a JOIN scored s ON s.company_id = a.account_id WHERE a.band = 'skip' AND a.urgency_score > 0 GROUP BY 1 ORDER BY 1 DESC", [review]).fetchall()
    rep.add(f"\nSkip accounts with urgency_score above 0, split at the floor Y = {review} (none is routed to review, D11.3; the clause is \"{SKIP_CLAUSE}\", or \"{SKIP_CLAUSE_SIGNAL}\" where a KEV or CVSS sentence is kept, D12.2):\n")
    rep.table(("where", "skip accounts urgency > 0", "non-SSH admin or database port", "CVSS 7.0 or more", "both", "union"),
              [(f"contact_score below {review} (D11.3 measured 659, 42, 32, 0, 74)" if below else f"contact_score {review} or more, beyond the top-N cut", *r[1:]) for r in rows for below in [r[0]]])
    sig_rows = con.execute("SELECT count(*), count(*) FILTER (WHERE contains(top_signals, 'kev_exposed')), count(*) FILTER (WHERE contains(top_signals, 'max_cvss_band')), "
                           "count(*) FILTER (WHERE contact_score >= ?), count(*) FILTER (WHERE contact_score < ?) FROM accounts WHERE band = 'skip' AND why LIKE ?",
                           [review, review, "%" + SKIP_CLAUSE_SIGNAL]).fetchone()
    plain = con.execute("SELECT count(*) FROM accounts WHERE band = 'skip' AND why LIKE ?", ["%" + SKIP_CLAUSE]).fetchone()[0]
    rep.add(f"\nSkip rows ending with the D12.2 clause: {sig_rows[0]:,} (KEV {sig_rows[1]:,}, CVSS {sig_rows[2]:,}; at or above the floor {sig_rows[3]:,}, below {sig_rows[4]:,}); D12 expected {D12_EXPECTED_SKIP_SIGNAL} = 303 + 234, 455 and 82. "
            f"Skip rows with the plain clause: {plain:,}.")
    exp = con.execute("SELECT count(*) FROM accounts WHERE why LIKE ?", ["%" + EXPOSED_OUTDATED_TEXT + "%"]).fetchone()[0]
    longest = con.execute("SELECT max(len(string_split(why, ' '))) FILTER (WHERE band = 'skip'), max(len(string_split(why, ' '))) FROM accounts").fetchone()
    rep.add(f"Accounts whose why carries the D12.3 exposure phrase: {exp:,} (D12 expected 45). Longest why in words: skip {longest[0]}, all rows {longest[1]} (limit {WHY_MAX_WORDS}).")


def section_union_effect(con, rep, n):
    """Report how many accounts lose fit because the penalty now covers T2-only names (D10) and how contact_score ranks moved, versus a T1-only penalty."""
    rep.add("\n### Effect of the union penalty (D10) versus the previous T1-only penalty\n")
    base = "p_territory + p_footprint + p_sensitive"
    t1_fit = f"greatest(0, least(100, {base} - CASE WHEN operator_shape_t1 THEN {PENALTY_OPERATOR} ELSE 0 END))"
    alt = contact_expr_sql("t1_fit")
    con.execute(f"CREATE OR REPLACE TABLE rank_cmp AS SELECT company_id, fit_score, contact_score, urgency_score, host_count, operator_name_shape, kev_host_count, {t1_fit} AS t1_fit FROM scored")
    con.execute(f"CREATE OR REPLACE TABLE rank_cmp AS SELECT *, ({alt})::INTEGER AS t1_contact FROM rank_cmp")
    con.execute(f"CREATE OR REPLACE TABLE rank_cmp AS SELECT *, row_number() OVER (ORDER BY {stage_order_sql('company_id')}) AS rank_new, "
                f"row_number() OVER (ORDER BY {stage_order_sql('company_id', 't1_contact')}) AS rank_old FROM rank_cmp")
    changed, lost, avg_loss, cchanged, max_loss = con.execute(
        "SELECT count(*) FILTER (WHERE fit_score <> t1_fit), sum(t1_fit - fit_score), avg(t1_fit - fit_score) FILTER (WHERE fit_score <> t1_fit), "
        "count(*) FILTER (WHERE contact_score <> t1_contact), max(t1_fit - fit_score) FROM rank_cmp").fetchone()
    rep.add(f"Accounts whose fit_score fell because the penalty now covers T2-only names: {changed:,} (total {lost or 0:,} fit points, mean {avg_loss or 0:.1f} per changed account, max {max_loss or 0}); "
            f"accounts whose contact_score changed: {cchanged:,}.")
    for k in (25, 50):
        gone = con.execute(f"SELECT count(*) FROM rank_cmp WHERE rank_old <= {k} AND rank_new > {k}").fetchone()[0]
        rep.add(f"Of the previous top {k} by contact_score, {gone} are no longer in the top {k}.")
    shifted, worst = con.execute(f"SELECT count(*) FILTER (WHERE rank_new <> rank_old), max(abs(rank_new - rank_old)) FILTER (WHERE rank_old <= {n} OR rank_new <= {n}) FROM rank_cmp").fetchone()
    rep.add(f"Accounts with a different overall rank: {shifted:,}; largest rank shift among accounts in either top {n}: {worst or 0}.")


def section_top(con, rep, n):
    """Report the top accounts with their why and the count flagged as operator-shaped by the name regexes (a manual read is added by hand)."""
    rep.add(f"\n## 4. Top {n} accounts by contact_score\n")
    rows = con.execute(
        f"SELECT a.company_name, a.country_code, a.host_count, a.fit_score, a.urgency_score, a.contact_score, a.band, coalesce(a.cap_reasons, ''), "
        f"s.operator_shape_t1, s.operator_shape_t2, a.why FROM accounts a JOIN scored s ON s.company_id = a.account_id "
        f"ORDER BY {stage_order_sql('a.account_id', 'a.contact_score', 'a.', 's.')} LIMIT {n}").fetchall()
    rep.table(("company", "cc", "hosts", "fit", "urgency", "contact", "band", "cap_reasons", "T1", "T2", "why"), rows)
    flagged = sum(1 for r in rows if r[8] or r[9])
    t1 = sum(1 for r in rows if r[8])
    rep.add(f"\nOf the top {n}, {flagged} carry the operator-name flag (T1 or T2; T1 alone {t1}). A by-eye read of the names (not a rule, not acted on) follows in section 7.")


def section_output(con, rep, output_path, signals_rows):
    """Report the output file, row equality, 17 columns, null rates, 5 random rows and the invariants checked by assertion."""
    report = load_module("stage_report", REPORT_SCRIPT)
    out = Path(output_path).as_posix()
    total = report.count_rows(con, out)
    assert total == signals_rows, "accounts rows != signals rows"
    described = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{quote_path(out)}')").fetchall()
    cols = [(r[0], r[1]) for r in described]
    assert tuple(cols) == OUTPUT_COLUMNS, f"output columns differ from D9.6 item 9: {cols}"
    rep.add(f"\n## 5. Output file\n\nPath: {out}; rows: {total:,}; columns: {len(cols)}. Previous layer (signals rows): {signals_rows:,}; difference 0 "
            f"(asserted: one row per company, account_id unique, no fan-out, no drop).\n\nColumns: " + ", ".join(f"{n} {t}" for n, t in cols) + ".\n")
    bad = con.execute(
        f"SELECT count(*) FROM accounts WHERE fit_score NOT BETWEEN 0 AND 100 OR urgency_score NOT BETWEEN 0 AND 100 OR contact_score NOT BETWEEN 0 AND 100 "
        f"OR final_band <> band OR band = 'contact' OR band IS NULL OR band_uncapped IS NULL OR trim(why) = '' OR decision IS NOT NULL OR prompt_version IS NOT NULL").fetchone()[0]
    assert bad == 0, f"{bad} accounts break a basic invariant"
    if CONTACT_FORM == "b":
        viol = con.execute(f"SELECT count(*) FROM accounts WHERE contact_score > urgency_score OR contact_score * 100 < {FLOOR_PCT} * urgency_score - 50").fetchone()[0]
        assert viol == 0, f"{viol} accounts break FLOOR * urgency <= contact <= urgency"
    rep.add("Asserted in the run: scores within 0 to 100; every account has a band, band_uncapped and a non-empty why; final_band = band; decision and "
            "prompt_version all null and no account in band contact (D10: only LLM adjudication may set final_band = contact); FLOOR * urgency <= contact_score <= urgency (rounding tolerance 0.5).\n")
    rep.add("Null rates (all columns, worst first):\n")
    rep.table(("column", "null rate"), [(c, f"{p}%") for c, p in report.null_rates(con, out, KEY_COLUMNS, total)])
    rep.add("\n5 random rows:\n")
    cur = con.execute(f"SELECT * FROM read_parquet('{quote_path(out)}') USING SAMPLE reservoir(5 ROWS) REPEATABLE (7)")
    names = [d[0] for d in cur.description]
    for i, row in enumerate(cur.fetchall(), 1):
        rep.add(f"- [{i}] " + ", ".join(f"{k}={str(v)[:70]}" for k, v in zip(names, row)))


def print_report(con, run, output_path, report_path, contact, review, review_n=REVIEW_N):
    """Print and save the stage report; assertions fail the run when the arithmetic breaks."""
    rep = Report()
    total = run["accounts_rows"]
    rep.add(f"# Accounts stage report ({datetime.date.today().isoformat()})\n")
    rep.add("**PROVISIONAL CONSTANTS: not calibrated, not owner-approved.** Points, FLOOR, thresholds, N and the T1-or-T2 operator penalty (D10, D11 provisional) are the D9.7 starting point, "
            "used so the stage can be exercised; read no band here as a decision. Contact form: "
            f"({CONTACT_FORM}), FLOOR {FLOOR_PCT / 100:.2f}, X = {contact}, Y = {review} (floor of the review band), N = {review_n}, territory points {IN_TERRITORY_POINTS} (neutral, D11.5).\n")
    rep.add("## 1. Row counts\n")
    rep.add(f"signals {run['signals_rows']:,} = accounts {total:,} (asserted; account_id unique, equal to company_id). Output: {Path(output_path).as_posix()}.")
    section_distributions(con, rep, output_path, total)
    section_bands(con, rep, contact, review, review_n, total)
    section_union_effect(con, rep, TOP_N)
    section_top(con, rep, TOP_N)
    section_output(con, rep, output_path, run["signals_rows"])
    rep.save(report_path)
    print(f"\nreport saved to {Path(report_path).as_posix()}")


def main():
    """Run the stage on the sample signals (default) or the full-run file (--full); thresholds are command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="read signals_full, write accounts_full (not for dev)")
    parser.add_argument("--input", help="override the signals parquet path")
    parser.add_argument("--output", help="override the output parquet path")
    parser.add_argument("--contact", type=int, default=THRESHOLD_CONTACT, help="contact threshold X (provisional default)")
    parser.add_argument("--review", type=int, default=THRESHOLD_REVIEW, help="review threshold Y, the floor of the top-N review band (provisional default)")
    parser.add_argument("--review-n", type=int, default=REVIEW_N, help="N: total accounts in the review band, would-be contacts always kept (provisional default)")
    args = parser.parse_args()
    input_path = args.input or (FULL_INPUT_PATH if args.full else INPUT_PATH)
    output_path = args.output or (FULL_OUTPUT_PATH if args.full else OUTPUT_PATH)
    report_name = f"accounts_stage_{'full_' if args.full else ''}{datetime.date.today().isoformat()}.md"
    con = duckdb.connect()
    run = run_stage(con, input_path, output_path, args.contact, args.review, args.review_n)
    print_report(con, run, output_path, REPORT_DIR / report_name, args.contact, args.review, args.review_n)


if __name__ == "__main__":
    sys.exit(main())
