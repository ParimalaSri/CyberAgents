"""Unit tests for pipeline/4_score.py on a tiny synthetic signals parquet (stdlib unittest, DuckDB, no pandas)."""
import importlib.util
import itertools
import tempfile
import unittest
from pathlib import Path

import duckdb

STAGE_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "4_score.py"
SPEC = importlib.util.spec_from_file_location("score_stage", STAGE_PATH)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)

SIGNAL_DDL = (
    "company_id VARCHAR, company_name VARCHAR, name_norm VARCHAR, identity_source VARCHAR, identity_confidence VARCHAR, host_count INTEGER, "
    "distinct_host_ips INTEGER, country_code VARCHAR, noise_host_count INTEGER, noise_host_share DOUBLE, counted_host_count INTEGER, "
    "host_signals_blind BOOLEAN, is_singleton BOOLEAN, in_territory BOOLEAN, named_registrant BOOLEAN, footprint_size INTEGER, footprint_band SMALLINT, "
    "sensitive_stack BOOLEAN, operator_shape_t1 BOOLEAN, operator_shape_t2 BOOLEAN, operator_name_shape BOOLEAN, kev_exposed BOOLEAN, "
    "kev_host_count INTEGER, max_cvss DOUBLE, max_cvss_band SMALLINT, cert_expired_or_soon BOOLEAN, cert_issue_host_count INTEGER, eol_stack BOOLEAN, "
    "eol_host_count INTEGER, legacy_tls BOOLEAN, legacy_tls_host_count INTEGER, risky_service_exposed BOOLEAN, risky_non_ssh_exposed BOOLEAN, "
    "risky_service_host_count INTEGER, risky_ports INTEGER[], exposed_and_outdated BOOLEAN"
)
DEFAULTS = {
    "company_name": "Acme", "name_norm": "acme", "identity_source": "org", "identity_confidence": "high", "host_count": 5, "distinct_host_ips": 5,
    "country_code": "DE", "noise_host_count": 0, "noise_host_share": 0.0, "counted_host_count": 5, "host_signals_blind": False, "is_singleton": False,
    "in_territory": False, "named_registrant": True, "footprint_size": 5, "footprint_band": 0, "sensitive_stack": False, "operator_shape_t1": False,
    "operator_shape_t2": False, "operator_name_shape": False, "kev_exposed": False, "kev_host_count": 0, "max_cvss": None, "max_cvss_band": 0,
    "cert_expired_or_soon": False, "cert_issue_host_count": 0, "eol_stack": False, "eol_host_count": 0, "legacy_tls": False, "legacy_tls_host_count": 0,
    "risky_service_exposed": False, "risky_non_ssh_exposed": False, "risky_service_host_count": 0, "risky_ports": [], "exposed_and_outdated": False,
}
COLUMNS = tuple(DEFAULTS)


def sig(company_id, **over):
    """Return a signals row dict with defaults and overrides; operator_name_shape follows the two shape flags unless given."""
    row = dict(DEFAULTS, company_id=company_id)
    row.update(over)
    if "max_cvss" not in over:
        row["max_cvss"] = {0: None, 1: 4.3, 2: 7.5, 3: 9.8}[row["max_cvss_band"]]
    if "operator_name_shape" not in over:
        row["operator_name_shape"] = row["operator_shape_t1"] or row["operator_shape_t2"]
    row["is_singleton"] = row["host_count"] == 1 if "is_singleton" not in over else row["is_singleton"]
    return row


def run_scores(rows, **kwargs):
    """Write rows as a signals parquet, run the stage, return {company_id: accounts row dict} and the ordered account ids."""
    with tempfile.TemporaryDirectory() as tmp:
        con = duckdb.connect()
        con.execute(f"CREATE TABLE s ({SIGNAL_DDL})")
        for row in rows:
            con.execute(f"INSERT INTO s VALUES ({','.join('?' * 36)})", [row["company_id"]] + [row[c] for c in COLUMNS])
        src = Path(tmp, "signals.parquet")
        con.execute(f"COPY s TO '{src.as_posix()}' (FORMAT PARQUET)")
        out = Path(tmp, "out", "accounts.parquet")
        counts = STAGE.run_stage(con, src, out, **kwargs)
        cur = con.execute(f"SELECT * FROM read_parquet('{out.as_posix()}')")
        names = [d[0] for d in cur.description]
        accounts = [dict(zip(names, r)) for r in cur.fetchall()]
        types = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{out.as_posix()}')").fetchall()
        return {a["account_id"]: a for a in accounts}, [a["account_id"] for a in accounts], counts, types


