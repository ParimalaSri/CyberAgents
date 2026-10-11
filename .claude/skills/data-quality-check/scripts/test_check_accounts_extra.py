"""Tests for check_accounts_extra.py and context/contracts/accounts.yml (D11): hand-computed unit cases, a clean synthetic layer, injected-fault mutations including the top-N cut."""
import hashlib
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_accounts_extra as extra  # noqa: E402
import check_contract as runner  # noqa: E402

CONTRACT_PATH = extra.REPO_ROOT / "context" / "contracts" / "accounts.yml"
SIGNALS_PLACEHOLDER = "data/gold/signals.parquet"
COMPANIES_PLACEHOLDER = "data/silver/companies.parquet"
CLAUSE = extra.CLAUSE
KEV_PHRASE = "running software whose version matches the CISA known-exploited list"  # D11.3
OLD_KEV = "with a vulnerability on the CISA known-exploited list"  # pre-D11 wording
SKIP = extra.SKIP_CLAUSE
OPC = extra.OPERATOR_CLAUSE
TEST_N = 8  # review band size of the synthetic layer; the contract text is rewritten from 200 to this value (see run_contract)
SIGNAL_TYPES = (
    ("company_id", "VARCHAR"), ("company_name", "VARCHAR"), ("name_norm", "VARCHAR"), ("identity_source", "VARCHAR"), ("identity_confidence", "VARCHAR"),
    ("host_count", "INTEGER"), ("distinct_host_ips", "INTEGER"), ("country_code", "VARCHAR"), ("noise_host_count", "INTEGER"), ("noise_host_share", "DOUBLE"),
    ("counted_host_count", "INTEGER"), ("host_signals_blind", "BOOLEAN"), ("is_singleton", "BOOLEAN"), ("in_territory", "BOOLEAN"), ("named_registrant", "BOOLEAN"),
    ("footprint_size", "INTEGER"), ("footprint_band", "SMALLINT"), ("sensitive_stack", "BOOLEAN"), ("operator_shape_t1", "BOOLEAN"), ("operator_shape_t2", "BOOLEAN"),
    ("operator_name_shape", "BOOLEAN"), ("kev_exposed", "BOOLEAN"), ("kev_host_count", "INTEGER"), ("max_cvss", "DOUBLE"), ("max_cvss_band", "SMALLINT"),
    ("cert_expired_or_soon", "BOOLEAN"), ("cert_issue_host_count", "INTEGER"), ("eol_stack", "BOOLEAN"), ("eol_host_count", "INTEGER"), ("legacy_tls", "BOOLEAN"),
    ("legacy_tls_host_count", "INTEGER"), ("risky_service_exposed", "BOOLEAN"), ("risky_non_ssh_exposed", "BOOLEAN"), ("risky_service_host_count", "INTEGER"),
    ("risky_ports", "INTEGER[]"), ("exposed_and_outdated", "BOOLEAN"))
ACCOUNT_TYPES = (("account_id", "VARCHAR"), ("company_name", "VARCHAR"), ("country_code", "VARCHAR"), ("host_count", "INTEGER"), ("identity_source", "VARCHAR"),
                 ("identity_confidence", "VARCHAR"), ("fit_score", "INTEGER"), ("urgency_score", "INTEGER"), ("contact_score", "INTEGER"), ("top_signals", "VARCHAR"),
                 ("band_uncapped", "VARCHAR"), ("cap_reasons", "VARCHAR"), ("band", "VARCHAR"), ("why", "VARCHAR"), ("decision", "VARCHAR"),
                 ("prompt_version", "VARCHAR"), ("final_band", "VARCHAR"))


