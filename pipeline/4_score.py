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
PTS_TERRITORY = 35  # fit: in_territory (the territory list in stage 3 is itself a placeholder)
PTS_FOOTPRINT_PER_BAND = 15  # fit: footprint_band x 15
PTS_SENSITIVE = 20  # fit: sensitive_stack
PENALTY_OPERATOR_T1 = 30  # fit: subtracted when operator_shape_t1 is true (T1 ONLY, see the comment at FIT_SQL)
FLOOR_PCT = 50  # contact form (b): FLOOR = 0.50, kept as a whole percent so the arithmetic is exact in integers
CONTACT_FORM = "b"  # "b" urgency gated by fit (recommended in D9.6 item 4); "a" weighted sum, kept only for the calibration comparison
W_F_PCT = 30  # form (a) only: weight of fit in percent; D9 gives no value, so this is a placeholder invented only to exercise form (a)
THRESHOLD_CONTACT = 40  # X
THRESHOLD_REVIEW = 20  # Y
# ======================================================================================================================
# End of PROVISIONAL block. The constants below are decided (D9.3, D9.6) or are display tables, not weights.
# ======================================================================================================================
NOISE_MIN_HOSTS = 2  # D9.3 (decided): exclude needs at least this many noise hosts ...
NOISE_MIN_SHARE = 0.5  # ... and at least this noise share
CAP_SINGLETON = "singleton"
CAP_LOW_CONFIDENCE = "low_confidence"
CAP_OPERATOR = "operator_name_shape"
CAP_CLAUSES = (  # priority order for the single cap clause in the why
    (CAP_OPERATOR, "Name looks like a network operator."),
    (CAP_SINGLETON, "Only one host seen."),
    (CAP_LOW_CONFIDENCE, "Named only by a TLS certificate."),
)
WHY_MAX_WORDS = 40
PORT_NAMES = {22: "SSH", 3389: "RDP", 445: "SMB", 3306: "MySQL", 6379: "Redis", 27017: "MongoDB", 9200: "Elasticsearch", 5900: "VNC",
              23: "Telnet", 2375: "Docker"}
PORTS_SHOWN = 2  # at most this many ports are named in a why
SSH_PORT = 22
BANDS = ("contact", "review", "skip", "exclude")
SENIOR_RUN = {  # D9.8 provisional run (ad hoc, T1 plus T2 penalty): thresholds -> (contact, review, skip, exclude)
    (45, 25): (43, 530, 5216, 1), (40, 20): (71, 593, 5125, 1), (35, 15): (138, 536, 5115, 1)}
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


def band_sql(contact, review):
    """Return a SQL CASE expression for the final band at the given thresholds, in D9.6 order: exclude, thresholds, then caps."""
    exclude = f"(noise_host_count >= {NOISE_MIN_HOSTS} AND noise_host_share >= {NOISE_MIN_SHARE})"
    uncapped = f"CASE WHEN contact_score >= {contact} THEN 'contact' WHEN contact_score >= {review} THEN 'review' ELSE 'skip' END"
    capped = "(is_singleton OR identity_confidence = 'low' OR operator_name_shape)"
    return f"CASE WHEN {exclude} THEN 'exclude' WHEN contact_score >= {contact} AND {capped} THEN 'review' ELSE {uncapped} END"