def score_one(**over):
    """Score one company named x and return its accounts row."""
    accounts, _, _, _ = run_scores([sig("x", **over)])
    return accounts["x"]


class PointRuleTests(unittest.TestCase):
    """Each point rule of D9.7 firing and not firing."""

    def test_urgency_baseline_is_zero(self):
        """A company with no urgency signal has urgency 0 and contact 0."""
        row = score_one()
        self.assertEqual((row["urgency_score"], row["contact_score"]), (0, 0))

    def test_vulnerability_larger_of_not_sum(self):
        """KEV 50 versus CVSS band 40/25/10: the larger counts, never the sum."""
        self.assertEqual(score_one(kev_exposed=True)["urgency_score"], 50)
        self.assertEqual(score_one(max_cvss_band=3)["urgency_score"], 40)
        self.assertEqual(score_one(max_cvss_band=2)["urgency_score"], 25)
        self.assertEqual(score_one(max_cvss_band=1)["urgency_score"], 10)
        self.assertEqual(score_one(kev_exposed=True, max_cvss_band=3)["urgency_score"], 50)
        self.assertEqual(score_one(kev_exposed=False, max_cvss_band=3)["urgency_score"], 40)

    def test_exposure_highest_applicable(self):
        """Exposure is exposed-and-outdated 30, else non-SSH 15, else SSH only 5; they are not added."""
        self.assertEqual(score_one(risky_service_exposed=True)["urgency_score"], 5)
        self.assertEqual(score_one(risky_service_exposed=True, risky_non_ssh_exposed=True)["urgency_score"], 15)
        self.assertEqual(score_one(risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True)["urgency_score"], 30)

    def test_hygiene_is_summed(self):
        """EOL 10, certificate 5 and legacy TLS 5 are added."""
        self.assertEqual(score_one(eol_stack=True)["urgency_score"], 10)
        self.assertEqual(score_one(cert_expired_or_soon=True)["urgency_score"], 5)
        self.assertEqual(score_one(legacy_tls=True)["urgency_score"], 5)
        self.assertEqual(score_one(eol_stack=True, cert_expired_or_soon=True, legacy_tls=True)["urgency_score"], 20)

    def test_urgency_clipped_at_100(self):
        """The maximum is exactly 100 (50 + 30 + 20), and the clip holds."""
        row = score_one(kev_exposed=True, risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, eol_stack=True,
                        cert_expired_or_soon=True, legacy_tls=True)
        self.assertEqual(row["urgency_score"], 100)

    def test_fit_rules(self):
        """Territory 35, footprint band x 15, sensitive 20, null territory counts 0."""
        self.assertEqual(score_one()["fit_score"], 0)
        self.assertEqual(score_one(in_territory=True)["fit_score"], 35)
        self.assertEqual(score_one(in_territory=None)["fit_score"], 0)
        self.assertEqual([score_one(footprint_band=b)["fit_score"] for b in range(4)], [0, 15, 30, 45])
        self.assertEqual(score_one(sensitive_stack=True)["fit_score"], 20)
        self.assertEqual(score_one(in_territory=True, footprint_band=3, sensitive_stack=True)["fit_score"], 100)

    def test_operator_penalty_t1_only(self):
        """The fit penalty of 30 applies to operator_shape_t1 only; T2 alone does not reduce fit; clipped at 0."""
        self.assertEqual(score_one(in_territory=True, footprint_band=3, operator_shape_t1=True)["fit_score"], 50)
        self.assertEqual(score_one(in_territory=True, footprint_band=3, operator_shape_t2=True)["fit_score"], 80)
        self.assertEqual(score_one(footprint_band=1, operator_shape_t1=True)["fit_score"], 0)