def sig(name, country="DE", conf="high", hosts=3, ips=3, kev=0, cvss=None, cert=0, eol=0, legacy=0, ports=(), eo=False, sens=False, t1=False, t2=False,
        noise=0, share=0.0, blind=False):
    """Build one synthetic signals row dict from the few knobs a case needs; every derived flag follows the D9.4 definitions."""
    band = 0 if cvss is None else 3 if cvss >= 9.0 else 2 if cvss >= 7.0 else 1
    return {"company_id": hashlib.sha256(name.encode()).hexdigest()[:16], "company_name": name, "name_norm": name.lower(), "identity_source": "cert_o" if conf == "low" else "org",
            "identity_confidence": conf, "host_count": hosts, "distinct_host_ips": ips, "country_code": country, "noise_host_count": noise, "noise_host_share": share,
            "counted_host_count": 0 if blind else hosts, "host_signals_blind": blind, "is_singleton": hosts == 1,
            "in_territory": None if country is None else country == "US", "named_registrant": conf == "high", "footprint_size": min(ips, 50),
            "footprint_band": 0 if ips <= 1 else 1 if ips <= 5 else 2 if ips <= 20 else 3, "sensitive_stack": sens, "operator_shape_t1": t1, "operator_shape_t2": t2,
            "operator_name_shape": t1 or t2, "kev_exposed": kev > 0, "kev_host_count": kev, "max_cvss": cvss, "max_cvss_band": band, "cert_expired_or_soon": cert > 0,
            "cert_issue_host_count": cert, "eol_stack": eol > 0, "eol_host_count": eol, "legacy_tls": legacy > 0, "legacy_tls_host_count": legacy,
            "risky_service_exposed": bool(ports), "risky_non_ssh_exposed": any(p != 22 for p in ports), "risky_service_host_count": len(ports),
            "risky_ports": list(ports), "exposed_and_outdated": eo}


# (signals row, expected fit, urgency, contact, top_signals, band_uncapped, cap_reasons, band, why); every expected value is computed by hand from D9.7, D10 and D11
# (territory 0 points, footprint 15 per band, operator penalty 30, contact = round half up of urgency * (0.5 + 0.5 * fit / 100)).
# band "AUTO": Beta Singleton and Mu Single Honey tie on every sort key except account_id; with TEST_N = 8 the lower account_id takes the last review slot (D11.2).
# Order of the non-excluded accounts: Omicron 83, Acme 51, Delta 45, Pi Wireless 40 (the four would-be contacts), Kappa 37, Gamma Research 35, Rackhost 25 (5 hosts),
# then Beta and Mu at 25 (1 host), Iota 24, Theta 16, then scores of 3 or less. Cut: score 25, tie of 3, 2 kept, 1 to skip; Iota (24) is beyond the cut, Theta (16) below the floor.
CASES = [
    (sig("Acme Retail", "US", hosts=24, ips=24, kev=2, cvss=9.8, ports=(22,), eol=1, cert=1), 45, 70, 51, "kev_exposed,footprint_band", "contact", "operator_unverified", "review",
     f"2 hosts {KEV_PHRASE}; 24 IPs in the footprint. {CLAUSE}"),
    (sig("Beta Singleton", "US", hosts=1, ips=1, kev=1), 0, 50, 25, "kev_exposed", "review", None, "AUTO", f"1 host {KEV_PHRASE}."),
    (sig("Gamma Cdn", "FR", conf="low", hosts=2, ips=2, cert=2, blind=True), 15, 5, 3, "footprint_band,cert_expired_or_soon", "skip", None, "skip",
     f"2 IPs in the footprint; 2 hosts with expired or soon-expiring certificates. {SKIP}"),
    (sig("Rackhost Zrt", "US", hosts=5, ips=5, kev=1, t2=True), 0, 50, 25, "kev_exposed,footprint_band", "review", None, "review",
     f"1 host {KEV_PHRASE}; 5 IPs in the footprint. {OPC}"),
    (sig("Gamma Research", "US", hosts=30, ips=30, kev=3, cvss=9.8, eol=1, t1=True), 15, 60, 35, "kev_exposed,footprint_band", "review", None, "review",
     f"3 hosts {KEV_PHRASE}; 30 IPs in the footprint. {OPC}"),
    (sig("Delta Stores", "US", conf="low", hosts=1, ips=1, kev=1, cvss=9.9, ports=(3389,), eol=1, eo=True), 0, 90, 45, "kev_exposed,exposed_and_outdated", "contact",
     "low_confidence,operator_unverified,singleton", "review",
     f"1 host {KEV_PHRASE}; an exposed admin or database service (RDP 3389) on outdated software. Only one host seen. {CLAUSE}"),
    (sig("Epsilon Quiet", "DE", hosts=3, ips=3), 15, 0, 0, None, "skip", None, "skip", "No exposure signal found in the scan (3 hosts seen)."),
    (sig("Zeta Honey", "US", hosts=2, ips=2, kev=1, noise=3, share=0.6), 15, 50, 29, None, "exclude", None, "exclude", "Mostly honeypot or attacker-infrastructure hosts (3 of 5)."),
    (sig("Eta Shell", None, hosts=1, ips=1, ports=(22,)), 0, 5, 3, "risky_service_exposed", "skip", None, "skip", f"SSH (port 22) open to the internet. {SKIP}"),
    (sig("Theta Systems", "US", hosts=8, ips=8, ports=(22, 3306), legacy=1, cert=1), 30, 25, 16, "footprint_band,risky_non_ssh_exposed", "skip", None, "skip",
     f"8 IPs in the footprint; remote-admin or database services exposed (SSH 22, MySQL 3306). {SKIP}"),
    (sig("Iota Works", "DE", hosts=4, ips=4, cvss=7.5, sens=True, eol=2), 35, 35, 24, "max_cvss_band,sensitive_stack", "review", None, "skip",
     f"Worst version-matched vulnerability scores CVSS 7.5; database, medical or IoT systems in the stack. {SKIP}"),
    (sig("Kappa Bank", "US", hosts=2, ips=2, cvss=7.2, ports=(22, 3389), eol=1, eo=True), 15, 65, 37, "exposed_and_outdated,max_cvss_band", "review", None, "review",
     "An exposed admin or database service (SSH 22, RDP 3389) on outdated software; worst version-matched vulnerability scores CVSS 7.2."),
    (sig("Lambda Legacy", "DE", hosts=3, ips=1, legacy=2), 0, 5, 3, "legacy_tls", "skip", None, "skip", f"2 hosts still offering old TLS versions. {SKIP}"),
    (sig("Mu Single Honey", "US", hosts=1, ips=1, kev=1, noise=1, share=0.5), 0, 50, 25, "kev_exposed", "review", None, "AUTO", f"1 host {KEV_PHRASE}."),
    (sig("Nu Cable", "US", hosts=1, ips=1, t1=True), 0, 0, 0, None, "skip", None, "skip", "No exposure signal found in the scan (1 host seen)."),
    (sig("Xi Mobile", "DE", hosts=1, ips=1, t1=True), 0, 0, 0, None, "skip", None, "skip", "No exposure signal found in the scan (1 host seen)."),
    (sig("Omicron Works", "US", hosts=40, ips=40, kev=1, cvss=9.9, ports=(3389,), eol=1, cert=1, legacy=1, eo=True, sens=True), 65, 100, 83, "kev_exposed,footprint_band",
     "contact", "operator_unverified", "review", f"1 host {KEV_PHRASE}; 40 IPs in the footprint. {CLAUSE}"),
    (sig("Pi Wireless", "DE", hosts=24, ips=24, kev=1, eol=1, cert=1, legacy=1, t1=True), 15, 70, 40, "kev_exposed,footprint_band", "contact", "operator_name_shape,operator_unverified",
     "review", f"1 host {KEV_PHRASE}; 24 IPs in the footprint. {OPC} {CLAUSE}"),
]
TIE_NAMES = ("Beta Singleton", "Mu Single Honey")
TIE_WINNER = min(TIE_NAMES, key=lambda n: hashlib.sha256(n.encode()).hexdigest()[:16])  # the lower account_id takes the last review slot
TIE_LOSER = next(n for n in TIE_NAMES if n != TIE_WINNER)


