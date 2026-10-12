"""Tests for check_contract.py and check_hosts_extra.py: denylist modes, infra_reason values, shares, cert_o assertions, recompute rules."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_contract as cc  # noqa: E402
import check_hosts_extra as ex  # noqa: E402


def make_con(rows, columns=("name", "isp")):
    """Build a DuckDB table t from rows of strings (None allowed)."""
    con = duckdb.connect()
    cols = ", ".join(f'"{c}" VARCHAR' for c in columns)
    con.execute(f"CREATE TABLE t ({cols})")
    marks = ", ".join("?" for _ in columns)
    for row in rows:
        con.execute(f"INSERT INTO t VALUES ({marks})", list(row))
    return con


def run(check, con, contract):
    """Run one check function and return its results list."""
    results = []
    check(con, contract, results)
    return results


def flagged(names, **extra):
    """Return the (ok, evidence) of the shared-rules denylist check over the given names."""
    con = make_con([(n, None) for n in names])
    contract = {"denylist": {"column": "name", "rules": "shared", **extra}}
    ((_, ok, evidence),) = run(cc.check_denylist, con, contract)
    return ok, evidence


class OldFormTests(unittest.TestCase):
    """The old {column, file} form keeps working."""

    def contract_for(self, names_text="# c\namazon.com, inc.\ngoogle llc\n"):
        """Write a small exact-names file in a temp dir (cleaned up after the test) and return a contract using it."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        file = tmp / "deny.txt"
        file.write_text(names_text, encoding="utf-8")
        return {"denylist": {"column": "name", "file": str(file)}}

    def test_old_fails_on_exact_and_variant(self):
        """Exact, case, punctuation and accent variants are caught."""
        con = make_con([("AMAZON.COM INC", None), ("Gôogle LLC", None), ("Stripe", None)])
        ((_, ok, ev),) = run(cc.check_denylist, con, self.contract_for())
        self.assertFalse(ok)
        self.assertIn("2 distinct", ev)

    def test_old_passes_clean(self):
        """A clean column passes."""
        con = make_con([("Stripe", None), ("Acme Bank", None)])
        ((_, ok, _),) = run(cc.check_denylist, con, self.contract_for())
        self.assertTrue(ok)

    def test_old_does_not_use_prefix_rules(self):
        """Old form is exact only: a prefix family is not flagged."""
        con = make_con([("Microsoft Azure", None)])
        ((_, ok, _),) = run(cc.check_denylist, con, self.contract_for())
        self.assertTrue(ok)

    def test_missing_file_fails_loudly(self):
        """A missing exact file fails with a message, never passes."""
        con = make_con([("Stripe", None)])
        contract = self.contract_for()
        contract["denylist"]["file"] += ".missing"
        ((_, ok, ev),) = run(cc.check_denylist, con, contract)
        self.assertFalse(ok)
        self.assertIn("cannot load", ev)