class ContactScoreTests(unittest.TestCase):
    """Form (b) arithmetic and its invariant."""

    def test_formula_and_rounding(self):
        """contact = round(urgency * (0.5 + 0.5 * fit / 100)), half rounded up, exact in integers."""
        row = score_one(kev_exposed=True, in_territory=True)  # urgency 50, fit 35 -> 50 * 0.675 = 33.75
        self.assertEqual((row["urgency_score"], row["fit_score"], row["contact_score"]), (50, 35, 34))
        row = score_one(max_cvss_band=1, footprint_band=1)  # urgency 10, fit 15 -> 10 * 0.575 = 5.75
        self.assertEqual(row["contact_score"], 6)
        row = score_one(eol_stack=True, cert_expired_or_soon=True, footprint_band=1, in_territory=False)  # urgency 15, fit 15 -> 15 * 0.575 = 8.625
        self.assertEqual(row["contact_score"], 9)
        row = score_one(max_cvss_band=1, sensitive_stack=True, in_territory=False, footprint_band=0)  # 10 * 0.6 = 6.0
        self.assertEqual(row["contact_score"], 6)
        row = score_one(max_cvss_band=2, footprint_band=0, sensitive_stack=True, operator_shape_t1=False, in_territory=False)  # 25 * 0.6 = 15.0
        self.assertEqual(row["contact_score"], 15)
        row = score_one(max_cvss_band=1, in_territory=True, sensitive_stack=True, footprint_band=0)  # fit 55: 10 * 0.775 = 7.75
        self.assertEqual(row["contact_score"], 8)

    def test_half_goes_up(self):
        """Values at and near .5 round half up (25 * 0.5 = 12.5 gives 13)."""
        row = score_one(risky_service_exposed=True, sensitive_stack=True)  # urgency 5, fit 20 -> 5 * 0.6 = 3.0
        self.assertEqual(row["contact_score"], 3)
        row = score_one(legacy_tls=True, in_territory=True, sensitive_stack=True, footprint_band=0)  # urgency 5, fit 55 -> 5 * 0.775 = 3.875
        self.assertEqual(row["contact_score"], 4)
        row = score_one(eol_stack=True, footprint_band=1)  # urgency 10, fit 15 -> 5.75
        self.assertEqual(row["contact_score"], 6)
        row = score_one(max_cvss_band=2, in_territory=False, footprint_band=0, sensitive_stack=False)  # fit 0: 25 * 0.5 = 12.5 -> 13
        self.assertEqual(row["contact_score"], 13)

    def test_invariant_at_extremes(self):
        """FLOOR * urgency <= contact <= urgency at fit 0 and 100 and urgency 0 and 100."""
        full = dict(kev_exposed=True, risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, eol_stack=True,
                    cert_expired_or_soon=True, legacy_tls=True)
        rich = dict(in_territory=True, footprint_band=3, sensitive_stack=True)
        cases = {"u100 f100": (full, rich, 100, 100, 100), "u100 f0": (full, {}, 100, 0, 50), "u0 f100": ({}, rich, 0, 100, 0), "u0 f0": ({}, {}, 0, 0, 0)}
        for label, (u_over, f_over, urgency, fit, contact) in cases.items():
            row = score_one(**u_over, **f_over)
            self.assertEqual((row["urgency_score"], row["fit_score"], row["contact_score"]), (urgency, fit, contact), label)

    def test_invariant_holds_for_all_combinations(self):
        """Over every combination of urgency flags and fit flags the invariant FLOOR * urgency <= contact <= urgency holds."""
        rows = []
        flags = ("kev_exposed", "eol_stack", "cert_expired_or_soon", "legacy_tls", "risky_service_exposed", "sensitive_stack", "in_territory", "operator_shape_t1")
        for i, combo in enumerate(itertools.product((False, True), repeat=len(flags))):
            over = dict(zip(flags, combo), footprint_band=i % 4)
            rows.append(sig(f"r{i}", **over))
        accounts, _, _, _ = run_scores(rows)
        for a in accounts.values():
            self.assertTrue(a["urgency_score"] * STAGE.FLOOR_PCT <= a["contact_score"] * 100 + 50, a)
            self.assertLessEqual(a["contact_score"], a["urgency_score"])
            for k in ("fit_score", "urgency_score", "contact_score"):
                self.assertTrue(0 <= a[k] <= 100)