def account_rows():
    """Return the expected accounts rows in the D9.6 item 8 sort order, as tuples in ACCOUNT_TYPES order; the AUTO tie accounts are resolved by account_id."""
    rows = []
    for s, fit, urgency, contact, top, uncapped, caps, band, why in CASES:
        name = s["company_name"]
        if band == "AUTO":
            band = "review" if name == TIE_WINNER else "skip"
            why = why if band == "review" else f"{why} {SKIP}"
        rows.append((s["company_id"], name, s["country_code"], s["host_count"], s["identity_source"], s["identity_confidence"], fit, urgency, contact, top,
                     uncapped, caps, band, why, None, None, band))
    return sorted(rows, key=lambda r: (-r[8], -r[7], -r[3], r[0]))


def build_layers(directory, mutation_sql=(), reverse=False):
    """Write synthetic signals, companies and accounts parquet files (accounts and signals with optional mutations) into a directory; return the three paths."""
    con = duckdb.connect()
    con.execute("CREATE TABLE s (" + ", ".join(f"{n} {t}" for n, t in SIGNAL_TYPES) + ")")
    con.executemany(f"INSERT INTO s VALUES ({', '.join('?' for _ in SIGNAL_TYPES)})", [tuple(c[0][n] for n, _ in SIGNAL_TYPES) for c in CASES])
    con.execute("CREATE TABLE c AS SELECT company_id FROM s")
    con.execute("CREATE TABLE a (" + ", ".join(f"{n} {t}" for n, t in ACCOUNT_TYPES) + ")")
    rows = account_rows()
    con.executemany(f"INSERT INTO a VALUES ({', '.join('?' for _ in ACCOUNT_TYPES)})", rows[::-1] if reverse else rows)
    for statement in mutation_sql:
        con.execute(statement)
    paths = [Path(directory) / name for name in ("accounts.parquet", "signals.parquet", "companies.parquet")]
    for table, path in zip(("a", "s", "c"), paths):
        con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT PARQUET)")
    return paths


