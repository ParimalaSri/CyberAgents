"""Unit tests for pipeline/4_score.py on a tiny synthetic signals parquet (stdlib unittest, DuckDB, no pandas)."""
import importlib.util
import itertools
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import duckdb

STAGE_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "4_score.py"
SPEC = importlib.util.spec_from_file_location("score_stage", STAGE_PATH)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)
GUARD_SUPPORT_SPEC = importlib.util.spec_from_file_location("guard_test_support", Path(__file__).resolve().parent / "guard_test_support.py")
GUARD_SUPPORT = importlib.util.module_from_spec(GUARD_SUPPORT_SPEC)
GUARD_SUPPORT_SPEC.loader.exec_module(GUARD_SUPPORT)

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
LAST_CON = []  # the DuckDB connection of the latest run_scores call, so a test can read the scored table and call report sections


class QuietReport(STAGE.Report):
    """A Report that collects lines without printing them, so the test run stays quiet."""

    def add(self, text=""):
        """Keep one line without printing it."""
        self.lines.append(text)


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
        LAST_CON[:] = [con]
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
        """D11.5: territory points are 0 (neutral), footprint band x 15, sensitive 20; the maximum fit is 65 until the territory list exists."""
        self.assertEqual(STAGE.IN_TERRITORY_POINTS, 0)
        self.assertEqual(score_one()["fit_score"], 0)
        self.assertEqual(score_one(in_territory=True)["fit_score"], 0)
        self.assertEqual(score_one(in_territory=None)["fit_score"], 0)
        self.assertEqual([score_one(footprint_band=b)["fit_score"] for b in range(4)], [0, 15, 30, 45])
        self.assertEqual(score_one(sensitive_stack=True)["fit_score"], 20)
        self.assertEqual(score_one(in_territory=True, footprint_band=3, sensitive_stack=True)["fit_score"], 65)

    def test_territory_is_neutral_for_scores_and_why(self):
        """In and out of territory give the same fit, contact, top_signals and why, and the why never names a location as a reason."""
        over = dict(kev_exposed=True, kev_host_count=2, footprint_band=1, distinct_host_ips=3, country_code="US")
        inside, outside = score_one(in_territory=True, **over), score_one(in_territory=False, **over)
        for key in ("fit_score", "urgency_score", "contact_score", "top_signals", "why", "band"):
            self.assertEqual(inside[key], outside[key], key)
        self.assertNotIn("located in", inside["why"])
        self.assertNotIn("in_territory", inside["top_signals"])

    def test_operator_penalty_union(self):
        """D10: the fit penalty of 30 applies to the T1-or-T2 union; a T2-only name loses fit points; one penalty when both fire; clipped at 0."""
        self.assertEqual(score_one(footprint_band=3, sensitive_stack=True, operator_shape_t1=True)["fit_score"], 35)
        self.assertEqual(score_one(footprint_band=3, sensitive_stack=True, operator_shape_t2=True)["fit_score"], 35)
        self.assertEqual(score_one(footprint_band=3, sensitive_stack=True, operator_shape_t1=True, operator_shape_t2=True)["fit_score"], 35)
        self.assertEqual(score_one(footprint_band=3, sensitive_stack=True)["fit_score"], 65)
        self.assertEqual(score_one(footprint_band=1, operator_shape_t2=True)["fit_score"], 0)
        self.assertEqual(score_one(footprint_band=1, operator_shape_t1=True)["fit_score"], 0)

    def test_union_penalty_lowers_contact_score(self):
        """A T2-only operator scores lower contact than the same account without the flag (urgency 100: fit 45 gives 73, fit 15 gives 58)."""
        full = dict(kev_exposed=True, risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, eol_stack=True,
                    cert_expired_or_soon=True, legacy_tls=True, in_territory=True, footprint_band=3)
        self.assertEqual(score_one(**full)["contact_score"], 73)
        self.assertEqual(score_one(operator_shape_t2=True, **full)["contact_score"], 58)