class BandTests(unittest.TestCase):
    """Band order, thresholds, caps and the exclude rule."""

    def test_thresholds_edges(self):
        """contact at exactly X, review at exactly Y, skip below Y (uncapped company)."""
        base = dict(host_count=5)
        # urgency 40 (cvss 3), fit 0: contact 20; add territory etc. to move contact
        accounts, _, _, _ = run_scores([sig("a", max_cvss_band=3, **base), sig("b", max_cvss_band=2, **base), sig("c", max_cvss_band=1, **base)])
        self.assertEqual((accounts["a"]["contact_score"], accounts["a"]["band"]), (20, "review"))
        self.assertEqual((accounts["b"]["contact_score"], accounts["b"]["band"]), (13, "skip"))
        self.assertEqual((accounts["c"]["contact_score"], accounts["c"]["band"]), (5, "skip"))
        accounts, _, _, _ = run_scores([sig("a", max_cvss_band=3, **base)], contact=20, review=10)
        self.assertEqual(accounts["a"]["band"], "contact")
        accounts, _, _, _ = run_scores([sig("a", max_cvss_band=3, **base)], contact=21, review=20)
        self.assertEqual(accounts["a"]["band"], "review")
        accounts, _, _, _ = run_scores([sig("a", max_cvss_band=3, **base)], contact=40, review=21)
        self.assertEqual(accounts["a"]["band"], "skip")

    def test_threshold_options_default_and_override(self):
        """The command-line defaults are the provisional X = 40, Y = 20 and the parser accepts overrides."""
        self.assertEqual((STAGE.THRESHOLD_CONTACT, STAGE.THRESHOLD_REVIEW), (40, 20))
        import sys
        old = sys.argv
        try:
            sys.argv = ["4_score.py", "--contact", "45", "--review", "25"]
            captured = {}
            original = (STAGE.run_stage, STAGE.print_report)
            STAGE.run_stage = lambda con, i, o, c, r: captured.update(c=c, r=r) or {"signals_rows": 0, "accounts_rows": 0}
            STAGE.print_report = lambda *a, **k: None
            STAGE.main()
            self.assertEqual((captured["c"], captured["r"]), (45, 25))
        finally:
            STAGE.run_stage, STAGE.print_report = original
            sys.argv = old
        with self.assertRaises(AssertionError):
            run_scores([sig("a")], contact=20, review=20)

    def strong(self, **over):
        """Return a company that reaches contact_score 50 uncapped: urgency 100 and fit 0 (contact 50)."""
        return dict(kev_exposed=True, risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, eol_stack=True,
                    cert_expired_or_soon=True, legacy_tls=True, **over)

    def test_each_cap_alone(self):
        """Singleton, low confidence and operator shape each move a would-be contact to review with exactly their reason."""
        rows = [sig("clean", **self.strong()),
                sig("single", host_count=1, **self.strong()),
                sig("low", identity_confidence="low", identity_source="cert_o", **self.strong()),
                sig("oper", operator_shape_t2=True, **self.strong())]
        accounts, _, _, _ = run_scores(rows)
        self.assertEqual((accounts["clean"]["band"], accounts["clean"]["cap_reasons"], accounts["clean"]["band_uncapped"]), ("contact", None, "contact"))
        for cid, reason in (("single", "singleton"), ("low", "low_confidence"), ("oper", "operator_name_shape")):
            a = accounts[cid]
            self.assertEqual((a["band_uncapped"], a["band"], a["cap_reasons"]), ("contact", "review", reason), cid)
            self.assertEqual(a["final_band"], "review")

    def test_caps_together_sorted(self):
        """All reasons that apply are listed, sorted and comma separated."""
        a = score_one(host_count=1, identity_confidence="low", identity_source="cert_o", operator_shape_t1=True, **self.strong())
        self.assertEqual(a["cap_reasons"], "low_confidence,operator_name_shape,singleton")
        a = score_one(host_count=1, operator_shape_t2=True, **self.strong())
        self.assertEqual(a["cap_reasons"], "operator_name_shape,singleton")

    def test_caps_only_contact_to_review_never_to_skip(self):
        """A capped company below the contact threshold is not touched by caps: review stays review (no reason), skip stays skip."""
        accounts, _, _, _ = run_scores([sig("r", host_count=1, max_cvss_band=3), sig("s", host_count=1, max_cvss_band=1)])
        self.assertEqual((accounts["r"]["band"], accounts["r"]["cap_reasons"]), ("review", None))
        self.assertEqual((accounts["s"]["band"], accounts["s"]["cap_reasons"], accounts["s"]["band_uncapped"]), ("skip", None, "skip"))

    def test_no_capped_company_in_contact(self):
        """Over a grid of cap flags and high urgency, no singleton, low-confidence or operator-shaped company has band contact."""
        rows = []
        for i, (single, low, op) in enumerate(itertools.product((False, True), repeat=3)):
            over = dict(host_count=1 if single else 5, operator_shape_t2=op, **self.strong())
            if low:
                over.update(identity_confidence="low", identity_source="cert_o")
            rows.append(sig(f"g{i}", **over))
        accounts, _, _, _ = run_scores(rows)
        for a in accounts.values():
            capped = a["host_count"] == 1 or a["identity_confidence"] == "low"
            if a["band"] == "contact":
                self.assertFalse(capped)

    def test_exclude_rule_edges(self):
        """Exclude needs noise_host_count >= 2 AND noise_host_share >= 0.5: count 1 vs 2 and share 0.49 vs 0.5."""
        cases = {"c1s60": (1, 0.6, "skip"), "c2s49": (2, 0.49, "skip"), "c2s50": (2, 0.5, "exclude"), "c3s60": (3, 0.6, "exclude"), "c1s50": (1, 0.5, "skip")}
        rows = [sig(k, noise_host_count=n, noise_host_share=s) for k, (n, s, _) in cases.items()]
        accounts, _, _, _ = run_scores(rows)
        for k, (_, _, band) in cases.items():
            self.assertEqual(accounts[k]["band"], band, k)

    def test_exclude_beats_everything(self):
        """An excluded account keeps band exclude even with top urgency, has no cap reasons, and band_uncapped is exclude."""
        a = score_one(noise_host_count=3, noise_host_share=0.6, host_count=2, **self.strong())
        self.assertEqual((a["band"], a["band_uncapped"], a["cap_reasons"], a["final_band"]), ("exclude", "exclude", None, "exclude"))


