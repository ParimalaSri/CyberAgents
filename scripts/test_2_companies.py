"""Unit tests for pipeline/2_companies.py on a tiny synthetic hosts parquet (stdlib unittest, no pandas)."""
import contextlib
import hashlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import duckdb

STAGE_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "2_companies.py"
SPEC = importlib.util.spec_from_file_location("companies_stage", STAGE_PATH)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)
GUARD_SUPPORT_SPEC = importlib.util.spec_from_file_location("guard_test_support", Path(__file__).resolve().parent / "guard_test_support.py")
GUARD_SUPPORT = importlib.util.module_from_spec(GUARD_SUPPORT_SPEC)
GUARD_SUPPORT_SPEC.loader.exec_module(GUARD_SUPPORT)

COLUMNS = ("host_ip", "port", "org", "org_norm", "country_code", "cert_subject_o", "is_noise", "identity_source", "name_norm")


def host(ip, port=443, org=None, norm=None, country="US", cert=None, noise=False, source="org", name=None):
    """Return one synthetic hosts row tuple; name defaults to norm for org rows."""
    return (ip, port, org, norm, country, cert, noise, source, name if name is not None else (norm if source == "org" else None))


def run_hosts(rows):
    """Write rows as a hosts parquet in a temp dir, run the stage, and return (companies as dicts, counts)."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "hosts.parquet"
        dst = Path(tmp) / "companies.parquet"
        con = duckdb.connect()
        con.execute("CREATE TABLE h(host_ip VARCHAR, port BIGINT, org VARCHAR, org_norm VARCHAR, country_code VARCHAR, "
                    "cert_subject_o VARCHAR, is_noise BOOLEAN, identity_source VARCHAR, name_norm VARCHAR)")
        con.executemany("INSERT INTO h VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        con.execute(f"COPY h TO '{src.as_posix()}' (FORMAT PARQUET)")
        counts = STAGE.run_stage(con, src, dst)
        cur = con.execute(f"SELECT * FROM read_parquet('{dst.as_posix()}')")
        names = [d[0] for d in cur.description]
        companies = [dict(zip(names, r)) for r in cur.fetchall()]
        return companies, counts, names, con


def by_name(companies):
    """Index company dicts by name_norm."""
    return {c["name_norm"]: c for c in companies}


class CompaniesStageTests(unittest.TestCase):
    """Behaviour of the grouping rules on synthetic hosts rows."""

    def test_exact_name_grouping(self):
        """Rows with equal name_norm form one company; different names stay apart (no fuzzy merge)."""
        companies, _, _, _ = run_hosts([
            host("1.1.1.1", org="Acme Inc", norm="acme"), host("1.1.1.2", org="ACME, Inc.", norm="acme"),
            host("1.1.1.3", org="Acme Systems", norm="acme systems"), host("1.1.1.4", org="Acme Bakery", norm="acme bakery"),
        ])
        index = by_name(companies)
        self.assertEqual(len(companies), 3)
        self.assertEqual(index["acme"]["host_count"], 2)

    def test_org_and_cert_o_merge(self):
        """A name under org and under cert_o is one company with source org, confidence high and the split kept."""
        companies, _, _, _ = run_hosts([
            host("1.1.1.1", org="Fiserv", norm="fiserv"),
            host("1.1.1.2", org=None, source="cert_o", cert="Fiserv, Inc.", name="fiserv"),
        ])
        self.assertEqual(len(companies), 1)
        row = companies[0]
        self.assertEqual((row["identity_source"], row["identity_confidence"]), ("org", "high"))
        self.assertEqual((row["org_host_count"], row["cert_o_host_count"], row["host_count"]), (1, 1, 2))
        self.assertEqual(row["company_name"], "Fiserv")

    def test_non_member_sources_never_create_companies(self):
        """noise, infrastructure_unresolved and null_org rows create no company and do not enter host_count."""
        companies, counts, _, _ = run_hosts([
            host("1.1.1.1", org="Acme", norm="acme"),
            host("2.2.2.2", org="Evil", norm="evil", noise=True, source="noise", name=None),
            host("3.3.3.3", org="Amazon", norm="amazon", source="infrastructure_unresolved", name=None),
            host("4.4.4.4", org=None, norm=None, source="null_org", name=None),
        ])
        self.assertEqual([c["name_norm"] for c in companies], ["acme"])
        self.assertEqual(companies[0]["host_count"], 1)
        self.assertEqual(counts["hosts_rows"], 4)

    def test_singleton_and_confidence_rule(self):
        """A singleton is kept; confidence is low iff the company has no org host."""
        companies, _, _, _ = run_hosts([
            host("1.1.1.1", org="Solo", norm="solo"),
            host("2.2.2.2", org=None, source="cert_o", cert="Certonly Ltd", name="certonly"),
            host("2.2.2.3", org=None, source="cert_o", cert="Certonly Ltd", name="certonly"),
        ])
        index = by_name(companies)
        self.assertEqual((index["solo"]["host_count"], index["solo"]["identity_confidence"]), (1, "high"))
        self.assertEqual((index["certonly"]["identity_source"], index["certonly"]["identity_confidence"]), ("cert_o", "low"))
        self.assertEqual(index["certonly"]["host_count"], 2)

    def test_display_name_most_frequent_then_not_upper_then_bytes(self):
        """company_name is the most frequent raw text; ties go to not-all-upper, then byte order."""
        companies, _, _, _ = run_hosts([
            host("1.0.0.1", org="Beta Corp", norm="beta"), host("1.0.0.2", org="Beta Corp", norm="beta"), host("1.0.0.3", org="BETA CORP", norm="beta"),
            host("2.0.0.1", org="SERVICENOW, INC.", norm="servicenow"), host("2.0.0.2", org="ServiceNow, Inc.", norm="servicenow"),
            host("3.0.0.1", org="Zeta Ltd", norm="zeta"), host("3.0.0.2", org="Zeta Limited", norm="zeta"),
        ])
        index = by_name(companies)
        self.assertEqual(index["beta"]["company_name"], "Beta Corp")
        self.assertEqual(index["servicenow"]["company_name"], "ServiceNow, Inc.")
        self.assertEqual(index["zeta"]["company_name"], "Zeta Limited")

    def test_display_name_prefers_org_text_over_cert_text(self):
        """When a company has any org host the cert O text is not a display candidate, even if more frequent."""
        companies, _, _, _ = run_hosts([
            host("1.0.0.1", org="Acme Co", norm="acme"),
            host("1.0.0.2", org=None, source="cert_o", cert="ACME, INC.", name="acme"),
            host("1.0.0.3", org=None, source="cert_o", cert="ACME, INC.", name="acme"),
        ])
        self.assertEqual(companies[0]["company_name"], "Acme Co")

    def test_company_id_is_stable_sha256_prefix(self):
        """company_id equals the first 16 hex characters of sha256(name_norm) and is identical across row orders."""
        rows = [host("1.1.1.1", org="Acme", norm="acme"), host("1.1.1.2", org="Zoho", norm="zoho"), host("1.1.1.3", org="美的集团", norm="美的集团")]
        first, _, _, _ = run_hosts(rows)
        second, _, _, _ = run_hosts(list(reversed(rows)))
        for row in first:
            self.assertEqual(row["company_id"], hashlib.sha256(row["name_norm"].encode("utf-8")).hexdigest()[:16])
        self.assertEqual(sorted(r["company_id"] for r in first), sorted(r["company_id"] for r in second))
        self.assertEqual([r["company_id"] for r in first], sorted(r["company_id"] for r in first))

    def test_host_count_sums_to_member_rows(self):
        """sum(host_count) equals the member rows; org plus cert_o counts equal host_count."""
        companies, _, _, _ = run_hosts([
            host("1.1.1.1", org="A", norm="a"), host("1.1.1.1", port=80, org="A", norm="a"), host("1.1.1.2", org="B", norm="b"),
            host("1.1.1.3", org=None, source="cert_o", cert="C", name="c"), host("9.9.9.9", org="X", norm="x", noise=True, source="noise", name=None),
        ])
        self.assertEqual(sum(c["host_count"] for c in companies), 4)
        for c in companies:
            self.assertEqual(c["host_count"], c["org_host_count"] + c["cert_o_host_count"])
            self.assertTrue(1 <= c["distinct_host_ips"] <= c["host_count"])
            self.assertTrue(1 <= c["distinct_port_count"] <= c["host_count"])
        self.assertEqual(by_name(companies)["a"]["distinct_host_ips"], 1)
        self.assertEqual(by_name(companies)["a"]["distinct_port_count"], 2)

    def test_country_majority_tie_and_nulls(self):
        """country_code is the majority non-null country, ties go to the smallest code, all-null gives null and count 0."""
        companies, _, _, _ = run_hosts([
            host("1.0.0.1", org="M", norm="m", country="US"), host("1.0.0.2", org="M", norm="m", country="DE"), host("1.0.0.3", org="M", norm="m", country="DE"),
            host("2.0.0.1", org="T", norm="t", country="US"), host("2.0.0.2", org="T", norm="t", country="BR"),
            host("3.0.0.1", org="N", norm="n", country=None),
        ])
        index = by_name(companies)
        self.assertEqual((index["m"]["country_code"], index["m"]["country_count"]), ("DE", 2))
        self.assertEqual(index["t"]["country_code"], "BR")
        self.assertEqual((index["n"]["country_code"], index["n"]["country_count"]), (None, 0))

    def test_noise_attribution_by_org_norm(self):
        """Noise rows attach to a company through org_norm, stay out of host_count, and a cert_o-only company gets 0."""
        companies, _, _, _ = run_hosts([
            host("1.0.0.1", org="Radio", norm="radio"), host("1.0.0.2", org="Radio", norm="radio"),
            host("1.0.0.3", org="Radio", norm="radio", noise=True, source="noise", name=None),
            host("1.0.0.4", org="Radio", norm="radio", noise=True, source="noise", name=None),
            host("1.0.0.5", org="Radio", norm="radio", noise=True, source="noise", name=None),
            host("2.0.0.1", org=None, source="cert_o", cert="Certco", name="certco"),
            host("2.0.0.2", org="Elsewhere", norm="elsewhere", noise=True, source="noise", name=None),
        ])
        index = by_name(companies)
        self.assertEqual((index["radio"]["host_count"], index["radio"]["noise_host_count"]), (2, 3))
        self.assertAlmostEqual(index["radio"]["noise_host_share"], 3 / 5)
        self.assertEqual((index["certco"]["noise_host_count"], index["certco"]["noise_host_share"]), (0, 0.0))
        self.assertNotIn("elsewhere", index)

    def test_no_fan_out_and_companies_le_hosts(self):
        """company_id and name_norm are unique, the file has 14 columns in order, and companies <= hosts."""
        rows = [host(f"10.0.0.{i}", org=f"Org {i % 4}", norm=f"org {i % 4}") for i in range(12)]
        rows.append(host("9.9.9.9", org="E", norm="e", noise=True, source="noise", name=None))
        companies, counts, names, _ = run_hosts(rows)
        self.assertEqual(len({c["company_id"] for c in companies}), len(companies))
        self.assertEqual(len({c["name_norm"] for c in companies}), len(companies))
        self.assertLessEqual(counts["companies_rows"], counts["hosts_rows"])
        self.assertEqual(tuple(names), STAGE.KEY_COLUMNS)
        self.assertEqual(len(names), 14)

    def test_report_runs_and_reconciles(self):
        """The D8.7 report prints, asserts the reconciliation and writes a markdown file on a small fixture."""
        rows = [
            host("1.0.0.1", org="Acme", norm="acme"), host("1.0.0.2", org=None, source="cert_o", cert="Certco", name="certco"),
            host("2.0.0.1", org="Amazon", norm="amazon", source="infrastructure_unresolved", name=None),
            host("3.0.0.1", org="E", norm="e", noise=True, source="noise", name=None), host("4.0.0.1", org=None, source="null_org", name=None),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            companies, _, _, con = run_hosts(rows)
            out = Path(tmp) / "c.parquet"
            STAGE.write_output(con, out)
            con.execute("ALTER TABLE hosts ADD COLUMN is_infrastructure BOOLEAN DEFAULT false")
            con.execute("ALTER TABLE hosts ADD COLUMN infra_reason VARCHAR")
            con.execute("UPDATE hosts SET is_infrastructure = true, infra_reason = 'org_exact' WHERE identity_source = 'infrastructure_unresolved'")
            report = Path(tmp) / "report.md"
            with contextlib.redirect_stdout(io.StringIO()):
                STAGE.print_report(con, out, report)
            text = report.read_text(encoding="utf-8")
        self.assertIn("cannot be attributed to a customer", text)
        self.assertIn("Row-count reconciliation", text)
        self.assertEqual(len(companies), 2)

    def test_full_flag_parses(self):
        """The constants for --full differ from the dev paths and main wires the flag."""
        self.assertNotEqual(STAGE.FULL_HOSTS_PATH, STAGE.HOSTS_PATH)
        self.assertNotEqual(STAGE.FULL_OUTPUT_PATH, STAGE.OUTPUT_PATH)
        source = STAGE_PATH.read_text(encoding="utf-8")
        self.assertIn('"--full"', source)


ROOT_DIR = Path(__file__).resolve().parent.parent


def run_cli(args, env=None):
    """Run the stage script as a subprocess and return the completed process (text output, UTF-8 decoded)."""
    return subprocess.run([sys.executable, str(STAGE_PATH), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=dict(os.environ, **(env or {})))


def dq_listing(prefix):
    """Return (name, mtime) pairs of the committed stage reports so a test can prove they were not touched."""
    dq = ROOT_DIR / "outputs" / "dq"
    return sorted((f.name, f.stat().st_mtime_ns) for f in dq.glob(prefix + "_stage_*.md")) if dq.exists() else []

HOSTS_CLI_DDL = ("host_ip VARCHAR, port BIGINT, org VARCHAR, org_norm VARCHAR, country_code VARCHAR, cert_subject_o VARCHAR, is_noise BOOLEAN, "
                 "identity_source VARCHAR, name_norm VARCHAR, is_infrastructure BOOLEAN, infra_reason VARCHAR")


def write_hosts(path, rows):
    """Write host tuples (the run_hosts shape plus infra flags) as a hosts parquet with the columns the report reads."""
    con = duckdb.connect()
    con.execute(f"CREATE TABLE h ({HOSTS_CLI_DDL})")
    for row in rows:
        infra = row[7] == "infrastructure_unresolved"
        con.execute("INSERT INTO h VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [*row, infra, "org_exact" if infra else None])
    con.execute(f"COPY h TO '{Path(path).as_posix()}' (FORMAT PARQUET)")


class CliRobustnessTests(unittest.TestCase):
    """QA findings 2, 3, 7, 8 for the companies stage: zero rows, report path, UTF-8 report, output path guard."""

    def run_hosts_cli(self, rows, env=None):
        """Run the CLI on a hosts file made from rows; return (process, company rows or None, report path next to the output)."""
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "hosts.parquet"), Path(tmp, "companies.parquet")
            write_hosts(src, rows)
            result = run_cli(["--input", src, "--output", out], env=env)
            count = duckdb.connect().execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchone()[0] if out.exists() else None
            return result, count, Path(tmp, "companies_stage_report.md").exists()

    def test_zero_row_batches_complete(self):
        """Empty, all-noise, all-infrastructure and all-null-org hosts files complete with exit code 0 and zero companies."""
        cases = {
            "empty": [],
            "noise": [host(f"1.1.1.{i}", noise=True, source="noise", norm=f"n{i}") for i in range(3)],
            "infra": [host(f"1.1.1.{i}", org=f"Cloudy {i}", norm=f"cloudy {i}", source="infrastructure_unresolved", name="") for i in range(3)],
            "null_org": [host(f"1.1.1.{i}", source="null_org") for i in range(3)],
        }
        for name, rows in cases.items():
            result, count, has_report = self.run_hosts_cli(rows)
            self.assertEqual((result.returncode, count, has_report), (0, 0, True), (name, result.stderr[-500:]))
        self.assertIn("rows: 0", self.run_hosts_cli([])[0].stdout)

    def test_zero_member_reconciliation_arithmetic(self):
        """With no companies the reconciliation still asserts sum(host_count) = member rows (0 = 0)."""
        result, _, _ = self.run_hosts_cli([host("1.1.1.1", source="null_org")])
        self.assertIn("sum(host_count) = 0 equals member rows (asserted)", result.stdout)

    def test_report_goes_next_to_scratch_output(self):
        """With a non-default --output and no --report the report sits beside the output; --report overrides; the committed reports are untouched."""
        before = dq_listing("companies")
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "hosts.parquet"), Path(tmp, "sub", "companies.parquet")
            write_hosts(src, [host("1.1.1.1", org="Acme", norm="acme")])
            self.assertEqual(run_cli(["--input", src, "--output", out]).returncode, 0)
            self.assertTrue(Path(tmp, "sub", "companies_stage_report.md").exists())
            custom = Path(tmp, "elsewhere", "my_report.md")
            self.assertEqual(run_cli(["--input", src, "--output", out, "--report", custom]).returncode, 0)
            self.assertTrue(custom.exists())
        self.assertEqual(before, dq_listing("companies"))

    def test_default_output_keeps_committed_report_path(self):
        """With the default output the report path is the committed outputs/dq path."""
        guard = STAGE.load_guard()
        default_report = STAGE.REPORT_DIR / "companies_stage_2026-01-01.md"
        self.assertEqual(guard.choose_report_path(str(STAGE.OUTPUT_PATH), STAGE.OUTPUT_PATH, None, default_report, "companies"), default_report)

    def test_cjk_name_under_cp1252_pipe(self):
        """A CJK company name does not break the report under the default Windows pipe encoding."""
        name = "\u682a\u5f0f\u4f1a\u793e\u30c6\u30b9\u30c8"
        result, count, _ = self.run_hosts_cli([host("1.1.1.1", org=name, norm=name)], env={"PYTHONIOENCODING": "cp1252"})
        self.assertEqual((result.returncode, count), (0, 1), result.stderr[-500:])

    def test_output_under_raw_or_dataset_folder_refused(self):
        """Outputs (and reports) under scratch stand-ins for data/raw and the dataset folder, in every path form, are refused and nothing is written."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "hosts.parquet")
            write_hosts(src, [host("1.1.1.1", org="Acme", norm="acme")])
            GUARD_SUPPORT.assert_stage_refuses(self, STAGE, ["--input", src], with_report=True, safe_dir=tmp)


    def test_inconsistent_input_exits_cleanly_before_writing(self):
        """A hosts file with an unknown identity_source exits with a readable message and leaves no output or report behind."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "hosts.parquet")
            write_hosts(src, [host("1.1.1.1", org="Acme", norm="acme", source="bogus")])
            out, report = Path(tmp, "o", "companies.parquet"), Path(tmp, "r", "report.md")
            code, _, _ = GUARD_SUPPORT.run_main(STAGE, ["--input", src, "--output", out, "--report", report], GUARD_SUPPORT.load_guard())
            self.assertIsInstance(code, str)
            self.assertIn("inconsistent input, nothing written", code)
            self.assertIn("unexpected identity_source", code)
            self.assertFalse(out.parent.exists())
            self.assertFalse(report.exists())
            result = run_cli(["--input", src, "--output", out])
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out.exists())




def write_hosts_custom(path, rows):
    """Write full-width host tuples (the 11 columns of HOSTS_CLI_DDL, infra flags given by the caller) as a hosts parquet."""
    con = duckdb.connect()
    con.execute(f"CREATE TABLE h ({HOSTS_CLI_DDL})")
    for row in rows:
        con.execute("INSERT INTO h VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", list(row))
    con.execute(f"COPY h TO '{Path(path).as_posix()}' (FORMAT PARQUET)")


EXTRA_COMPANY = "SELECT '{i}', 'X', '{i}', 'org', 'high', 0, 0, 0, 0, 0, NULL, 0, 0, 0.0"


class PreWriteConsistencyTests(unittest.TestCase):
    """Every pre-write consistency check of stage 2 refuses an input that breaks only that check: message, exit code 1, nothing written."""

    def run_checked(self, rows, tamper=None, expect=""):
        """Run main in process on rows (optionally tampering with table companies right after it is built); assert a clean refusal and no files."""
        with tempfile.TemporaryDirectory() as tmp:
            src, out, report = Path(tmp, "hosts.parquet"), Path(tmp, "o", "companies.parquet"), Path(tmp, "r", "report.md")
            write_hosts_custom(src, rows)
            original = STAGE.build_companies

            def build_then_tamper(con):
                """Build companies, then apply the tampering SQL."""
                original(con)
                if tamper:
                    con.execute(tamper)

            with mock.patch.object(STAGE, "build_companies", build_then_tamper), mock.patch.object(STAGE, "write_output") as writer:
                code, _, _ = GUARD_SUPPORT.run_main(STAGE, ["--input", src, "--output", out, "--report", report], GUARD_SUPPORT.load_guard())
            self.assertIsInstance(code, str)
            self.assertIn("inconsistent input, nothing written", code)
            self.assertIn(expect, code)
            writer.assert_not_called()
            self.assertFalse(out.parent.exists())
            self.assertFalse(report.parent.exists())
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["hosts.parquet"])

    def test_null_identity_source(self):
        """A NULL identity_source is an unexpected value."""
        self.run_checked([("1.1.1.1", 443, "A", "a", "US", None, False, None, "a", False, None)], expect="unexpected identity_source")

    def test_unknown_identity_source(self):
        """A value outside the five identity sources is refused."""
        self.run_checked([("1.1.1.1", 443, "A", "a", "US", None, False, "bogus", "a", False, None)], expect="unexpected identity_source")

    def test_infra_reason_outside_contract_set(self):
        """An infrastructure row with an infra_reason outside the contract set is refused."""
        row = ("1.1.1.1", 443, "A", "a", "US", None, False, "infrastructure_unresolved", None, True, "made_up")
        self.run_checked([row], expect="infra_reason values outside")

    def test_infra_reason_null_on_infrastructure_row(self):
        """An infrastructure row with a NULL infra_reason is refused."""
        row = ("1.1.1.1", 443, "A", "a", "US", None, False, "infrastructure_unresolved", None, True, None)
        self.run_checked([row], expect="infra_reason values outside")

    def test_missing_report_columns_refused_by_the_cli(self):
        """A hosts file without is_infrastructure or infra_reason is refused before the write (it used to fail in the report, after the write)."""
        with tempfile.TemporaryDirectory() as tmp:
            src, out, report = Path(tmp, "hosts.parquet"), Path(tmp, "o", "companies.parquet"), Path(tmp, "r", "report.md")
            con = duckdb.connect()
            con.execute("CREATE TABLE h(host_ip VARCHAR, port BIGINT, org VARCHAR, org_norm VARCHAR, country_code VARCHAR, cert_subject_o VARCHAR, "
                        "is_noise BOOLEAN, identity_source VARCHAR, name_norm VARCHAR)")
            con.execute("INSERT INTO h VALUES ('1.1.1.1', 443, 'A', 'a', 'US', NULL, false, 'org', 'a')")
            con.execute(f"COPY h TO '{src.as_posix()}' (FORMAT PARQUET)")
            result = run_cli(["--input", src, "--output", out, "--report", report])
            self.assertEqual(result.returncode, 1)
            self.assertIn("lacks is_infrastructure or infra_reason", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out.parent.exists())
            self.assertFalse(report.parent.exists())

    def test_companies_exceed_hosts(self):
        """One company more than hosts rows (unique keys, matching host_count sum) is refused; two more as well."""
        rows = [("1.1.1.1", 443, "A", "a", "US", None, False, "org", "a", False, None)]
        self.run_checked(rows, "INSERT INTO companies " + EXTRA_COMPANY.format(i="x1"), "companies 2 exceed hosts rows 1")
        tamper = "INSERT INTO companies " + EXTRA_COMPANY.format(i="x1") + " UNION ALL " + EXTRA_COMPANY.format(i="x2")
        self.run_checked(rows, tamper, "exceed hosts rows")

    def test_company_id_not_unique(self):
        """A duplicated company_id (distinct name_norm, counts unchanged, companies <= hosts) is refused."""
        rows = [("1.1.1.%d" % i, 443, "A", "a", "US", None, False, "org", "a", False, None) for i in range(3)]
        tamper = "INSERT INTO companies SELECT company_id, 'Y', 'y', identity_source, identity_confidence, 0, 0, 0, 0, 0, NULL, 0, 0, 0.0 FROM companies"
        self.run_checked(rows, tamper, "not unique")

    def test_name_norm_not_unique(self):
        """A duplicated name_norm (distinct company_id, counts unchanged, companies <= hosts) is refused."""
        rows = [("1.1.1.%d" % i, 443, "A", "a", "US", None, False, "org", "a", False, None) for i in range(3)]
        tamper = "INSERT INTO companies SELECT 'zz', 'Y', name_norm, identity_source, identity_confidence, 0, 0, 0, 0, 0, NULL, 0, 0, 0.0 FROM companies"
        self.run_checked(rows, tamper, "not unique")

    def test_host_count_sum_differs_from_member_rows(self):
        """sum(host_count) different from the member rows (companies <= hosts, keys unique) is refused."""
        rows = [("1.1.1.%d" % i, 443, "A", "a", "US", None, False, "org", "a", False, None) for i in range(3)]
        self.run_checked(rows, "UPDATE companies SET host_count = host_count + 1", "sum(host_count)")

    def test_never_create_plus_member_rows_must_equal_hosts_rows(self):
        """The reconciliation function reports an imbalance and stays quiet on a balanced input (unreachable through data once identity_source is checked)."""
        self.assertIsNone(STAGE.reconcile_rows({"org": 2, "noise": 1, "null_org": 3}, 6))
        self.assertIn("!=", STAGE.reconcile_rows({"org": 2, "noise": 1}, 4))
        self.assertIn("!=", STAGE.reconcile_rows({"cert_o": 2, "org": 1}, 2))
        self.assertIsNone(STAGE.reconcile_rows({}, 0))

    def test_check_consistency_calls_reconcile_rows(self):
        """check_consistency exits through reconcile_rows when it reports an imbalance (wiring check)."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "hosts.parquet")
            write_hosts_custom(src, [("1.1.1.1", 443, "A", "a", "US", None, False, "org", "a", False, None)])
            con = duckdb.connect()
            STAGE.build_members(con, src)
            STAGE.build_companies(con)
            STAGE.check_consistency(con)
            with mock.patch.object(STAGE, "reconcile_rows", return_value="forced imbalance"):
                with self.assertRaises(SystemExit) as caught:
                    STAGE.check_consistency(con)
            self.assertIn("forced imbalance", str(caught.exception))
            self.assertIn("nothing written", str(caught.exception))

    def test_refusal_exits_with_code_one_in_a_process(self):
        """As a process, a refused input exits with code 1 and a readable message, no traceback."""
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "hosts.parquet"), Path(tmp, "o", "companies.parquet")
            write_hosts_custom(src, [("1.1.1.1", 443, "A", "a", "US", None, False, None, "a", False, None)])
            result = run_cli(["--input", src, "--output", out])
            self.assertEqual(result.returncode, 1)
            self.assertIn("nothing written", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out.parent.exists())


if __name__ == "__main__":
    unittest.main()