def build_scored(con, input_path, contact, review):
    """Create table scored: the signals plus point columns, the three scores, band_uncapped, cap_reasons and band (D9.6 items 2 to 5)."""
    con.execute(f"CREATE OR REPLACE TABLE signals AS SELECT * FROM read_parquet('{quote_path(input_path)}')")
    cvss = cvss_points_sql()
    # Fit penalty uses operator_shape_t1 ONLY. T2 (operator_shape_t2) is computed in stage 3 and is deliberately NOT used in the
    # penalty until the data-analyst's T2 gate passes (D9.5). The caps below still use operator_name_shape (the T1-or-T2 union), as D9.6 item 5 says.
    if CONTACT_FORM == "b":
        contact_expr = f"(urgency_score * ({FLOOR_PCT * 100} + {100 - FLOOR_PCT} * fit_score) + 5000) // 10000"
    else:
        contact_expr = f"({W_F_PCT} * fit_score + {100 - W_F_PCT} * urgency_score + 50) // 100"
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
            (CASE WHEN coalesce(in_territory, false) THEN {PTS_TERRITORY} ELSE 0 END)::INTEGER AS p_territory,
            (CASE WHEN sensitive_stack THEN {PTS_SENSITIVE} ELSE 0 END)::INTEGER AS p_sensitive,
            (CASE WHEN operator_shape_t1 THEN {PENALTY_OPERATOR_T1} ELSE 0 END)::INTEGER AS p_penalty
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
                                             CASE WHEN is_singleton THEN '{CAP_SINGLETON}' END), '')
                  ELSE NULL END) AS cap_reasons
        FROM scored
        """
    )
    con.execute(f"CREATE OR REPLACE TABLE scored AS SELECT *, ({band_sql(contact, review)}) AS band FROM scored")


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
            phrase = f"{plural_hosts(row['kev_host_count'])} with a vulnerability on the CISA known-exploited list"
        else:
            phrase = f"worst vulnerability scores CVSS {row['max_cvss']:.1f}"
        out.append((row["p_vuln"], 0, 0, row["vuln_signal"], phrase))
    if row["p_expo"] > 0:
        sig = row["expo_signal"]
        if sig == "exposed_and_outdated":
            phrase = f"an exposed admin or database service ({port_text(ports)}) on outdated software"
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
    """Return (top_signals, why) for one account: exclude text, no-signal text, or the top two signals by points plus one cap clause (D9.8)."""
    if row["band"] == "exclude":
        return None, f"Mostly honeypot or attacker-infrastructure hosts ({row['noise_host_count']} of {row['host_count'] + row['noise_host_count']})."
    clause = cap_clause(row["cap_reasons"])
    if row["urgency_score"] == 0:
        return None, " ".join(x for x in (f"No exposure signal found in the scan ({plural_hosts(row['host_count'])} seen).", clause) if x)
    ranked = sorted(signal_candidates(row), key=lambda c: (-c[0], c[1], c[2]))
    tail = clause or ("Exposure is limited." if row["band"] == "skip" else "")
    for keep in (2, 1):
        top = ranked[:keep]
        body = "; ".join(c[4] for c in top)
        why = " ".join(x for x in (body[0].upper() + body[1:] + ".", tail) if x)
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
        """
        CREATE OR REPLACE TABLE accounts AS
        SELECT s.company_id::VARCHAR AS account_id, s.company_name::VARCHAR AS company_name, s.country_code::VARCHAR AS country_code,
            s.host_count::INTEGER AS host_count, s.identity_source::VARCHAR AS identity_source, s.identity_confidence::VARCHAR AS identity_confidence,
            s.fit_score::INTEGER AS fit_score, s.urgency_score::INTEGER AS urgency_score, s.contact_score::INTEGER AS contact_score,
            w.top_signals::VARCHAR AS top_signals, s.band_uncapped::VARCHAR AS band_uncapped, s.cap_reasons::VARCHAR AS cap_reasons,
            s.band::VARCHAR AS band, w.why::VARCHAR AS why, NULL::VARCHAR AS decision, NULL::VARCHAR AS prompt_version,
            s.band::VARCHAR AS final_band
        FROM scored s JOIN why_tbl w USING (company_id)
        ORDER BY contact_score DESC, urgency_score DESC, host_count DESC, account_id
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


def run_stage(con, input_path, output_path, contact=THRESHOLD_CONTACT, review=THRESHOLD_REVIEW):
    """Score, band, explain and write one signals file; return the row counts."""
    assert review < contact, "review threshold must be below the contact threshold"
    build_scored(con, input_path, contact, review)
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


def band_counts(con, contact, review):
    """Return {band: count} at the given thresholds, computed from table scored with caps applied."""
    rows = con.execute(f"SELECT {band_sql(contact, review)} AS b, count(*) FROM scored GROUP BY 1").fetchall()
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