class WhyTests(unittest.TestCase):
    """Pinned phrases, the length limit and no empty why."""

    def test_pinned_phrases(self):
        """Every signal phrase, each cap clause, the no-signal text and the exclude text are pinned."""
        cases = [
            (dict(kev_exposed=True, kev_host_count=1), "1 host with a vulnerability on the CISA known-exploited list."),
            (dict(kev_exposed=True, kev_host_count=3), "3 hosts with a vulnerability on the CISA known-exploited list."),
            (dict(max_cvss_band=3, max_cvss=9.8), "Worst vulnerability scores CVSS 9.8."),
            (dict(max_cvss_band=2, max_cvss=7.5), "Worst vulnerability scores CVSS 7.5."),
            (dict(max_cvss_band=1, max_cvss=4.3), "Worst vulnerability scores CVSS 4.3."),
            (dict(risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, risky_ports=[22, 3389, 3306]),
             "An exposed admin or database service (SSH 22, RDP 3389) on outdated software."),
            (dict(risky_service_exposed=True, risky_non_ssh_exposed=True, risky_ports=[22, 3389]), "Remote-admin or database services exposed (RDP 3389)."),
            (dict(risky_service_exposed=True, risky_ports=[22]), "SSH (port 22) open to the internet."),
            (dict(eol_stack=True, eol_host_count=2), "2 hosts on end-of-life software."),
            (dict(cert_expired_or_soon=True, cert_issue_host_count=1), "1 host with expired or soon-expiring certificates."),
            (dict(legacy_tls=True, legacy_tls_host_count=4), "4 hosts still offering old TLS versions."),
        ]
        for over, text in cases:
            why = score_one(**over)["why"]
            self.assertTrue(why.startswith(text), (over, why))
        top = score_one(max_cvss_band=1, max_cvss=3.0, distinct_host_ips=9, footprint_band=2, in_territory=True, country_code="US")
        self.assertTrue(top["why"].startswith("Hosts located in US; 9 IPs in the footprint."), top["why"])
        sens = score_one(max_cvss_band=1, max_cvss=3.0, sensitive_stack=True, in_territory=True, country_code="US")
        self.assertTrue(sens["why"].startswith("Hosts located in US; database, medical or IoT systems in the stack."), sens["why"])

    def test_cap_clauses_and_skip_texts(self):
        """Cap clauses, the no-signal sentence, the limited-exposure sentence for skip and the exclude sentence."""
        strong = dict(kev_exposed=True, kev_host_count=1, eol_stack=True, eol_host_count=1, risky_service_exposed=True, risky_non_ssh_exposed=True,
                      exposed_and_outdated=True, risky_ports=[3389], cert_expired_or_soon=True, cert_issue_host_count=1, legacy_tls=True, legacy_tls_host_count=1)
        self.assertTrue(score_one(host_count=1, **strong)["why"].endswith("Only one host seen."))
        self.assertTrue(score_one(identity_confidence="low", identity_source="cert_o", **strong)["why"].endswith("Named only by a TLS certificate."))
        self.assertTrue(score_one(operator_shape_t1=True, **strong)["why"].endswith("Name looks like a network operator."))
        self.assertEqual(score_one()["why"], "No exposure signal found in the scan (5 hosts seen).")
        self.assertEqual(score_one(host_count=1)["why"], "No exposure signal found in the scan (1 host seen).")
        self.assertTrue(score_one(max_cvss_band=1, max_cvss=3.0)["why"].endswith("Exposure is limited."))
        self.assertEqual(score_one(noise_host_count=3, noise_host_share=0.6, host_count=2)["why"],
                         "Mostly honeypot or attacker-infrastructure hosts (3 of 5).")

    def test_top_two_by_points_with_tie_order(self):
        """Top two signals by points; ties go vulnerability, exposure, hygiene, fit; top_signals lists exactly the signals used."""
        a = score_one(kev_exposed=True, kev_host_count=1, exposed_and_outdated=True, risky_service_exposed=True, risky_non_ssh_exposed=True,
                      risky_ports=[3389], eol_stack=True, eol_host_count=1)
        self.assertEqual(a["top_signals"], "kev_exposed,exposed_and_outdated")
        a = score_one(cert_expired_or_soon=True, cert_issue_host_count=1, legacy_tls=True, legacy_tls_host_count=1, eol_stack=True, eol_host_count=1)
        self.assertEqual(a["top_signals"], "eol_stack,cert_expired_or_soon")
        a = score_one(max_cvss_band=1, max_cvss=3.0, footprint_band=1, distinct_host_ips=3)  # CVSS 10 vs footprint 15
        self.assertEqual(a["top_signals"], "footprint_band,max_cvss_band")
        self.assertIsNone(score_one()["top_signals"])
        self.assertIsNone(score_one(noise_host_count=3, noise_host_share=0.6)["top_signals"])

    def test_length_limit_and_never_empty(self):
        """Over every combination of signals, caps and bands the why is non-empty, at most 40 words and free of column names, equals signs and breach words."""
        flags = ("kev_exposed", "exposed_and_outdated", "eol_stack", "cert_expired_or_soon", "legacy_tls", "sensitive_stack", "in_territory")
        rows = []
        for i, combo in enumerate(itertools.product((False, True), repeat=len(flags))):
            over = dict(zip(flags, combo), footprint_band=3, distinct_host_ips=50, kev_host_count=120, eol_host_count=120, cert_issue_host_count=120,
                        legacy_tls_host_count=120, country_code="US", max_cvss=10.0, max_cvss_band=3, risky_ports=[22, 2375, 3389], host_count=1 + (i % 2) * 5,
                        risky_service_exposed=combo[1], risky_non_ssh_exposed=combo[1], operator_shape_t1=(i % 3 == 0))
            rows.append(sig(f"w{i}", **over))
        accounts, _, _, _ = run_scores(rows)
        for a in accounts.values():
            why = a["why"]
            self.assertTrue(why and why.strip() == why, a)
            self.assertLessEqual(len(why.split()), 40, why)
            self.assertNotIn("_", why)
            self.assertNotIn("=", why)
            for word in ("breach", "compromised", "hacked"):
                self.assertNotIn(word, why.lower())
        worst = max(len(a["why"].split()) for a in accounts.values())
        self.assertLessEqual(worst, 40)


