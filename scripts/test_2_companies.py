"""Unit tests for pipeline/2_companies.py on a tiny synthetic hosts parquet (stdlib unittest, no pandas)."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

import duckdb

STAGE_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "2_companies.py"
SPEC = importlib.util.spec_from_file_location("companies_stage", STAGE_PATH)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)

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


if __name__ == "__main__":
    unittest.main()