class ContactScoreTests(unittest.TestCase):
    """Form (b) arithmetic and its invariant."""

    def test_formula_and_rounding(self):
        """contact = round(urgency * (0.5 + 0.5 * fit / 100)), half rounded up, exact in integers."""
        row = score_one(kev_exposed=True, footprint_band=1)  # urgency 50, fit 15 -> 50 * 0.575 = 28.75
        self.assertEqual((row["urgency_score"], row["fit_score"], row["contact_score"]), (50, 15, 29))
        row = score_one(max_cvss_band=1, footprint_band=1)  # urgency 10, fit 15 -> 10 * 0.575 = 5.75
        self.assertEqual(row["contact_score"], 6)
        row = score_one(eol_stack=True, cert_expired_or_soon=True, footprint_band=1, in_territory=False)  # urgency 15, fit 15 -> 15 * 0.575 = 8.625
        self.assertEqual(row["contact_score"], 9)
        row = score_one(max_cvss_band=1, sensitive_stack=True, in_territory=False, footprint_band=0)  # 10 * 0.6 = 6.0
        self.assertEqual(row["contact_score"], 6)
        row = score_one(max_cvss_band=2, footprint_band=0, sensitive_stack=True, operator_shape_t1=False, in_territory=False)  # 25 * 0.6 = 15.0
        self.assertEqual(row["contact_score"], 15)
        row = score_one(max_cvss_band=1, sensitive_stack=True, footprint_band=1)  # fit 35: 10 * 0.675 = 6.75
        self.assertEqual(row["contact_score"], 7)

    def test_half_goes_up(self):
        """Values at and near .5 round half up (25 * 0.5 = 12.5 gives 13)."""
        row = score_one(risky_service_exposed=True, sensitive_stack=True)  # urgency 5, fit 20 -> 5 * 0.6 = 3.0
        self.assertEqual(row["contact_score"], 3)
        row = score_one(legacy_tls=True, sensitive_stack=True, footprint_band=3)  # urgency 5, fit 65 -> 5 * 0.825 = 4.125
        self.assertEqual(row["contact_score"], 4)
        row = score_one(eol_stack=True, footprint_band=1)  # urgency 10, fit 15 -> 5.75
        self.assertEqual(row["contact_score"], 6)
        row = score_one(max_cvss_band=2, in_territory=False, footprint_band=0, sensitive_stack=False)  # fit 0: 25 * 0.5 = 12.5 -> 13
        self.assertEqual(row["contact_score"], 13)

    def test_invariant_at_extremes(self):
        """FLOOR * urgency <= contact <= urgency at fit 0 and 65 (the D11 maximum) and urgency 0 and 100."""
        full = dict(kev_exposed=True, risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, eol_stack=True,
                    cert_expired_or_soon=True, legacy_tls=True)
        rich = dict(in_territory=True, footprint_band=3, sensitive_stack=True)
        cases = {"u100 f65": (full, rich, 100, 65, 83), "u100 f0": (full, {}, 100, 0, 50), "u0 f65": ({}, rich, 0, 65, 0), "u0 f0": ({}, {}, 0, 0, 0)}
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
        self.assertEqual((accounts["a"]["band_uncapped"], accounts["a"]["band"]), ("contact", "review"))  # D10: a would-be contact is held in review
        accounts, _, _, _ = run_scores([sig("a", max_cvss_band=3, **base)], contact=21, review=20)
        self.assertEqual(accounts["a"]["band"], "review")
        accounts, _, _, _ = run_scores([sig("a", max_cvss_band=3, **base)], contact=40, review=21)
        self.assertEqual(accounts["a"]["band"], "skip")

    def test_threshold_options_default_and_override(self):
        """The command-line defaults are the provisional X = 40, Y = 20, N = 200 and the parser accepts overrides including --review-n."""
        self.assertEqual((STAGE.THRESHOLD_CONTACT, STAGE.THRESHOLD_REVIEW, STAGE.REVIEW_N), (40, 20, 200))
        import sys
        old = sys.argv
        try:
            captured = {}
            original = (STAGE.run_stage, STAGE.print_report)
            STAGE.run_stage = lambda con, i, o, c, r, n: captured.update(c=c, r=r, n=n) or {"signals_rows": 0, "accounts_rows": 0}
            STAGE.print_report = lambda *a, **k: None
            sys.argv = ["4_score.py", "--contact", "45", "--review", "25", "--review-n", "77"]
            STAGE.main()
            self.assertEqual((captured["c"], captured["r"], captured["n"]), (45, 25, 77))
            sys.argv = ["4_score.py"]
            STAGE.main()
            self.assertEqual((captured["c"], captured["r"], captured["n"]), (40, 20, 200))
        finally:
            STAGE.run_stage, STAGE.print_report = original
            sys.argv = old
        with self.assertRaises(ValueError):
            run_scores([sig("a")], contact=20, review=20)

    def strong(self, **over):
        """Return a company that reaches contact_score 50 uncapped: urgency 100 and fit 0 (contact 50)."""
        return dict(kev_exposed=True, risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, eol_stack=True,
                    cert_expired_or_soon=True, legacy_tls=True, **over)

    def test_each_cap_alone(self):
        """Every would-be contact gets operator_unverified; singleton, low confidence and operator shape add their own reason; all go to review."""
        rows = [sig("clean", **self.strong()),
                sig("single", host_count=1, **self.strong()),
                sig("low", identity_confidence="low", identity_source="cert_o", **self.strong()),
                sig("oper", operator_shape_t2=True, **self.strong())]
        accounts, _, _, _ = run_scores(rows)
        expected = {"clean": "operator_unverified", "single": "operator_unverified,singleton", "low": "low_confidence,operator_unverified",
                    "oper": "operator_name_shape,operator_unverified"}
        for cid, reasons in expected.items():
            a = accounts[cid]
            self.assertEqual((a["band_uncapped"], a["band"], a["cap_reasons"], a["final_band"]), ("contact", "review", reasons, "review"), cid)

    def test_operator_unverified_on_would_be_contact_alone(self):
        """A clean would-be contact is capped only by operator_unverified; band_uncapped stays contact; its contact_score is at or above X."""
        a = score_one(**self.strong())
        self.assertEqual((a["band_uncapped"], a["band"], a["cap_reasons"]), ("contact", "review", "operator_unverified"))
        self.assertGreaterEqual(a["contact_score"], STAGE.THRESHOLD_CONTACT)

    def test_operator_unverified_not_given_to_non_contacts_or_excluded(self):
        """Review, skip and excluded accounts never carry operator_unverified, and an excluded would-be contact stays exclude."""
        rows = [sig("r", max_cvss_band=3), sig("s", max_cvss_band=1), sig("e", noise_host_count=3, noise_host_share=0.6, host_count=2, **self.strong())]
        accounts, _, _, _ = run_scores(rows)
        for cid, band in (("r", "review"), ("s", "skip"), ("e", "exclude")):
            self.assertEqual((accounts[cid]["band"], accounts[cid]["cap_reasons"]), (band, None), cid)
        self.assertEqual(accounts["e"]["band_uncapped"], "exclude")

    def test_caps_together_sorted(self):
        """All reasons that apply are listed, sorted alphabetically and comma separated, with operator_unverified among them."""
        a = score_one(host_count=1, identity_confidence="low", identity_source="cert_o", operator_shape_t1=True, **self.strong())
        self.assertEqual(a["cap_reasons"], "low_confidence,operator_name_shape,operator_unverified,singleton")
        a = score_one(host_count=1, operator_shape_t2=True, **self.strong())
        self.assertEqual(a["cap_reasons"], "operator_name_shape,operator_unverified,singleton")
        a = score_one(host_count=1, **self.strong())
        self.assertEqual(a["cap_reasons"], "operator_unverified,singleton")
        b = score_one(identity_confidence="low", identity_source="cert_o", operator_shape_t2=True, **self.strong())
        for r in (a, b):
            parts = r["cap_reasons"].split(",")
            self.assertEqual(parts, sorted(parts))

    def test_caps_only_contact_to_review_never_to_skip(self):
        """A capped company below the contact threshold is not touched by caps: review stays review (no reason), skip stays skip."""
        accounts, _, _, _ = run_scores([sig("r", host_count=1, max_cvss_band=3), sig("s", host_count=1, max_cvss_band=1)])
        self.assertEqual((accounts["r"]["band"], accounts["r"]["cap_reasons"]), ("review", None))
        self.assertEqual((accounts["s"]["band"], accounts["s"]["cap_reasons"], accounts["s"]["band_uncapped"]), ("skip", None, "skip"))

    def test_no_account_in_contact(self):
        """Over a grid of cap flags and high urgency, no account has band contact (D10), final_band equals band, and every would-be contact has the reason."""
        rows = []
        for i, (single, low, op) in enumerate(itertools.product((False, True), repeat=3)):
            over = dict(host_count=1 if single else 5, operator_shape_t2=op, **self.strong())
            if low:
                over.update(identity_confidence="low", identity_source="cert_o")
            rows.append(sig(f"g{i}", **over))
        rows.append(sig("weak", max_cvss_band=3))
        accounts, _, _, _ = run_scores(rows)
        for a in accounts.values():
            self.assertNotEqual(a["band"], "contact", a)
            self.assertEqual(a["final_band"], a["band"])
            if a["band_uncapped"] == "contact":
                self.assertIn("operator_unverified", a["cap_reasons"].split(","))

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