def run_contract(accounts_path, signals_path, companies_path):
    """Run accounts.yml (REVIEW_N rewritten from 200 to TEST_N) against an accounts file with the cross-file paths pointed at the temporary signals and companies; return results."""
    text = CONTRACT_PATH.read_text(encoding="utf-8").replace(SIGNALS_PLACEHOLDER, Path(signals_path).as_posix())
    text = text.replace(COMPANIES_PLACEHOLDER, Path(companies_path).as_posix())
    assert text.count("SELECT 200 AS n") == 3, "the contract must hold REVIEW_N in exactly the three top-N checks"
    contract = yaml.safe_load(text.replace("SELECT 200 AS n", f"SELECT {TEST_N} AS n"))
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM {runner.source_sql(accounts_path)}")
    results = []
    for step in (runner.check_columns, runner.check_key, runner.check_row_rule, runner.check_denylist, runner.check_infra_reason, runner.check_shares, runner.check_custom):
        step(con, contract, results)
    return results


def run_extra(accounts_path, signals_path, companies_path):
    """Run the extra checks with REVIEW_N = TEST_N and return their results list."""
    return extra.run_checks(accounts_path, signals_path, companies_path, TEST_N)[0]


def failures(results):
    """Return the names of failed checks."""
    return [name for name, ok, _ in results if not ok]


def q(name, sql):
    """Return a mutation SQL statement that updates the accounts table for one company name (the sql is the SET clause)."""
    return f"UPDATE a SET {sql} WHERE company_name = '{name}'"


def to_band(name, band):
    """Return a mutation SQL statement that sets band and final_band of one company."""
    return q(name, f"band = '{band}', final_band = '{band}'")