class SharedModeTests(unittest.TestCase):
    """The new {column, rules: shared} form applies every pipeline rule."""

    def test_exact(self):
        """An exact denylist name is caught."""
        ok, ev = flagged(["Google LLC"])
        self.assertFalse(ok)
        self.assertIn("exact", ev)

    def test_prefix_family(self):
        """A prefix family member is caught."""
        ok, ev = flagged(["Microsoft Azure"])
        self.assertFalse(ok)
        self.assertIn("prefix", ev)

    def test_pattern(self):
        """A CIDR text and a glob in the column are caught."""
        for name in ("139.162.0.0/16", "host-se5-ptk-01"):
            ok, ev = flagged([name])
            self.assertFalse(ok, name)
            self.assertIn("pattern", ev)

    def test_org_keyword(self):
        """An org-scoped keyword (telecom) and a plain keyword (hosting) are caught."""
        for name in ("Acme Telecom Ltd", "Krystal Hosting Ltd"):
            ok, ev = flagged([name])
            self.assertFalse(ok, name)
            self.assertIn("keyword", ev)

    def test_accented_variant(self):
        """Accented spellings fold onto the rule."""
        for name in ("Telefónica Chile", "Microsóft Corporation"):
            ok, _ = flagged([name])
            self.assertFalse(ok, name)

    def test_real_company_not_flagged(self):
        """Real companies pass, including near-miss words (ghosting is excluded from the *hosting compound rule; webhosting is matched by design)."""
        ok, ev = flagged(["Stripe, Inc.", "Acme Bank", "OVHTECH", "Ghosting Media", "Vpnsoft"])
        self.assertTrue(ok, ev)

    def test_reports_at_most_five_examples(self):
        """Evidence lists no more than five example names and the matched rule type."""
        ok, ev = flagged([f"Microsoft Unit {i}" for i in range(9)])
        self.assertFalse(ok)
        self.assertIn("9 distinct", ev)
        self.assertEqual(ev.count("[prefix"), 5)

    def test_isp_text_not_matched(self):
        """The check reads the named column only; telecom text in an isp column is ignored."""
        con = make_con([("Stripe", "Acme Telecom Ltd"), ("Acme Bank", "Microsoft Azure")])
        ((_, ok, _),) = run(cc.check_denylist, con, {"denylist": {"column": "name", "rules": "shared"}})
        self.assertTrue(ok)

    def test_missing_rule_file_fails_loudly(self):
        """A context dir without rule files fails with a readable message."""
        tmp = tempfile.mkdtemp()
        try:
            ok, ev = flagged(["Stripe"], context_dir=tmp)
            self.assertFalse(ok)
            self.assertIn("cannot load", ev)
        finally:
            shutil.rmtree(tmp)

    def test_missing_matcher_fails_loudly(self):
        """A checker copied where scripts/denylist_match.py does not exist reports a failure, not a pass."""
        tmp = Path(tempfile.mkdtemp())
        try:
            dest = tmp / ".claude" / "skills" / "data-quality-check" / "scripts"
            dest.mkdir(parents=True)
            shutil.copy(HERE / "check_contract.py", dest)
            probe = (
                "import sys, duckdb\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "import check_contract as cc\n"
                "con = duckdb.connect()\n"
                "con.execute(\"CREATE TABLE t AS SELECT 'x' AS name\")\n"
                "r = []\n"
                "cc.check_denylist(con, {'denylist': {'column': 'name', 'rules': 'shared'}}, r)\n"
                "print(r)\n"
            )
            out = subprocess.run([sys.executable, "-c", probe, str(dest)], capture_output=True, text=True)
            self.assertIn("False", out.stdout, out.stderr)
            self.assertIn("cannot import shared matcher", out.stdout)
        finally:
            shutil.rmtree(tmp)

    def test_runs_from_other_directory(self):
        """The script runs from a different working directory and finds the matcher."""
        tmp = Path(tempfile.mkdtemp())
        try:
            data = tmp / "d.parquet"
            duckdb.connect().execute(f"COPY (SELECT 'Microsoft Azure' AS name) TO '{data.as_posix()}' (FORMAT PARQUET)")
            contract = tmp / "c.yml"
            contract.write_text(f"layer: x\npath: {data.as_posix()}\ndenylist: {{column: name, rules: shared}}\n")
            out = subprocess.run([sys.executable, str(HERE / "check_contract.py"), str(contract)],
                                 capture_output=True, text=True, cwd=tmp)
            self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
            self.assertIn("prefix", out.stdout)
        finally:
            shutil.rmtree(tmp)


class InfraReasonTests(unittest.TestCase):
    """The infra_reason value check."""

    def test_allowed_values_pass(self):
        """Every INFRA_REASONS value passes, nulls allowed by default."""
        values = ("cloud_provider", "tag_rule", "ip_pattern", "org_exact", "org_prefix", "org_pattern", "org_keyword", None)
        con = make_con([(v,) for v in values], ("infra_reason",))
        ((_, ok, _),) = run(cc.check_infra_reason, con, {"infra_reason": {}})
        self.assertTrue(ok)

    def test_isp_and_unknown_values_fail(self):
        """isp_* and unknown values fail."""
        con = make_con([("isp_exact",), ("org_exact",), ("bogus",)], ("infra_reason",))
        ((_, ok, ev),) = run(cc.check_infra_reason, con, {"infra_reason": {}})
        self.assertFalse(ok)
        self.assertIn("isp_exact", ev)
        self.assertIn("bogus", ev)

    def test_nullable_false_flags_nulls(self):
        """nullable: false fails on nulls."""
        con = make_con([(None,)], ("infra_reason",))
        ((_, ok, _),) = run(cc.check_infra_reason, con, {"infra_reason": {"nullable": False}})
        self.assertFalse(ok)


class SharesTests(unittest.TestCase):
    """The identity_source share check."""

    @staticmethod
    def rows(org, other):
        """Return rows with the given counts of org and null_org identity_source."""
        return [("org",)] * org + [("null_org",)] * other

    def test_in_range_passes(self):
        """A 14% resolved share passes inside 5 to 20."""
        con = make_con(self.rows(14, 86), ("identity_source",))
        rule = {"shares": {"column": "identity_source", "allowed": ["org", "null_org"],
                           "resolved_values": ["org"], "resolved_min": 5, "resolved_max": 20}}
        self.assertTrue(all(ok for _, ok, _ in run(cc.check_shares, con, rule)))

    def test_out_of_range_and_nulls_fail(self):
        """A 50% share fails the range and a null identity_source fails the sum check."""
        rule = {"shares": {"column": "identity_source", "resolved_values": ["org"], "resolved_min": 5, "resolved_max": 20}}
        res = run(cc.check_shares, make_con(self.rows(50, 50), ("identity_source",)), rule)
        self.assertFalse(res[1][1])
        res = run(cc.check_shares, make_con([(None,), ("org",)], ("identity_source",)), rule)
        self.assertFalse(res[0][1])