class ReviewBandTests(unittest.TestCase):
    """D11.2: review is every would-be contact plus the best remaining accounts by the stage order up to N, with the floor Y."""

    @staticmethod
    def strong(**over):
        """Return a company with urgency 100 and fit 0 (contact 50), a would-be contact."""
        return dict(kev_exposed=True, risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, eol_stack=True,
                    cert_expired_or_soon=True, legacy_tls=True, **over)

    @staticmethod
    def graded(prefix, count):
        """Return count companies mixing KEV and CVSS band 3 with footprint bands 3 to 0 to give contact scores 36, 33, 29, 25, 29, 26, 23, 20."""
        specs = [dict(kev_exposed=True, footprint_band=3), dict(kev_exposed=True, footprint_band=2), dict(kev_exposed=True, footprint_band=1),
                 dict(kev_exposed=True, footprint_band=0), dict(max_cvss_band=3, footprint_band=3), dict(max_cvss_band=3, footprint_band=2),
                 dict(max_cvss_band=3, footprint_band=1), dict(max_cvss_band=3, footprint_band=0)]  # contact 36, 33, 29, 25, 29, 26, 23, 20
        return [sig(f"{prefix}{i}", **specs[i]) for i in range(count)]

    def test_top_n_keeps_the_best_in_stage_order(self):
        """With N = 3 and eight scored accounts, exactly the three best by contact_score are in review and the rest are skip."""
        accounts, order, _, _ = run_scores(self.graded("g", 8), review_n=3)
        review = [a for a in order if accounts[a]["band"] == "review"]
        self.assertEqual(len(review), 3)
        self.assertEqual(review, order[:3])  # the output sort is the stage order
        self.assertEqual(sorted(accounts[a]["contact_score"] for a in review), [29, 33, 36])
        for a in order[3:]:
            self.assertEqual(accounts[a]["band"], "skip")
            self.assertTrue(accounts[a]["why"].endswith(STAGE.SKIP_CLAUSE_SIGNAL), accounts[a]["why"])  # D12.2: KEV and CVSS sentences are kept
        self.assertTrue(all(accounts[a]["band_uncapped"] in ("review", "contact") for a in order))  # band_uncapped keeps its threshold meaning

    def test_would_be_contacts_are_never_dropped(self):
        """When the would-be contacts exceed N the band is exactly the would-be contacts, and no other account is in review."""
        rows = [sig(f"w{i}", **self.strong()) for i in range(5)] + self.graded("g", 4)
        for n in (0, 1, 3, 5):
            accounts, _, _, _ = run_scores(rows, review_n=n)
            review = {a for a, r in accounts.items() if r["band"] == "review"}
            self.assertEqual(review, {f"w{i}" for i in range(5)}, n)
            for a in review:
                self.assertEqual((accounts[a]["band_uncapped"], accounts[a]["cap_reasons"]), ("contact", "operator_unverified"))

    def test_n_larger_than_would_be_count_adds_the_best_others(self):
        """With 2 would-be contacts and N = 5 the band is the 2 plus the 3 best others, with the floor applied last."""
        rows = [sig(f"w{i}", **self.strong()) for i in range(2)] + self.graded("g", 8)
        accounts, _, _, _ = run_scores(rows, review_n=5)
        review = {a for a, r in accounts.items() if r["band"] == "review"}
        self.assertEqual(len(review), 5)
        self.assertTrue({"w0", "w1", "g0", "g1"} <= review)
        self.assertEqual(sum(1 for a in review if a.startswith("g") and accounts[a]["contact_score"] >= 29), 3)
        accounts, _, _, _ = run_scores(rows, review_n=100)
        self.assertEqual(sum(1 for r in accounts.values() if r["band"] == "review"), 10)  # every contact_score is at or above 20

    def test_floor_stops_a_large_n(self):
        """The floor Y keeps low scores out of review however large N is: contact 20 is in at Y = 20 and out at Y = 21; 13 is out at Y = 20."""
        rows = [sig("hi", max_cvss_band=3), sig("lo", max_cvss_band=2), sig("zero")]
        accounts, _, _, _ = run_scores(rows, review_n=1000)
        self.assertEqual([accounts[k]["band"] for k in ("hi", "lo", "zero")], ["review", "skip", "skip"])
        accounts, _, _, _ = run_scores(rows, review_n=1000, review=21)
        self.assertEqual(accounts["hi"]["band"], "skip")
        self.assertEqual(accounts["hi"]["band_uncapped"], "skip")

    def test_tie_break_urgency_then_host_count_then_id(self):
        """At the cut equal contact_score is ordered by urgency desc, then host_count desc, then account_id asc (a total order)."""
        urg = [sig("b_low_urgency", max_cvss_band=3, footprint_band=3, host_count=20), sig("a_high_urgency", kev_exposed=True, footprint_band=1, host_count=2)]
        accounts, _, _, _ = run_scores(urg, review_n=1)
        self.assertEqual(accounts["a_high_urgency"]["contact_score"], accounts["b_low_urgency"]["contact_score"])
        self.assertEqual((accounts["a_high_urgency"]["band"], accounts["b_low_urgency"]["band"]), ("review", "skip"))
        hosts = [sig("small", kev_exposed=True, footprint_band=1, host_count=5), sig("big", kev_exposed=True, footprint_band=1, host_count=9)]
        accounts, _, _, _ = run_scores(hosts, review_n=1)
        self.assertEqual((accounts["big"]["band"], accounts["small"]["band"]), ("review", "skip"))
        ids = [sig("id2", kev_exposed=True, footprint_band=1), sig("id1", kev_exposed=True, footprint_band=1)]
        for _ in range(2):  # a rerun is identical
            accounts, _, _, _ = run_scores(ids, review_n=1)
            self.assertEqual((accounts["id1"]["band"], accounts["id2"]["band"]), ("review", "skip"))

    def test_tie_at_the_cut_unflagged_beats_flagged(self):
        """D12.1: at the cut, equal score and urgency, the unflagged account wins the slot over a flagged one even with more hosts and more KEV hosts."""
        flagged = sig("a_flagged", kev_exposed=True, kev_host_count=9, footprint_band=3, host_count=50, operator_shape_t2=True)  # fit 45 - 30 = 15
        plain = sig("z_plain", kev_exposed=True, kev_host_count=1, footprint_band=1, host_count=2)  # fit 15
        accounts, order, _, _ = run_scores([flagged, plain], review_n=1)
        self.assertEqual(accounts["a_flagged"]["contact_score"], accounts["z_plain"]["contact_score"])
        self.assertEqual(accounts["a_flagged"]["urgency_score"], accounts["z_plain"]["urgency_score"])
        self.assertEqual((accounts["z_plain"]["band"], accounts["a_flagged"]["band"]), ("review", "skip"))
        self.assertEqual(order, ["z_plain", "a_flagged"])
        self.assertTrue(accounts["a_flagged"]["why"].endswith(STAGE.SKIP_CLAUSE_SIGNAL))

    def test_tie_order_kev_hosts_then_host_count_then_id(self):
        """D12.1: with score, urgency and flag equal the order is kev_host_count desc, then host_count desc, then account_id asc; null KEV counts as 0."""
        base = dict(kev_exposed=True, footprint_band=1)
        rows = [sig("k0", kev_host_count=1, host_count=9, **base), sig("k3", kev_host_count=3, host_count=2, **base),
                sig("h8", kev_host_count=2, host_count=8, **base), sig("h4b", kev_host_count=2, host_count=4, **base),
                sig("h4a", kev_host_count=2, host_count=4, **base)]
        accounts, order, _, _ = run_scores(rows, review_n=2)
        self.assertEqual(len({r["contact_score"] for r in accounts.values()}), 1)
        self.assertEqual(order, ["k3", "h8", "h4a", "h4b", "k0"])
        self.assertEqual([accounts[a]["band"] for a in order], ["review", "review", "skip", "skip", "skip"])
        _, order, _, _ = run_scores([sig("o", kev_host_count=0, **base), sig("n", kev_host_count=None, **base)], review_n=1)
        self.assertEqual(order, ["n", "o"])  # null counts as 0, so the id decides

    def test_stage_order_sql_text(self):
        """D12.1: the shared order list is exactly score, urgency, flag asc, coalesce KEV, host_count, id."""
        self.assertEqual(STAGE.stage_order_sql("account_id"),
                         "contact_score DESC, urgency_score DESC, operator_name_shape ASC, coalesce(kev_host_count, 0) DESC, host_count DESC, account_id ASC")

    def test_top_accounts_report_uses_the_new_order(self):
        """D12.1: the top-accounts report lists a tie in the stage order (unflagged before flagged)."""
        flagged = sig("a_flagged", company_name="Flagged Co", kev_exposed=True, kev_host_count=9, footprint_band=3, host_count=50, operator_shape_t2=True)
        plain = sig("z_plain", company_name="Plain Co", kev_exposed=True, kev_host_count=1, footprint_band=1, host_count=2)
        run_scores([flagged, plain], review_n=1)
        rep = QuietReport()
        STAGE.section_top(LAST_CON[0], rep, 2)
        text = "\n".join(rep.lines)
        self.assertLess(text.index("Plain Co"), text.index("Flagged Co"))

    def test_excluded_accounts_never_take_a_slot(self):
        """An excluded account is not ranked: with N = 1 the single review slot goes to the best non-excluded account."""
        rows = [sig("ex", noise_host_count=3, noise_host_share=0.6, host_count=2, **self.strong(footprint_band=3)), sig("ok", max_cvss_band=3), sig("ok2", max_cvss_band=3, host_count=9)]
        accounts, _, _, _ = run_scores(rows, review_n=1)
        self.assertEqual(accounts["ex"]["band"], "exclude")
        self.assertEqual(sorted(a for a, r in accounts.items() if r["band"] == "review"), ["ok2"])

    def test_no_account_in_contact_and_final_band_follows_band(self):
        """Whatever N is, no account is in contact and final_band equals band."""
        for n in (0, 2, 200):
            accounts, _, _, _ = run_scores([sig(f"w{i}", **self.strong()) for i in range(3)] + self.graded("g", 8), review_n=n)
            for a in accounts.values():
                self.assertNotEqual(a["band"], "contact")
                self.assertEqual(a["final_band"], a["band"])

    def test_cut_report_prints_score_and_tie_size(self):
        """The cut section names the score at the cut and the tie size and how many tied accounts are kept."""
        rows = [sig(f"t{i}", kev_exposed=True, footprint_band=1, host_count=2 + i) for i in range(4)] + [sig("top", **self.strong())]
        run_scores(rows, review_n=3)  # would-be 1, N = 3: two of the four tied accounts (contact 29) are kept
        rep = QuietReport()
        STAGE.section_cut(LAST_CON[0], rep, STAGE.THRESHOLD_CONTACT, STAGE.THRESHOLD_REVIEW, 3)
        text = "\n".join(rep.lines)
        self.assertIn("contact_score 29: 4 non-excluded accounts are tied at 29, 2 are kept in review and 2 go to skip", text)
        self.assertIn("tie broken by urgency_score, operator_name_shape (false first), kev_host_count, host_count, account_id", text)
        self.assertIn("Kept at the cut: Acme (unflagged, 5 hosts, 0 KEV hosts)", text)
        rep = QuietReport()
        STAGE.section_cut(LAST_CON[0], rep, STAGE.THRESHOLD_CONTACT, STAGE.THRESHOLD_REVIEW, 1)
        self.assertIn("the band is the would-be contacts only", "\n".join(rep.lines))