KAPPA_HEAD = "An exposed admin or database service (SSH 22, RDP 3389) on outdated software"
LONG_WHY = f"1 host {KEV_PHRASE}; " + " ".join(["Extra words"] * 20)
# (name, SQL statements, detectors that must fail, reverse order, needle). Detector "contract" is accounts.yml, "extra" is check_accounts_extra.
# needle: a substring that must appear in a failed contract check name (pins the mutation to the intended rule); "" = any check.
MUTATIONS = [
    ("duplicated account row (join fan-out)", ["INSERT INTO a SELECT * FROM a WHERE company_name = 'Kappa Bank'"], ("contract", "extra"), False, ""),
    ("missing account", ["DELETE FROM a WHERE company_name = 'Epsilon Quiet'"], ("contract", "extra"), False, ""),
    ("account_id no longer equals company_id", [q("Kappa Bank", "account_id = 'aaaaaaaaaaaaaaaa'")], ("contract", "extra"), False, ""),
    ("fit_score of 101", [q("Acme Retail", "fit_score = 101")], ("contract", "extra"), False, ""),
    ("urgency_score of 101", [q("Omicron Works", "urgency_score = 101")], ("contract", "extra"), False, ""),
    ("contact_score above urgency_score", [q("Eta Shell", "contact_score = 6")], ("contract", "extra"), False, ""),
    ("contact_score below FLOOR times urgency", [q("Kappa Bank", "contact_score = 30")], ("contract", "extra"), False, ""),
    ("would-be contact left in contact", [q("Acme Retail", "band = 'contact', final_band = 'contact', cap_reasons = NULL")], ("contract", "extra"), False, ""),
    ("would-be contact left in contact with its cap_reasons kept", [q("Acme Retail", "band = 'contact', final_band = 'contact'")], ("contract", "extra"), False, ""),
    ("would-be contact without cap_reasons (D11: cap_reasons null only when band_uncapped is not contact)", [q("Acme Retail", "cap_reasons = NULL")], ("contract", "extra"), False,
     "cap_reasons is null exactly"),
    ("capped account without operator_unverified", [q("Pi Wireless", "cap_reasons = 'operator_name_shape'")], ("contract", "extra"), False, ""),
    ("singleton cap reason dropped from a singleton would-be contact", [q("Delta Stores", "cap_reasons = 'low_confidence,operator_unverified'")], ("contract", "extra"), False, ""),
    ("operator_unverified on a skip account", [q("Epsilon Quiet", "cap_reasons = 'operator_unverified'")], ("contract", "extra"), False, ""),
    ("operator_unverified on a review account reached by top-N", [q("Kappa Bank", "cap_reasons = 'operator_unverified'")], ("contract", "extra"), False, ""),
    ("cap_reasons on a skip account beyond the cut (band_uncapped review)", [q("Iota Works", "cap_reasons = 'operator_name_shape'")], ("contract", "extra"), False,
     "cap_reasons is null exactly"),
    ("excluded account not excluded", [q("Zeta Honey", "band = 'review', band_uncapped = 'review', final_band = 'review'")], ("contract", "extra"), False, ""),
    ("non-excluded account excluded (one honeypot row on a singleton)", [q("Mu Single Honey", "band = 'exclude', band_uncapped = 'exclude', final_band = 'exclude'")],
     ("contract", "extra"), False, ""),
    ("exclude boundary: two noise hosts at share 0.5 not excluded", ["UPDATE s SET noise_host_count = 2 WHERE company_name = 'Mu Single Honey'"], ("contract", "extra"), False, ""),
    # ---- the D11.2 cut ----
    ("wrong N: the review band holds one account too many (the tie loser promoted)", [to_band(TIE_LOSER, "review")], ("contract", "extra"), False, "N = 200"),
    ("wrong N: the review band is one account short (the tie winner dropped, as if an excluded account took the slot)", [to_band(TIE_WINNER, "skip")], ("contract", "extra"), False,
     "N = 200"),
    ("a would-be contact dropped from review (moved to skip)", [to_band("Pi Wireless", "skip")], ("contract", "extra"), False, "would-be contact is in band review"),
    ("order violation: a skip account scores higher than the weakest review account (Kappa 37 out, Iota 24 in)", [to_band("Kappa Bank", "skip"), to_band("Iota Works", "review")],
     ("contract", "extra"), False, "N = 200"),
    ("tie broken wrongly: the higher account_id takes the last slot", [to_band(TIE_WINNER, "skip"), to_band(TIE_LOSER, "review")], ("contract", "extra"), False, "N = 200"),
    ("tie broken by host_count wrongly: the 5-host account out, both 1-host accounts in", [to_band("Rackhost Zrt", "skip"), to_band(TIE_LOSER, "review")],
     ("contract", "extra"), False, "N = 200"),
    ("the floor ignored: a below-floor account (Theta, 16) promoted into review", [to_band("Theta Systems", "review")], ("contract", "extra"), False, "bands move only"),
    ("a skip account moved up from band_uncapped skip to review", [to_band("Lambda Legacy", "review")], ("contract", "extra"), False, "bands move only"),
    ("band_uncapped of a beyond-the-cut account no longer follows contact_score", [q("Iota Works", "band_uncapped = 'skip'")], ("contract", "extra"), False, "band_uncapped follows"),
    # ---- why ----
    ("empty why", [q("Kappa Bank", "why = ''")], ("contract", "extra"), False, ""),
    ("null why", [q("Kappa Bank", "why = NULL")], ("contract", "extra"), False, ""),
    ("why over 40 words", [q("Kappa Bank", f"why = '{LONG_WHY}'")], ("contract", "extra"), False, ""),
    ("why missing the D10 clause", [q("Acme Retail", f"why = '2 hosts {KEV_PHRASE}; 24 IPs in the footprint.'")], ("contract", "extra"), False, ""),
    ("D10 clause on a non-contact account", [q("Kappa Bank", f"why = why || ' {CLAUSE}'")], ("contract", "extra"), False, ""),
    ("missing operator clause on an operator-shaped review row reached by top-N (Gamma Research)", [q("Gamma Research", f"why = '3 hosts {KEV_PHRASE}; 30 IPs in the footprint.'")],
     ("contract", "extra"), False, "Name looks like a network operator"),
    ("missing operator clause on an operator-shaped would-be contact (Pi Wireless)", [q("Pi Wireless", f"why = '1 host {KEV_PHRASE}; 24 IPs in the footprint. {CLAUSE}'")],
     ("contract", "extra"), False, "Name looks like a network operator"),
    ("operator clause on a row that is not operator-shaped", [q("Kappa Bank", f"why = why || ' {OPC}'")], ("contract", "extra"), False, "Name looks like a network operator"),
    ("old skip wording 'Exposure is limited.'", [q("Eta Shell", "why = 'SSH (port 22) open to the internet. Exposure is limited.'")], ("contract", "extra"), False, ""),
    ("skip clause dropped from a skip account with urgency", [q("Eta Shell", "why = 'SSH (port 22) open to the internet.'")], ("contract", "extra"), False, "Below the review cut-off"),
    ("skip clause on a review account", [q("Kappa Bank", f"why = why || ' {SKIP}'")], ("contract", "extra"), False, "Below the review cut-off"),
    ("old KEV wording", [q("Acme Retail", f"why = '2 hosts {OLD_KEV}; 24 IPs in the footprint. {CLAUSE}'")], ("contract", "extra"), False, ""),
    ("old CVSS wording (worst vulnerability scores)", [q("Kappa Bank", f"why = '{KAPPA_HEAD}; worst vulnerability scores CVSS 7.2.'")], ("contract", "extra"), False, ""),
    ("why states a territory country as a reason", [q("Kappa Bank", f"why = '{KAPPA_HEAD}; hosts located in US.'")], ("contract", "extra"), False, ""),
    ("in_territory named in top_signals while territory carries 0 points", [q("Rackhost Zrt", "top_signals = 'kev_exposed,in_territory'")], ("contract", "extra"), False, ""),
    ("why naming a signal the company does not have, top_signals also changed",
     [q("Kappa Bank", f"top_signals = 'exposed_and_outdated,legacy_tls', why = '{KAPPA_HEAD}; 2 hosts still offering old TLS versions.'")], ("contract", "extra"), False, ""),
    ("why naming a signal the company does not have, top_signals unchanged", [q("Kappa Bank", f"why = '{KAPPA_HEAD}; 2 hosts on end-of-life software.'")], ("extra",), False, ""),
    ("why with a wrong CVSS number", [q("Iota Works", f"why = 'Worst version-matched vulnerability scores CVSS 9.8; database, medical or IoT systems in the stack. {SKIP}'")],
     ("extra",), False, ""),
    ("why with a wrong host count", [q("Acme Retail", f"why = '5 hosts {KEV_PHRASE}; 24 IPs in the footprint. {CLAUSE}'")], ("extra",), False, ""),
    ("why cap clause does not match cap_reasons",
     [q("Delta Stores", f"why = '1 host {KEV_PHRASE}; an exposed admin or database service (RDP 3389) on outdated software. {OPC} {CLAUSE}'")], ("extra",), False, ""),
    ("why states a breach", [q("Kappa Bank", f"why = '{KAPPA_HEAD}; breach detected.'")], ("contract", "extra"), False, ""),
    ("why shows a formula", [q("Kappa Bank", f"why = '{KAPPA_HEAD}; score=34.'")], ("contract", "extra"), False, ""),
    ("why shows a column name", [q("Kappa Bank", f"why = '{KAPPA_HEAD}; kev_exposed true.'")], ("contract", "extra"), False, ""),
    ("final_band differs from band", [q("Kappa Bank", "final_band = 'skip'")], ("contract", "extra"), False, ""),
    ("decision set at stage 4", [q("Acme Retail", "decision = 'contact', prompt_version = 'v1'")], ("contract", "extra"), False, ""),
    ("denylisted company name in accounts and signals", ["UPDATE a SET company_name = 'Cloudflare, Inc.' WHERE company_name = 'Epsilon Quiet'",
                                                        "UPDATE s SET company_name = 'Cloudflare, Inc.' WHERE company_name = 'Epsilon Quiet'"], ("contract", "extra"), False, ""),
    ("cap_reasons not alphabetical", [q("Pi Wireless", "cap_reasons = 'operator_unverified,operator_name_shape'")], ("contract", "extra"), False, ""),
    ("cap_reasons outside the allowed set", [q("Acme Retail", "cap_reasons = 'unknown'")], ("contract", "extra"), False, ""),
    ("fit_score from the pre-D11 territory form (35 points for a US account), consistent with contact_score", [q("Beta Singleton", "fit_score = 35, contact_score = 34")],
     ("extra",), False, ""),
    ("contact_score rounded down instead of half up", [q("Zeta Honey", "contact_score = 28")], ("extra",), False, ""),
    ("band_uncapped inconsistent with contact_score", [q("Kappa Bank", "band_uncapped = 'skip', band = 'skip', final_band = 'skip'")], ("contract", "extra"), False, ""),
    ("top_signals in the wrong order", [q("Acme Retail", "top_signals = 'footprint_band,kev_exposed'")], ("extra",), False, ""),
    ("top_signals missing on an account with urgency", [q("Kappa Bank", "top_signals = NULL")], ("contract", "extra"), False, ""),
    ("urgency 0 account with signals text", [q("Epsilon Quiet", f"why = '1 host {KEV_PHRASE}.', top_signals = 'kev_exposed'")], ("contract", "extra"), False, ""),
    ("contact_score typed BIGINT", ["ALTER TABLE a ALTER contact_score TYPE BIGINT"], ("contract",), False, ""),
    ("extra raw column added", ["ALTER TABLE a ADD COLUMN banner VARCHAR"], ("contract",), False, ""),
    ("carried host_count differs from signals", [q("Kappa Bank", "host_count = 3")], ("contract",), False, ""),
    ("file not sorted by contact_score", [], ("extra",), True, ""),
]