class CertOAssertionTests(unittest.TestCase):
    """The cert_o assertions and the independent recompute rules of check_hosts_extra.py (D6)."""

    @classmethod
    def setUpClass(cls):
        """Load the real shared matcher, rules and cert defaults once."""
        cls.matcher = ex.load_matcher()
        cls.rules = cls.matcher.load_rules()
        cls.defaults = cls.matcher.load_cert_defaults()

    def usable(self, name):
        """Return cert_usable for a name with the real rules."""
        return ex.cert_usable(name, self.matcher, self.rules, self.defaults)

    def test_usable_tenant_and_rejections(self):
        """A tenant is usable; a default, a keyword hit, an exact hit, a prefix hit, an empty string and None are not."""
        self.assertTrue(self.usable("Accenture"))
        self.assertFalse(self.usable("Plesk"))          # cert default
        self.assertFalse(self.usable("Bouygues Telecom"))  # keyword rule (D6.4: keywords apply to cert O)
        self.assertFalse(self.usable("Google LLC"))     # exact rule
        self.assertFalse(self.usable("Microsoft Azure"))  # prefix rule
        self.assertFalse(self.usable("   "))
        self.assertFalse(self.usable(None))

    def test_recompute_flags_precedence(self):
        """Noise wins, then org, then cert_o for infrastructure or null-org rows, then unresolved, then null_org."""
        def flags(**kw):
            """Return recompute_flags for a row with defaults overridden by kw."""
            row = {"host_ip": "8.8.4.4", "org": None, "tags": [], "cp": None, "module": None, "cert_o": None}
            row.update(kw)
            return ex.recompute_flags(row, self.matcher, self.rules, self.defaults)
        self.assertEqual(flags(tags=["honeypot"], org="Stripe")[2], "noise")
        self.assertEqual(flags(org="Stripe, Inc.")[2:], ("org", "stripe"))
        self.assertEqual(flags(org="Google LLC", cert_o="Accenture")[2:], ("cert_o", "accenture"))
        self.assertEqual(flags(cert_o="Accenture")[2], "cert_o")      # null org, usable cert O
        self.assertEqual(flags(org="Google LLC", cert_o="Plesk")[2], "infrastructure_unresolved")
        self.assertEqual(flags()[2], "null_org")

    def test_noise_module_pattern(self):
        """The D6.1 pattern flags rat modules, njrat and blackshades, and not njrat78 or xiaongmai-backdoor."""
        for module, want in (("darktrack-rat", True), ("njrat", True), ("blackshades", True), ("rat", True),
                             ("njrat78", False), ("xiaongmai-backdoor", False), ("pirate", False)):
            row = {"host_ip": "8.8.4.4", "org": "Stripe", "tags": [], "cp": None, "module": module, "cert_o": None}
            self.assertEqual(ex.recompute_flags(row, self.matcher, self.rules, self.defaults)[1], want, module)

    def hosts_con(self, rows):
        """Build a hosts table (identity_source, name_norm, cert_subject_o) from rows."""
        con = make_con(rows, ("identity_source", "name_norm", "cert_subject_o"))
        con.execute("CREATE VIEW hosts AS SELECT * FROM t")
        return con

    def test_assertion_a_catches_default_name(self):
        """A cert_o row whose name_norm is a cert default is reported; a tenant and a non-cert_o row are not."""
        con = self.hosts_con([("cert_o", "plesk", "Plesk"), ("cert_o", "accenture", "Accenture"), ("org", "plesk", None)])
        self.assertEqual(ex.cert_o_default_rows(con, self.matcher, self.defaults), [("plesk", 1)])

    def test_assertion_a_clean(self):
        """No default names gives an empty list."""
        con = self.hosts_con([("cert_o", "accenture", "Accenture")])
        self.assertEqual(ex.cert_o_default_rows(con, self.matcher, self.defaults), [])

    def test_assertion_b_disagreements(self):
        """Rows only I classify as cert_o, only the stage does, and a differing name are each reported."""
        mine = {("1", 1, "tcp"): "a", ("2", 1, "tcp"): "b", ("3", 1, "tcp"): "c"}
        parquet = [(("1", 1, "tcp"), "cert_o", "a"), (("2", 1, "tcp"), "infrastructure_unresolved", None),
                   (("3", 1, "tcp"), "cert_o", "other"), (("4", 1, "tcp"), "cert_o", "d")]
        only_mine, only_theirs, names = ex.cert_o_disagreements(mine, parquet)
        self.assertEqual(only_mine, [("2", 1, "tcp")])
        self.assertEqual(only_theirs, [("4", 1, "tcp")])
        self.assertEqual(names, [("3", 1, "tcp")])

    def test_cert_invalid(self):
        """Dates outside 1990..2100, unparseable text and an invalid month are invalid; valid and null dates are not."""
        self.assertFalse(ex.cert_invalid("20300101000000Z", "20200101000000Z"))
        self.assertFalse(ex.cert_invalid(None, None))
        self.assertTrue(ex.cert_invalid("20300101000000Z", "19700101000000Z"))
        self.assertTrue(ex.cert_invalid("40960101000000Z", None))
        self.assertTrue(ex.cert_invalid("garbage", None))
        self.assertTrue(ex.cert_invalid("20301301000000Z", None))


if __name__ == "__main__":
    unittest.main(verbosity=1)