def section_bands(con, rep, contact, review, total):
    """Report band counts at the run thresholds, the threshold previews against the senior's run, and the cap effects and review composition."""
    rep.add(f"\n## 3. Bands at contact >= {contact}, review >= {review} (PROVISIONAL)\n")
    counts = dict(con.execute("SELECT band, count(*) FROM accounts GROUP BY 1").fetchall())
    rep.table(("band", "accounts", "share"), [(b, f"{counts.get(b, 0):,}", pct(counts.get(b, 0), total)) for b in BANDS])
    rep.add("\n### Threshold previews against the senior's provisional run (D9.8, ad hoc, T1 plus T2 penalty)\n")
    rows = []
    for pair in COMPARE_PAIRS:
        mine = band_counts(con, *pair)
        senior = SENIOR_RUN[pair]
        rows.append((f"{pair[0]} / {pair[1]}", " / ".join(f"{mine[b]:,}" for b in BANDS), " / ".join(f"{n:,}" for n in senior),
                     " / ".join(f"{mine[b] - n:+,}" for b, n in zip(BANDS, senior))))
    rep.table(("contact / review thresholds", "this stage: contact / review / skip / exclude", "senior: same order", "difference"), rows)
    rep.add(f"\n### Cap effects (at {contact} / {review})\n")
    would = con.execute(f"SELECT count(*) FROM scored WHERE band_uncapped = 'contact'").fetchone()[0]
    moved = con.execute("SELECT count(*) FROM accounts WHERE cap_reasons IS NOT NULL").fetchone()[0]
    rep.add(f"Would-be contacts (band_uncapped = contact, not excluded): {would:,}; moved to review by a cap: {moved:,}; remain contact: {would - moved:,}.")
    rows = [(reason, con.execute(f"SELECT count(*) FROM accounts WHERE list_contains(string_split(coalesce(cap_reasons, ''), ','), '{reason}')").fetchone()[0])
            for reason, _ in CAP_CLAUSES]
    only = dict(con.execute("SELECT cap_reasons, count(*) FROM accounts WHERE cap_reasons IS NOT NULL GROUP BY 1 ORDER BY 2 DESC").fetchall())
    rep.table(("cap reason (accounts carrying it; some carry two or three)", "accounts"), rows)
    rep.add("\nBy exact reason set: " + "; ".join(f"{k} = {v}" for k, v in only.items()) + ".")
    rep.add(f"\n### Review band composition (at {contact} / {review})\n")
    rv, capped, thr, single, op, low, us = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE a.cap_reasons IS NOT NULL), count(*) FILTER (WHERE a.cap_reasons IS NULL), "
        "count(*) FILTER (WHERE s.is_singleton), count(*) FILTER (WHERE s.operator_name_shape), "
        "count(*) FILTER (WHERE s.identity_confidence = 'low'), count(*) FILTER (WHERE s.country_code = 'US') "
        "FROM accounts a JOIN scored s ON s.company_id = a.account_id WHERE a.band = 'review'").fetchone()
    rep.table(("review accounts", "value", "senior (40 / 20)"), [
        ("total", f"{rv:,}", "593"), ("reached by a cap (was contact)", f"{capped:,}", "37"), ("reached by threshold alone", f"{thr:,}", "556"),
        ("singletons", f"{single:,}", "325"), ("operator-shaped (T1 or T2)", f"{op:,}", "187"), ("low identity confidence", f"{low:,}", "21"),
        ("country US", f"{us:,}", "125")])
    excl = con.execute("SELECT company_name, host_count, noise_host_count, noise_host_share FROM scored WHERE band = 'exclude'").fetchall()
    rep.add(f"\nExclude band (D9.3 rule, noise_host_count >= {NOISE_MIN_HOSTS} AND noise_host_share >= {NOISE_MIN_SHARE}): {len(excl)} account(s): "
            + "; ".join(f"{n} ({h} hosts, {k} noise rows, share {s:.2f})" for n, h, k, s in excl) + ".")