class UnitTests(unittest.TestCase):
    """Small pure-function cases and the hand-computed reference."""

    def test_round_half_up(self):
        """Halves round up: 2.5 is 3, 37.5 is 38, 2.4 is 2 and 0 is 0."""
        self.assertEqual([extra.round_half_up(Fraction(v)) for v in ("5/2", "75/2", "12/5", "0")], [3, 38, 2, 0])

    def test_reference_matches_every_hand_computed_case(self):
        """The independent reference reproduces the hand-computed scores, caps, top_signals and final bands (top-N, N = TEST_N) of all 18 synthetic accounts."""
        refs, stats = extra.reference_all([c[0] for c in CASES], TEST_N)
        for s, fit, urgency, contact, top, uncapped, caps, band, _why in CASES:
            name = s["company_name"]
            want = ("review" if name == TIE_WINNER else "skip") if band == "AUTO" else band
            with self.subTest(name=name):
                ref = refs[s["company_id"]]
                self.assertEqual((ref["fit_score"], ref["urgency_score"], ref["contact_score"], ref["band_uncapped"], ref["cap_reasons"], ref["band"]),
                                 (fit, urgency, contact, uncapped, caps, want))
                self.assertEqual(ref["top_signals"], top.split(",") if top else None)
        self.assertEqual((stats["would_be_contacts"], stats["top_n_only"], stats["cut_score"], stats["tie_size"], stats["tie_kept"], stats["tie_to_skip"], stats["accounts_above_cut"]),
                         (4, 4, 25, 3, 2, 1, 6))

    def test_tie_winner_is_the_lower_account_id(self):
        """Beta Singleton and Mu Single Honey differ only in account_id; the lower id is kept (hand rule: account_id ascending)."""
        ids = {c[0]["company_name"]: c[0]["company_id"] for c in CASES}
        self.assertLess(ids[TIE_WINNER], ids[TIE_LOSER])

    def test_top_n_cases(self):
        """N smaller than the would-be contacts keeps every would-be contact; the floor stops a large N; excluded accounts take no slot."""
        sigs = [c[0] for c in CASES]
        refs, stats = extra.reference_all(sigs, 2)
        self.assertEqual((sum(1 for r in refs.values() if r["band"] == "review"), stats["top_n_only"], stats["cut_score"]), (4, 0, None))
        refs, stats = extra.reference_all(sigs, 1000)
        self.assertEqual((sum(1 for r in refs.values() if r["band"] == "review"), stats["top_n_only"], stats["cut_score"]), (10, 6, 24))  # 4 would-be + 6 with contact_score >= 20
        by_name = {c[0]["company_name"]: refs[c[0]["company_id"]] for c in CASES}
        self.assertEqual(by_name["Zeta Honey"]["band"], "exclude")

    def test_territory_carries_no_points(self):
        """A US account has the same fit as a non-US account with the same footprint (D11.5, territory 0)."""
        self.assertEqual(extra.reference_account(sig("US", "US", ips=24))["fit_score"], extra.reference_account(sig("DE", "DE", ips=24))["fit_score"])

    def test_pre_d10_penalty_differs_for_t2_only(self):
        """A T2-only name keeps its fit under the T1-only form and loses 30 under the union (D10)."""
        s = sig("Rackhost X", "US", hosts=30, ips=30, kev=1, t2=True)
        self.assertEqual((extra.reference_account(s, union=False)["fit_score"], extra.reference_account(s, union=True)["fit_score"]), (45, 15))

    def test_kev_and_cvss_never_added(self):
        """KEV 50 and CVSS band 3 together give 50, the larger single contribution, not 90."""
        s = sig("X", kev=1, cvss=9.9)
        self.assertEqual(extra.reference_account(s)["urgency_score"], 50)

    def test_tie_preference_vulnerability_over_hygiene_over_fit(self):
        """Equal points rank vulnerability, then exposure, then hygiene, then fit (CVSS band 1 = 10 = EOL; SSH 5 = cert 5)."""
        s = sig("Y", "DE", ips=1, cvss=3.0, eol=1)
        self.assertEqual(extra.reference_account(s)["top_signals"], ["max_cvss_band", "eol_stack"])
        s = sig("Z", "DE", ips=1, ports=(22,), cert=1)
        self.assertEqual(extra.reference_account(s)["top_signals"], ["risky_service_exposed", "cert_expired_or_soon"])

    def test_no_signal_account_has_no_top_signals_even_with_fit(self):
        """Urgency 0 gives top_signals none even when fit is above 0."""
        self.assertIsNone(extra.reference_account(sig("W", "US", ips=30))["top_signals"])

    def test_quantile_linear(self):
        """Linear quantile of 0 to 4: p50 is 2 and p25 is 1."""
        self.assertEqual((extra.quantile([0, 1, 2, 3, 4], 0.5), extra.quantile([0, 1, 2, 3, 4], 0.25)), (2, 1))

    def test_parse_why_flags_a_false_phrase(self):
        """A phrase for a signal the company lacks is reported; a true one is not; the old KEV wording is not a known phrase."""
        s = sig("V", "US", kev=1)
        _named, problems, _rest = extra.parse_why("2 hosts still offering old TLS versions", s, {})
        self.assertTrue(problems)
        _named, problems, _rest = extra.parse_why(f"1 host {KEV_PHRASE}", s, {})
        self.assertFalse(problems)
        named, _problems, rest = extra.parse_why(f"1 host {OLD_KEV}", s, {})
        self.assertEqual(named, [])
        self.assertTrue(rest.strip())