class WhyTests(unittest.TestCase):
    """Pinned phrases, the length limit and no empty why."""

    def test_pinned_phrases(self):
        """Every signal phrase, each cap clause, the no-signal text and the exclude text are pinned."""
        cases = [
            (dict(kev_exposed=True, kev_host_count=1), "1 host running software whose version matches the CISA known-exploited list."),
            (dict(kev_exposed=True, kev_host_count=3), "3 hosts running software whose version matches the CISA known-exploited list."),
            (dict(max_cvss_band=3, max_cvss=9.8), "Worst version-matched vulnerability scores CVSS 9.8."),
            (dict(max_cvss_band=2, max_cvss=7.5), "Worst version-matched vulnerability scores CVSS 7.5."),
            (dict(max_cvss_band=1, max_cvss=4.3), "Worst version-matched vulnerability scores CVSS 4.3."),
            (dict(risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, risky_ports=[22, 3389, 3306]),
             "An exposed admin or database service (SSH 22, RDP 3389) on software that is end-of-life or whose version matches a CVSS 7+ vulnerability."),
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
        self.assertTrue(top["why"].startswith("9 IPs in the footprint; worst version-matched vulnerability scores CVSS 3.0."), top["why"])
        sens = score_one(max_cvss_band=1, max_cvss=3.0, sensitive_stack=True, in_territory=True, country_code="US")
        self.assertTrue(sens["why"].startswith("Database, medical or IoT systems in the stack; worst version-matched vulnerability scores CVSS 3.0."), sens["why"])
        for why in (top["why"], sens["why"]):
            self.assertNotIn("located in", why)
            self.assertNotIn("is vulnerable", why)
            self.assertNotIn("known-exploited host", why)

    def test_cap_clauses_and_skip_texts(self):
        """Cap clauses, the no-signal sentence, the D11.3 skip and operator sentences and the exclude sentence."""
        strong = dict(kev_exposed=True, kev_host_count=1, eol_stack=True, eol_host_count=1, risky_service_exposed=True, risky_non_ssh_exposed=True,
                      exposed_and_outdated=True, risky_ports=[3389], cert_expired_or_soon=True, cert_issue_host_count=1, legacy_tls=True, legacy_tls_host_count=1)
        clause = "Not yet checked that this is an end-user organisation, not a network operator."
        self.assertEqual(STAGE.UNVERIFIED_CLAUSE, clause)
        self.assertTrue(score_one(**strong)["why"].endswith(" " + clause))
        for over, text in ((dict(host_count=1), "Only one host seen."), (dict(identity_confidence="low", identity_source="cert_o"), "Named only by a TLS certificate."),
                           (dict(operator_shape_t1=True), "Name looks like a network operator.")):
            why = score_one(**over, **strong)["why"]
            self.assertTrue(why.endswith(f"{text} {clause}"), why)
            self.assertEqual(sum(why.count(c) for _, c in STAGE.CAP_CLAUSES), 1, why)  # one existing cap clause plus the D10 clause
        two = score_one(host_count=1, operator_shape_t2=True, **strong)["why"]
        self.assertTrue(two.endswith(f"Name looks like a network operator. {clause}"), two)  # priority rule keeps one existing cap clause
        self.assertNotIn(clause, score_one(max_cvss_band=3, max_cvss=9.8)["why"])  # a review account that is not a would-be contact
        self.assertEqual(score_one()["why"], "No exposure signal found in the scan (5 hosts seen).")
        self.assertEqual(score_one(host_count=1)["why"], "No exposure signal found in the scan (1 host seen).")
        self.assertEqual(STAGE.SKIP_CLAUSE, "Below the review cut-off.")
        self.assertEqual(STAGE.SKIP_CLAUSE_SIGNAL, "Ranked below this run's review list; a rank, not a judgement of risk.")
        skip = score_one(max_cvss_band=1, max_cvss=3.0)
        self.assertEqual((skip["band"], skip["why"]),
                         ("skip", "Worst version-matched vulnerability scores CVSS 3.0. Ranked below this run's review list; a rank, not a judgement of risk."))  # D12.2: a CVSS skip row
        self.assertNotIn("Exposure is limited", skip["why"])
        self.assertNotIn("Below the review cut-off.", score_one(max_cvss_band=3, max_cvss=9.8)["why"])  # a review row
        self.assertEqual(score_one(noise_host_count=3, noise_host_share=0.6, host_count=2)["why"],
                         "Mostly honeypot or attacker-infrastructure hosts (3 of 5).")

    def test_operator_clause_on_review_rows_reached_by_top_n(self):
        """A review row with operator_name_shape that is not a would-be contact ends with the operator clause; a non-operator review row and an operator skip row do not."""
        op = score_one(max_cvss_band=3, max_cvss=9.8, operator_shape_t2=True)  # urgency 40, fit 0 -> contact 20, review by the floor and N
        self.assertEqual((op["band"], op["band_uncapped"], op["cap_reasons"]), ("review", "review", None))
        self.assertEqual(op["why"], "Worst version-matched vulnerability scores CVSS 9.8. Name looks like a network operator.")
        plain = score_one(max_cvss_band=3, max_cvss=9.8)
        self.assertEqual(plain["why"], "Worst version-matched vulnerability scores CVSS 9.8.")
        skip_op = score_one(max_cvss_band=1, max_cvss=3.0, operator_shape_t1=True)
        self.assertEqual(skip_op["band"], "skip")
        self.assertNotIn("network operator", skip_op["why"])
        self.assertEqual(skip_op["why"], "Worst version-matched vulnerability scores CVSS 3.0. Ranked below this run's review list; a rank, not a judgement of risk.")
        accounts, _, _, _ = run_scores([sig("o", max_cvss_band=3, max_cvss=9.8, operator_shape_t2=True)], review_n=0)
        self.assertEqual(accounts["o"]["band"], "skip")  # N = 0 and not a would-be contact: skip, so no operator clause
        self.assertTrue(accounts["o"]["why"].endswith(STAGE.SKIP_CLAUSE_SIGNAL))  # D12.2: the CVSS sentence is kept

    def test_skip_clause_d12_by_kept_signal(self):
        """D12.2: a skip row with a kept KEV or CVSS sentence ends with the signal clause; any other skip row keeps the plain clause."""
        accounts, _, _, _ = run_scores([sig("k", kev_exposed=True, kev_host_count=2), sig("v", max_cvss_band=1, max_cvss=3.0), sig("e", eol_stack=True, eol_host_count=2),
                                        sig("f", footprint_band=1, distinct_host_ips=5, risky_service_exposed=True, risky_ports=[22])], review_n=0)
        self.assertEqual(accounts["k"]["band"], "skip")
        self.assertEqual(accounts["k"]["why"], "2 hosts running software whose version matches the CISA known-exploited list. " + STAGE.SKIP_CLAUSE_SIGNAL)  # a KEV skip row
        self.assertEqual(accounts["v"]["why"], "Worst version-matched vulnerability scores CVSS 3.0. " + STAGE.SKIP_CLAUSE_SIGNAL)  # a CVSS skip row
        self.assertEqual(accounts["e"]["why"], "2 hosts on end-of-life software. Below the review cut-off.")  # no KEV or CVSS sentence: the old clause
        self.assertEqual(accounts["f"]["why"], "5 IPs in the footprint; SSH (port 22) open to the internet. Below the review cut-off.")
        for cid in ("k", "v"):
            self.assertNotIn(STAGE.SKIP_CLAUSE, accounts[cid]["why"])
        self.assertNotIn(STAGE.SKIP_CLAUSE_SIGNAL, accounts["e"]["why"] + accounts["f"]["why"])
        self.assertEqual(len(STAGE.SKIP_CLAUSE_SIGNAL.split()), 13)

    def test_skip_clause_follows_the_kept_signals(self):
        """D12.2: the clause is judged on the signals kept: a skip row whose kept signal is not KEV or CVSS gets the plain clause."""
        row = dict(band="skip", noise_host_count=0, host_count=5, cap_reasons=None, operator_name_shape=False, urgency_score=40, p_vuln=40, vuln_signal="max_cvss_band",
                   max_cvss=9.8, p_expo=0, expo_signal=None, p_eol=0, p_cert=0, p_legacy=0, p_footprint=0, p_territory=0, p_sensitive=0, risky_ports=[],
                   kev_host_count=0, eol_host_count=0, cert_issue_host_count=0, legacy_tls_host_count=0, distinct_host_ips=1, country_code="DE")
        top, why = STAGE.build_why(row)
        self.assertEqual((top, why.endswith(STAGE.SKIP_CLAUSE_SIGNAL)), ("max_cvss_band", True))
        row.update(p_vuln=0, vuln_signal=None, p_eol=10, eol_host_count=1)
        top, why = STAGE.build_why(row)
        self.assertEqual((top, why.endswith(STAGE.SKIP_CLAUSE), STAGE.SKIP_CLAUSE_SIGNAL in why), ("eol_stack", True, False))

    def test_exposure_phrase_d12(self):
        """D12.3: one phrase for exposed_and_outdated, no branch, and the old words never appear."""
        self.assertEqual(STAGE.EXPOSED_OUTDATED_TEXT, "on software that is end-of-life or whose version matches a CVSS 7+ vulnerability")
        for over in (dict(eol_stack=True, eol_host_count=1), dict(max_cvss_band=2, max_cvss=7.5), dict()):
            why = score_one(risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, risky_ports=[3306], **over)["why"]
            self.assertIn("An exposed admin or database service (MySQL 3306) on software that is end-of-life or whose version matches a CVSS 7+ vulnerability", why)
            self.assertNotIn("on outdated software", why)
            self.assertLessEqual(len(why.split()), 40)

    def test_exposure_phrase_with_kev_falls_back_to_one_signal(self):
        """D12.3: when KEV, the longer exposure phrase and the D10 clause exceed 40 words, the one-signal fallback keeps the top signal and the why stays within 40 words."""
        a = score_one(kev_exposed=True, kev_host_count=3, risky_service_exposed=True, risky_non_ssh_exposed=True, exposed_and_outdated=True, risky_ports=[3389, 3306],
                      eol_stack=True, eol_host_count=1)
        self.assertEqual((a["band_uncapped"], a["top_signals"]), ("contact", "kev_exposed"))
        self.assertLessEqual(len(a["why"].split()), 40)
        self.assertNotIn("end-of-life or whose", a["why"])

    def test_top_two_by_points_with_tie_order(self):
        """Top two signals by points; ties go vulnerability, exposure, hygiene, fit; top_signals lists exactly the signals used."""
        a = score_one(kev_exposed=True, kev_host_count=1, exposed_and_outdated=True, risky_service_exposed=True, risky_non_ssh_exposed=True,
                      risky_ports=[3389], eol_stack=True, eol_host_count=1)
        self.assertEqual(a["top_signals"], "kev_exposed")  # D12.3: the longer exposure phrase no longer fits beside KEV and the D10 clause in 40 words, so the one-signal fallback applies
        a = score_one(exposed_and_outdated=True, risky_service_exposed=True, risky_non_ssh_exposed=True, risky_ports=[3389], eol_stack=True, eol_host_count=1)
        self.assertEqual(a["top_signals"], "exposed_and_outdated,eol_stack")
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
            self.assertNotIn("located in", why)
            self.assertNotIn("Exposure is limited", why)
            for word in ("breach", "compromised", "hacked"):
                self.assertNotIn(word, why.lower())
            if a["band_uncapped"] == "contact":
                self.assertTrue(a["why"].endswith(STAGE.UNVERIFIED_CLAUSE), why)
            else:
                self.assertNotIn(STAGE.UNVERIFIED_CLAUSE, why)
        self.assertTrue(any(a["band_uncapped"] == "contact" for a in accounts.values()))
        worst = max(len(a["why"].split()) for a in accounts.values())
        self.assertLessEqual(worst, 40)


class OutputShapeTests(unittest.TestCase):
    """Row equality, the 17 columns with their types, ordering and the stage 4 nulls."""

    def test_rows_equal_columns_types_order_nulls(self):
        """Row count equals the signals, the 17 columns have the D9.6 types, sort is contact desc, and decision and prompt_version are null."""
        rows = [sig("a", max_cvss_band=3), sig("b", kev_exposed=True, footprint_band=1), sig("c"), sig("d", noise_host_count=2, noise_host_share=0.5)]
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
            row = score_one(kev_exposed=True, footprint_band=1)  # (30 * 15 + 70 * 50 + 50) // 100 = 40
            self.assertEqual(row["contact_score"], 40)
            row = score_one(footprint_band=1)  # urgency 0, fit 15: form (a) lets fit alone lift the score (the reason (b) is recommended)
            self.assertEqual(row["contact_score"], (STAGE.W_F_PCT * 15 + 50) // 100)
        finally:
            STAGE.CONTACT_FORM = original

    def test_full_flag_defaults_do_not_overwrite_sample(self):
        """--full has its own default paths so it cannot overwrite the sample output."""
        self.assertNotEqual(STAGE.FULL_OUTPUT_PATH, STAGE.OUTPUT_PATH)
        self.assertNotEqual(STAGE.FULL_INPUT_PATH, STAGE.INPUT_PATH)


ROOT_DIR = Path(__file__).resolve().parent.parent


def run_cli(args, env=None, flags=()):
    """Run the stage script as a subprocess and return the completed process (text output, UTF-8 decoded)."""
    return subprocess.run([sys.executable, *flags, str(STAGE_PATH), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=dict(os.environ, **(env or {})))


def write_signals(path, rows):
    """Write signal row dicts as a signals parquet at path (an empty list gives a valid zero-row file)."""
    con = duckdb.connect()
    con.execute(f"CREATE TABLE s ({SIGNAL_DDL})")
    for row in rows:
        con.execute(f"INSERT INTO s VALUES ({','.join('?' * 36)})", [row["company_id"]] + [row[c] for c in COLUMNS])
    con.execute(f"COPY s TO '{Path(path).as_posix()}' (FORMAT PARQUET)")


def why_row(**over):
    """Return a row dict for build_why: a review account with a KEV signal and an exposed-and-outdated signal (34 words before any clause)."""
    row = dict(band="review", noise_host_count=0, host_count=5, cap_reasons=None, operator_name_shape=False, urgency_score=50,
               p_vuln=50, vuln_signal="kev_exposed", kev_host_count=3, max_cvss=9.8, p_expo=30, expo_signal="exposed_and_outdated",
               risky_ports=[22, 3389], p_eol=0, eol_host_count=0, p_cert=0, cert_issue_host_count=0, p_legacy=0, legacy_tls_host_count=0,
               p_footprint=0, distinct_host_ips=5, p_territory=0, country_code="DE", p_sensitive=0)
    row.update(over)
    return row


class BandEdgeTests(unittest.TestCase):
    """QA finding 4: the band edges are inclusive, pinned with accounts exactly at the thresholds."""

    def five_at_eight(self, **kwargs):
        """Score five accounts that each have contact_score 8 (RDP exposed only, fit 0) and return the rows by id."""
        rows = [sig(c, risky_service_exposed=True, risky_non_ssh_exposed=True, risky_ports=[3389]) for c in "abcde"]
        accounts, _, _, _ = run_scores(rows, **kwargs)
        self.assertEqual({a["contact_score"] for a in accounts.values()}, {8})
        return accounts

    def test_would_be_contact_exactly_at_contact_threshold(self):
        """Five accounts at 8 with --contact 8 are all would-be contacts (held in review) even with N = 1; with --contact 9 only N = 1 reaches review."""
        accounts = self.five_at_eight(contact=8, review=1, review_n=1)
        self.assertEqual([accounts[c]["band_uncapped"] for c in "abcde"], ["contact"] * 5)
        self.assertEqual([accounts[c]["band"] for c in "abcde"], ["review"] * 5)
        accounts = self.five_at_eight(contact=9, review=1, review_n=1)
        self.assertEqual([accounts[c]["band_uncapped"] for c in "abcde"], ["review"] * 5)  # band_uncapped ignores the top-N cut
        self.assertEqual([accounts[c]["band"] for c in "abcde"], ["review", "skip", "skip", "skip", "skip"])

    def test_review_floor_exactly_at_review_threshold(self):
        """Accounts at 8 reach review with --review 8 and fall to skip with --review 9 (the floor is inclusive)."""
        accounts = self.five_at_eight(contact=20, review=8, review_n=10)
        self.assertEqual([accounts[c]["band"] for c in "abcde"], ["review"] * 5)
        accounts = self.five_at_eight(contact=20, review=9, review_n=10)
        self.assertEqual([accounts[c]["band"] for c in "abcde"], ["skip"] * 5)


class WhyLimitTests(unittest.TestCase):
    """QA finding 6: the 40-word limit pinned with literal numbers, not derived from the constant."""

    def test_forty_words_accepted(self):
        """A why of exactly 40 words keeps both signals."""
        top, why = STAGE.build_why(why_row(cap_reasons="low_confidence"))
        self.assertEqual(len(why.split()), 40)
        self.assertEqual(top, "kev_exposed,exposed_and_outdated")
        self.assertTrue(why.endswith("Named only by a TLS certificate."))

    def test_forty_one_words_cut_to_one_signal(self):
        """A why that would be 41 words drops to one signal and ends within 40 words."""
        top, why = STAGE.build_why(why_row(band="skip", vuln_signal="max_cvss_band", max_cvss=9.8))
        self.assertEqual(top, "max_cvss_band")
        self.assertEqual(why, "Worst version-matched vulnerability scores CVSS 9.8. Ranked below this run's review list; a rank, not a judgement of risk.")
        self.assertLessEqual(len(why.split()), 40)

    def test_limit_constant_is_forty(self):
        """The limit itself is 40 (D9.6 item 7)."""
        self.assertEqual(STAGE.WHY_MAX_WORDS, 40)


class ArgumentErrorTests(unittest.TestCase):
    """QA finding 9: threshold and review-n checks are explicit argument errors that survive python -O."""

    def refused(self, args, text, flags=()):
        """Assert the CLI exits with code 2 and an error message containing text, writing no output file."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp, "o.parquet")
            result = run_cli(["--input", Path(tmp, "none.parquet"), "--output", out, *args], flags=flags)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn(text, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out.exists())

    def test_contact_below_review(self):
        """--contact below --review, and equal, are refused."""
        self.refused(["--contact", "10", "--review", "50"], "must be below --contact")
        self.refused(["--contact", "20", "--review", "20"], "must be below --contact")

    def test_negative_review_n(self):
        """A negative --review-n is refused with a message."""
        self.refused(["--review-n", "-1"], "must not be negative")

    def test_non_integer_inputs(self):
        """Non-integer thresholds and N are refused by the argument parser."""
        self.refused(["--contact", "40.5"], "invalid int value")
        self.refused(["--review", "abc"], "invalid int value")
        self.refused(["--review-n", "1e3"], "invalid int value")

    def test_checks_survive_python_optimise_flag(self):
        """With python -O (asserts removed) the refusals still happen."""
        self.refused(["--contact", "10", "--review", "50"], "must be below --contact", flags=("-O",))
        self.refused(["--review-n", "-5"], "must not be negative", flags=("-O",))

    def test_run_stage_rejects_bad_values(self):
        """run_stage itself raises ValueError (not an assert) for a bad pair and for a negative N."""
        for kwargs in ({"contact": 20, "review": 30}, {"review_n": -1}):
            with self.assertRaises(ValueError):
                run_scores([sig("a")], **kwargs)


class CliRobustnessTests(unittest.TestCase):
    """QA findings 2, 3, 7, 8 for the accounts stage: zero rows, report path, UTF-8 report, output path guard."""

    def test_zero_row_signals_complete(self):
        """An empty signals parquet gives exit code 0, a valid zero-row accounts file and a readable report."""
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "signals.parquet"), Path(tmp, "accounts.parquet")
            write_signals(src, [])
            result = run_cli(["--input", src, "--output", out])
            self.assertEqual(result.returncode, 0, result.stderr[-500:])
            con = duckdb.connect()
            self.assertEqual(con.execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchone()[0], 0)
            self.assertIn("0 rows", result.stdout)
            self.assertTrue(Path(tmp, "accounts_stage_report.md").exists())

    def test_report_goes_next_to_scratch_output(self):
        """With a non-default --output and no --report the report sits beside the output; the committed dq folder is untouched."""
        dq = ROOT_DIR / "outputs" / "dq"
        before = sorted((f.name, f.stat().st_mtime_ns) for f in dq.glob("accounts_stage_*.md")) if dq.exists() else []
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "signals.parquet"), Path(tmp, "sub", "accounts.parquet")
            write_signals(src, [sig("a", max_cvss_band=3)])
            result = run_cli(["--input", src, "--output", out])
            self.assertEqual(result.returncode, 0, result.stderr[-500:])
            self.assertTrue(Path(tmp, "sub", "accounts_stage_report.md").exists())
            custom = Path(tmp, "elsewhere", "my_report.md")
            result = run_cli(["--input", src, "--output", out, "--report", custom])
            self.assertEqual(result.returncode, 0, result.stderr[-500:])
            self.assertTrue(custom.exists())
        after = sorted((f.name, f.stat().st_mtime_ns) for f in dq.glob("accounts_stage_*.md")) if dq.exists() else []
        self.assertEqual(before, after)

    def test_default_output_keeps_committed_report_path(self):
        """With the default output the report path is the committed outputs/dq path."""
        guard = STAGE.load_guard()
        default_report = STAGE.REPORT_DIR / "accounts_stage_2026-01-01.md"
        self.assertEqual(guard.choose_report_path(str(STAGE.OUTPUT_PATH), STAGE.OUTPUT_PATH, None, default_report, "accounts"), default_report)
        self.assertEqual(guard.choose_report_path("scratch/a.parquet", STAGE.OUTPUT_PATH, None, default_report, "accounts").name, "accounts_stage_report.md")

    def test_cjk_name_under_cp1252_pipe(self):
        """A CJK company name does not break the report under the default Windows pipe encoding."""
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "signals.parquet"), Path(tmp, "accounts.parquet")
            write_signals(src, [sig("a", company_name="\u682a\u5f0f\u4f1a\u793e\u30c6\u30b9\u30c8", max_cvss_band=3)])
            env = {"PYTHONIOENCODING": "cp1252"}
            result = run_cli(["--input", src, "--output", out], env=env)
            self.assertEqual(result.returncode, 0, result.stderr[-500:])
            self.assertTrue(out.exists())

    def test_output_under_raw_or_dataset_folder_refused(self):
        """Outputs (and reports) under scratch stand-ins for data/raw and the dataset folder, in every path form, are refused and nothing is written."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "signals.parquet")
            write_signals(src, [sig("a")])
            GUARD_SUPPORT.assert_stage_refuses(self, STAGE, ["--input", src], with_report=True, safe_dir=tmp)


    def test_check_consistency_exits_before_writing(self):
        """Fan-out, an empty why and a band contact each stop the stage with a readable message before write_output runs."""
        cases = {"fan-out": "INSERT INTO signals SELECT * FROM signals", "empty why": "UPDATE accounts SET why = ' '", "band contact": "UPDATE accounts SET band = 'contact', final_band = 'contact'"}
        for label, damage in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                src, out = Path(tmp, "signals.parquet"), Path(tmp, "o", "accounts.parquet")
                write_signals(src, [sig("a")])
                con = duckdb.connect()
                real_build = STAGE.build_accounts

                def damaged(connection, real_build=real_build, damage=damage):
                    """Build accounts as usual, then damage the table the way the label says."""
                    real_build(connection)
                    connection.execute(damage)

                with mock.patch.object(STAGE, "build_accounts", damaged), mock.patch.object(STAGE, "write_output") as writer:
                    with self.assertRaises(SystemExit) as caught:
                        STAGE.run_stage(con, src, out)
                self.assertIn("inconsistent input, nothing written", str(caught.exception), label)
                writer.assert_not_called()
                self.assertFalse(out.parent.exists(), label)


if __name__ == "__main__":
    unittest.main()