def section_top(con, rep, n):
    """Report the top accounts with their why and the count flagged as operator-shaped by the name regexes (a manual read is added by hand)."""
    rep.add(f"\n## 4. Top {n} accounts by contact_score\n")
    rows = con.execute(
        f"SELECT a.company_name, a.country_code, a.host_count, a.fit_score, a.urgency_score, a.contact_score, a.band, coalesce(a.cap_reasons, ''), "
        f"s.operator_shape_t1, s.operator_shape_t2, a.why FROM accounts a JOIN scored s ON s.company_id = a.account_id "
        f"ORDER BY a.contact_score DESC, a.urgency_score DESC, a.host_count DESC, a.account_id LIMIT {n}").fetchall()
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
        f"OR final_band <> band OR band IS NULL OR band_uncapped IS NULL OR trim(why) = '' OR decision IS NOT NULL OR prompt_version IS NOT NULL").fetchone()[0]
    assert bad == 0, f"{bad} accounts break a basic invariant"
    if CONTACT_FORM == "b":
        viol = con.execute(f"SELECT count(*) FROM accounts WHERE contact_score > urgency_score OR contact_score * 100 < {FLOOR_PCT} * urgency_score - 50").fetchone()[0]
        assert viol == 0, f"{viol} accounts break FLOOR * urgency <= contact <= urgency"
    rep.add("Asserted in the run: scores within 0 to 100; every account has a band, band_uncapped and a non-empty why; final_band = band; decision and "
            "prompt_version all null (LLM adjudication is a later milestone); FLOOR * urgency <= contact_score <= urgency (rounding tolerance 0.5).\n")
    rep.add("Null rates (all columns, worst first):\n")
    rep.table(("column", "null rate"), [(c, f"{p}%") for c, p in report.null_rates(con, out, KEY_COLUMNS, total)])
    rep.add("\n5 random rows:\n")
    cur = con.execute(f"SELECT * FROM read_parquet('{quote_path(out)}') USING SAMPLE reservoir(5 ROWS) REPEATABLE (7)")
    names = [d[0] for d in cur.description]
    for i, row in enumerate(cur.fetchall(), 1):
        rep.add(f"- [{i}] " + ", ".join(f"{k}={str(v)[:70]}" for k, v in zip(names, row)))


def print_report(con, run, output_path, report_path, contact, review):
    """Print and save the stage report; assertions fail the run when the arithmetic breaks."""
    rep = Report()
    total = run["accounts_rows"]
    rep.add(f"# Accounts stage report ({datetime.date.today().isoformat()})\n")
    rep.add("**PROVISIONAL CONSTANTS: not calibrated, not owner-approved.** Points, FLOOR, thresholds and the T1-only penalty are the D9.7 starting point, "
            "used so the stage can be exercised; read no band here as a decision. Contact form: "
            f"({CONTACT_FORM}), FLOOR {FLOOR_PCT / 100:.2f}, X = {contact}, Y = {review}.\n")
    rep.add("## 1. Row counts\n")
    rep.add(f"signals {run['signals_rows']:,} = accounts {total:,} (asserted; account_id unique, equal to company_id). Output: {Path(output_path).as_posix()}.")
    section_distributions(con, rep, output_path, total)
    section_bands(con, rep, contact, review, total)
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
    parser.add_argument("--review", type=int, default=THRESHOLD_REVIEW, help="review threshold Y (provisional default)")
    args = parser.parse_args()
    input_path = args.input or (FULL_INPUT_PATH if args.full else INPUT_PATH)
    output_path = args.output or (FULL_OUTPUT_PATH if args.full else OUTPUT_PATH)
    report_name = f"accounts_stage_{'full_' if args.full else ''}{datetime.date.today().isoformat()}.md"
    con = duckdb.connect()
    run = run_stage(con, input_path, output_path, args.contact, args.review)
    print_report(con, run, output_path, REPORT_DIR / report_name, args.contact, args.review)


if __name__ == "__main__":
    sys.exit(main())