class CleanLayerTests(unittest.TestCase):
    """A correct synthetic layer must pass both detectors."""

    def test_clean_layer_passes_contract_and_extra(self):
        """Contract and extra checks both pass on the hand-built layer."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_layers(tmp)
            self.assertEqual(failures(run_contract(*paths)), [])
            self.assertEqual(failures(run_extra(*paths)), [])

    def test_clean_whys_respect_the_limit_and_names_are_not_denylisted(self):
        """The hand-written why strings are at most 40 words and no synthetic name is denylisted (guards the test itself)."""
        matcher = extra.load_matcher()
        rules = matcher.load_rules()
        for c in CASES:
            self.assertLessEqual(len(c[8].split()), 40, c[0]["company_name"])
            self.assertIsNone(matcher.match_name(c[0]["company_name"], "org", rules), c[0]["company_name"])
        self.assertIsNotNone(matcher.match_name("Cloudflare, Inc.", "org", rules))


class MutationTests(unittest.TestCase):
    """Every injected fault must make the named detector fail."""

    def test_each_mutation_is_caught(self):
        """For each fault the detectors named in MUTATIONS report at least one failed check (the contract one containing the needle when given)."""
        self.assertGreaterEqual(len(MUTATIONS), 10)
        for name, statements, detectors, reverse, needle in MUTATIONS:
            with self.subTest(fault=name), tempfile.TemporaryDirectory() as tmp:
                paths = build_layers(tmp, statements, reverse)
                found = {"contract": failures(run_contract(*paths)), "extra": failures(run_extra(*paths))}
                for detector in detectors:
                    self.assertTrue(found[detector], f"{detector} did not catch: {name}")
                if needle and "contract" in detectors:
                    self.assertTrue(any(needle in n for n in found["contract"]), f"contract caught {name} but not by the rule containing {needle!r}: {found['contract']}")


if __name__ == "__main__":
    unittest.main()