class OutputShapeTests(unittest.TestCase):
    """Row equality, the 17 columns with their types, ordering and the stage 4 nulls."""

    def test_rows_equal_columns_types_order_nulls(self):
        """Row count equals the signals, the 17 columns have the D9.6 types, sort is contact desc, and decision and prompt_version are null."""
        rows = [sig("a", max_cvss_band=3), sig("b", kev_exposed=True, in_territory=True), sig("c"), sig("d", noise_host_count=2, noise_host_share=0.5)]
        accounts, order, counts, types = run_scores(rows)
        self.assertEqual(counts, {"signals_rows": 4, "accounts_rows": 4})
        self.assertEqual(len(accounts), 4)
        self.assertEqual([(t[0], t[1]) for t in types], list(STAGE.OUTPUT_COLUMNS))
        self.assertEqual(len(types), 17)
        self.assertEqual(order[0], "b")
        for a in accounts.values():
            self.assertIsNone(a["decision"])
            self.assertIsNone(a["prompt_version"])
            self.assertEqual(a["final_band"], a["band"])
            self.assertIn(a["band"], STAGE.BANDS)
            self.assertIn(a["band_uncapped"], STAGE.BANDS)

    def test_account_id_is_company_id(self):
        """account_id carries the company_id value unchanged."""
        accounts, _, _, _ = run_scores([sig("abc123")])
        self.assertIn("abc123", accounts)

    def test_deterministic_rerun(self):
        """Two runs on the same signals give identical rows."""
        rows = [sig("a", max_cvss_band=3), sig("b", kev_exposed=True), sig("c")]
        self.assertEqual(run_scores(rows)[0], run_scores(rows)[0])

    def test_form_a_behind_constant(self):
        """Candidate (a) is implemented behind CONTACT_FORM and computes round(W_F * fit + (1 - W_F) * urgency)."""
        original = STAGE.CONTACT_FORM
        try:
            STAGE.CONTACT_FORM = "a"
            row = score_one(kev_exposed=True, in_territory=True)  # (30 * 35 + 70 * 50 + 50) // 100 = 46
            self.assertEqual(row["contact_score"], 46)
            row = score_one(in_territory=True)  # urgency 0, fit 35: form (a) lets fit alone lift the score (the reason (b) is recommended)
            self.assertEqual(row["contact_score"], (STAGE.W_F_PCT * 35 + 50) // 100)
        finally:
            STAGE.CONTACT_FORM = original

    def test_full_flag_defaults_do_not_overwrite_sample(self):
        """--full has its own default paths so it cannot overwrite the sample output."""
        self.assertNotEqual(STAGE.FULL_OUTPUT_PATH, STAGE.OUTPUT_PATH)
        self.assertNotEqual(STAGE.FULL_INPUT_PATH, STAGE.INPUT_PATH)


if __name__ == "__main__":
    unittest.main()
