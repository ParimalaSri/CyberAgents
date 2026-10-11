"""Unit tests for pipeline/1_clean.py on a tiny synthetic JSONL (stdlib unittest, no pandas)."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import itertools
import unittest
from pathlib import Path

import duckdb

STAGE_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "1_clean.py"
SPEC = importlib.util.spec_from_file_location("clean_stage", STAGE_PATH)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)
GUARD_SUPPORT_SPEC = importlib.util.spec_from_file_location("guard_test_support", Path(__file__).resolve().parent / "guard_test_support.py")
GUARD_SUPPORT = importlib.util.module_from_spec(GUARD_SUPPORT_SPEC)
GUARD_SUPPORT_SPEC.loader.exec_module(GUARD_SUPPORT)

BASE = {"ip_str": "8.8.4.4", "port": 443, "transport": "tcp", "timestamp": "2026-09-14T10:00:00.000000",
        "org": "Kent State University", "_shodan": {"module": "https"}, "tags": ["x"]}


def make_row(**over):
    """Return a raw row dict: BASE with overrides applied."""
    row = json.loads(json.dumps(BASE))
    row.update(over)
    return row


def run_rows(rows):
    """Run the stage on rows in a temp dir; return a list of dicts for the silver table plus the counts."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.jsonl"
        src.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        dst = Path(tmp) / "out.parquet"
        con = duckdb.connect()
        counts = STAGE.run_stage(con, src, dst)
        cur = con.execute(f"SELECT * FROM read_parquet('{dst.as_posix()}') ORDER BY host_ip, port, transport, timestamp")
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()], counts, names


class CleanStageTests(unittest.TestCase):
    """Behaviour of the stage rules on synthetic rows."""

    def test_dedupe_keeps_latest_timestamp(self):
        """Two rows with the same key collapse to the later one."""
        rows, counts, _ = run_rows([
            make_row(timestamp="2026-09-14T10:00:00.000000", product="old"),
            make_row(timestamp="2026-09-14T10:30:00.000000", product="new"),
            make_row(port=80),
        ])
        self.assertEqual(len(rows), 2)
        self.assertEqual(counts["flagged_rows"] - counts["out_rows"], 1)
        kept = [r for r in rows if r["port"] == 443][0]
        self.assertEqual(kept["product"], "new")

    def test_dedupe_tie_is_deterministic(self):
        """Equal timestamps give the same winner whatever the input order."""
        first = make_row(product="a")
        second = make_row(product="b")
        out_a, _, _ = run_rows([first, second])
        out_b, _, _ = run_rows([second, first])
        self.assertEqual(out_a[0]["product"], out_b[0]["product"])

    def test_ipv6_fallback(self):
        """host_ip uses ipv6 when ip_str is missing, and rows with neither are dropped."""
        v6 = make_row(ipv6="2001:db8::1")
        del v6["ip_str"]
        nothing = make_row(port=22)
        del nothing["ip_str"]
        rows, counts, _ = run_rows([v6, nothing])
        self.assertEqual([r["host_ip"] for r in rows], ["2001:db8::1"])
        self.assertEqual(counts["no_host_ip"], 1)

    def test_sentinel_cert_dates_nulled(self):
        """Certificate dates in year 4096, 0001 or 1970 become null; a normal date survives."""
        def cert(expires, issued):
            """Build an ssl struct with the two dates."""
            return {"cert": {"expires": expires, "issued": issued, "expired": False, "subject": {"O": None, "CN": None}}, "versions": ["TLSv1.2"]}
        rows, _, _ = run_rows([
            make_row(port=1, ssl=cert("40960101000000Z", "19700101000000Z")),
            make_row(port=2, ssl=cert("00010101000000Z", "00010101000000Z")),
            make_row(port=3, ssl=cert("20270105120000Z", "20250105120000Z")),
        ])
        by_port = {r["port"]: r for r in rows}
        self.assertIsNone(by_port[1]["cert_expires"])
        self.assertIsNone(by_port[1]["cert_issued"])
        self.assertIsNone(by_port[2]["cert_expires"])
        self.assertIsNotNone(by_port[3]["cert_expires"])
        self.assertEqual(by_port[3]["cert_expires"].year, 2027)

    def test_noise_precedence(self):
        """Honeypot tag and RAT module rows are noise even when the org would resolve; infrastructure is still flagged."""
        rows, _, _ = run_rows([
            make_row(port=1, tags=["honeypot"]),
            make_row(port=2, _shodan={"module": "orcus-rat"}),
            make_row(port=3, org="Google LLC", tags=["tor"]),
            make_row(port=4),
        ])
        by_port = {r["port"]: r for r in rows}
        for port in (1, 2, 3):
            self.assertTrue(by_port[port]["is_noise"])
            self.assertEqual(by_port[port]["identity_source"], "noise")
            self.assertIsNone(by_port[port]["name_norm"])
        self.assertTrue(by_port[3]["is_infrastructure"])
        self.assertFalse(by_port[4]["is_noise"])

    def test_identity_source_order(self):
        """org, cert_o, infrastructure_unresolved and null_org follow D4 order, and the cert default list is respected."""
        cert_o = {"cert": {"expires": None, "issued": None, "expired": False, "subject": {"O": "Fiserv, Inc.", "CN": None}}, "versions": None}
        cert_default = {"cert": {"expires": None, "issued": None, "expired": False, "subject": {"O": "Internet Widgits Pty Ltd", "CN": None}}, "versions": None}
        rows, _, _ = run_rows([
            make_row(port=1),
            make_row(port=2, org="Google LLC", ssl=cert_o),
            make_row(port=3, org="Google LLC", ssl=cert_default),
            make_row(port=4, org=None),
            make_row(port=5, org="Google LLC", ssl=cert_o, tags=["honeypot"]),
        ])
        by_port = {r["port"]: r for r in rows}
        self.assertEqual(by_port[1]["identity_source"], "org")
        self.assertEqual(by_port[1]["name_norm"], "kent state university")
        self.assertEqual(by_port[2]["identity_source"], "cert_o")
        self.assertEqual(by_port[2]["name_norm"], "fiserv")
        self.assertEqual(by_port[3]["identity_source"], "infrastructure_unresolved")
        self.assertEqual(by_port[4]["identity_source"], "null_org")
        self.assertEqual(by_port[5]["identity_source"], "noise")
        for row in rows:
            self.assertIn(row["identity_source"], STAGE.IDENTITY_SOURCES)

    def test_infra_reason_values_and_precedence(self):
        """infra_reason is null or inside INFRA_REASONS; cloud provider beats tag beats org; isp alone never excludes."""
        matcher = STAGE.load_matcher()
        rows, _, _ = run_rows([
            make_row(port=1, cloud={"provider": "Google"}, tags=["cloud"], org="Google LLC"),
            make_row(port=2, tags=["cdn"], org="Google LLC"),
            make_row(port=3, org="Google LLC"),
            make_row(port=4, org="Kent State University", isp="Google LLC"),
            make_row(port=5, ip_str="139.162.5.5", org="Somebody Else"),
        ])
        by_port = {r["port"]: r for r in rows}
        self.assertEqual(by_port[1]["infra_reason"], "cloud_provider")
        self.assertEqual(by_port[2]["infra_reason"], "tag_rule")
        self.assertEqual(by_port[3]["infra_reason"], "org_exact")
        self.assertIsNone(by_port[4]["infra_reason"])
        self.assertFalse(by_port[4]["is_infrastructure"])
        self.assertEqual(by_port[5]["infra_reason"], "ip_pattern")
        for row in rows:
            self.assertEqual(row["is_infrastructure"], row["infra_reason"] is not None)
            if row["infra_reason"] is not None:
                self.assertIn(row["infra_reason"], matcher.INFRA_REASONS)

    def test_vulns_reduced_and_capped(self):
        """vulns become max_cvss, has_kev and a capped count."""
        vulns = {f"CVE-2020-{i}": {"cvss": 5.0, "kev": False} for i in range(STAGE.VULN_COUNT_CAP + 10)}
        vulns["CVE-2021-1"] = {"cvss": 9.8, "kev": True}
        rows, _, _ = run_rows([make_row(port=1, vulns=vulns), make_row(port=2)])
        by_port = {r["port"]: r for r in rows}
        self.assertEqual(by_port[1]["max_cvss"], 9.8)
        self.assertTrue(by_port[1]["has_kev"])
        self.assertEqual(by_port[1]["vuln_count"], STAGE.VULN_COUNT_CAP)
        self.assertIsNone(by_port[2]["max_cvss"])
        self.assertFalse(by_port[2]["has_kev"])
        self.assertEqual(by_port[2]["vuln_count"], 0)

    def test_no_raw_payload_columns(self):
        """The silver table has exactly the declared columns and no html, screenshot, data or http payload."""
        rows, _, names = run_rows([make_row(html="<html>", data="banner", screenshot={"data": "x"}, http={"html": "x"})])
        self.assertEqual(names, [n for n, _ in STAGE.OUTPUT_COLUMNS])
        for banned in ("html", "screenshot", "data", "http", "vulns", "ssl", "location", "cloud"):
            self.assertNotIn(banned, names)
        self.assertEqual(len(rows), 1)

    def test_key_unique_and_row_flow(self):
        """Output key is unique and raw rows equal output rows plus dropped plus duplicates."""
        rows, counts, _ = run_rows([make_row(), make_row(), make_row(port=80)])
        keys = {(r["host_ip"], r["port"], r["transport"]) for r in rows}
        self.assertEqual(len(keys), len(rows))
        self.assertEqual(counts["raw_rows"], 3)
        self.assertEqual(counts["out_rows"], 2)

    def test_noise_module_pattern(self):
        """Only the explicit RAT module names are noise; njrat78, xiaongmai-backdoor and 'moderate' are not."""
        modules = ["blackshades", "njrat", "darktrack-rat", "ghost-rat", "rat", "njrat78", "xiaongmai-backdoor", "moderate", "ratio"]
        rows, _, _ = run_rows([make_row(port=i + 1, _shodan={"module": m}) for i, m in enumerate(modules)])
        by_port = {r["port"]: r for r in rows}
        for i, module in enumerate(modules):
            expected = module in ("blackshades", "njrat", "darktrack-rat", "ghost-rat", "rat")
            self.assertEqual(by_port[i + 1]["is_noise"], expected, module)

    def test_cert_o_keyword_and_vendor_rejected(self):
        """A cert O that hits a keyword (telecom), a vendor default or the guard list is not usable; a real tenant is."""
        def cert(name):
            """Build an ssl struct with one subject O."""
            return {"cert": {"expires": None, "issued": None, "expired": False, "subject": {"O": name, "CN": None}}, "versions": None}
        rows, _, _ = run_rows([
            make_row(port=1, org="Google LLC", ssl=cert("Bouygues Telecom")),
            make_row(port=2, org="Google LLC", ssl=cert("Huawei Technologies")),
            make_row(port=3, org="Google LLC", ssl=cert("Meta Platforms, Inc.")),
            make_row(port=4, org="Google LLC", ssl=cert("Fiserv, Inc.")),
        ])
        by_port = {r["port"]: r for r in rows}
        for port in (1, 2, 3):
            self.assertEqual(by_port[port]["identity_source"], "infrastructure_unresolved", port)
            self.assertIsNone(by_port[port]["name_norm"])
        self.assertEqual(by_port[4]["identity_source"], "cert_o")

    def test_cert_o_applicability(self):
        """cert_o applies on infrastructure or null org, never when a non-infrastructure org exists (org wins)."""
        cert_o = {"cert": {"expires": None, "issued": None, "expired": False, "subject": {"O": "Fiserv, Inc.", "CN": None}}, "versions": None}
        rows, _, _ = run_rows([
            make_row(port=1, org="Google LLC", ssl=cert_o),
            make_row(port=2, org=None, ssl=cert_o),
            make_row(port=3, org="Kent State University", ssl=cert_o),
        ])
        by_port = {r["port"]: r for r in rows}
        self.assertEqual(by_port[1]["identity_source"], "cert_o")
        self.assertEqual(by_port[2]["identity_source"], "cert_o")
        self.assertEqual(by_port[3]["identity_source"], "org")
        self.assertEqual(by_port[3]["cert_subject_o"], "Fiserv, Inc.")

    def test_cert_date_invalid(self):
        """cert_date_invalid is true when a present date was nulled, false for valid or absent dates."""
        def cert(expires, issued):
            """Build an ssl struct with the two dates."""
            return {"cert": {"expires": expires, "issued": issued, "expired": False, "subject": {"O": None, "CN": None}}, "versions": None}
        rows, _, _ = run_rows([
            make_row(port=1, ssl=cert("40960101000000Z", "20250105120000Z")),
            make_row(port=2, ssl=cert("20270105120000Z", "19700101000000Z")),
            make_row(port=3, ssl=cert("20270105120000Z", "20250105120000Z")),
            make_row(port=4, ssl=cert(None, None)),
            make_row(port=5),
            make_row(port=6, ssl=cert("garbage", None)),
        ])
        by_port = {r["port"]: r["cert_date_invalid"] for r in rows}
        self.assertEqual(by_port, {1: True, 2: True, 3: False, 4: False, 5: False, 6: True})

    def test_dup_count_totals(self):
        """dup_count is at least 1 and sum(dup_count - 1) over kept rows equals the rows removed."""
        rows, counts, _ = run_rows([make_row(), make_row(), make_row(), make_row(port=80), make_row(port=81), make_row(port=81)])
        by_port = {r["port"]: r["dup_count"] for r in rows}
        self.assertEqual(by_port, {443: 3, 80: 1, 81: 2})
        self.assertEqual(sum(r["dup_count"] - 1 for r in rows), counts["flagged_rows"] - counts["out_rows"])

    def test_vuln_cap_keeps_cvss_and_kev(self):
        """The count cap never changes max_cvss or has_kev, even when the top CVE is the last of many."""
        vulns = {f"CVE-2020-{i}": {"cvss": 4.0, "kev": False} for i in range(STAGE.VULN_COUNT_CAP * 3)}
        vulns["CVE-2099-1"] = {"cvss": 10.0, "kev": True}
        rows, _, _ = run_rows([make_row(vulns=vulns)])
        self.assertEqual(rows[0]["vuln_count"], STAGE.VULN_COUNT_CAP)
        self.assertEqual(rows[0]["max_cvss"], 10.0)
        self.assertTrue(rows[0]["has_kev"])

    def test_full_default_output_is_separate(self):
        """--full defaults to hosts_full.parquet, the sample default stays hosts.parquet, an explicit path wins."""
        self.assertEqual(Path(STAGE.resolve_output(None, True)).name, "hosts_full.parquet")
        self.assertEqual(Path(STAGE.resolve_output(None, False)).name, "hosts.parquet")
        self.assertNotEqual(STAGE.resolve_output(None, True), STAGE.resolve_output(None, False))
        self.assertEqual(STAGE.resolve_output("x/y.parquet", True), "x/y.parquet")


ROOT_DIR = Path(__file__).resolve().parent.parent


def run_cli(args, env=None):
    """Run the stage script as a subprocess and return the completed process (text output, UTF-8 decoded)."""
    return subprocess.run([sys.executable, str(STAGE_PATH), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=dict(os.environ, **(env or {})))


def cert_row(port, expires, issued):
    """Return a raw row with a certificate carrying the two date strings."""
    return make_row(port=port, ssl={"cert": {"expires": expires, "issued": issued, "expired": False, "subject": {"O": None, "CN": None}}, "versions": None})


class QaFixTests(unittest.TestCase):
    """QA findings 1, 5, 6: total dedupe tie-break, certificate year edges and the vuln cap pinned with literal values."""

    def test_dedupe_tie_total_over_every_column(self):
        """Rows with the same key and timestamp that differ only in vulns or hostnames give one output for all 6 input orders."""
        a = make_row(vulns={"CVE-1": {"cvss": 9.8, "kev": True}}, hostnames=["a.example"])
        b = make_row(vulns={"CVE-2": {"cvss": 2.0, "kev": False}}, hostnames=["b.example"])
        c = make_row(vulns={"CVE-3": {"cvss": 5.0, "kev": False}, "CVE-4": {"cvss": 1.0, "kev": False}}, hostnames=None, domains=["z.example"])
        outputs = set()
        for order in itertools.permutations([a, b, c]):
            rows, _, _ = run_rows(list(order))
            self.assertEqual(len(rows), 1)
            outputs.add((rows[0]["max_cvss"], rows[0]["has_kev"], rows[0]["vuln_count"], str(rows[0]["hostnames"]), str(rows[0]["domains"])))
        self.assertEqual(len(outputs), 1, outputs)

    def test_dedupe_tie_total_for_same_hash_columns_different_other_fields(self):
        """Rows that agree on org, isp, product, version, module, cert O and tags but differ in cert dates or country still tie-break identically."""
        a = make_row(location={"country_code": "DE"}, ssl={"cert": {"expires": "20300101000000Z", "issued": "20200101000000Z", "expired": False, "subject": {"O": None, "CN": "x"}}, "versions": None})
        b = make_row(location={"country_code": "FR"}, ssl={"cert": {"expires": "20310101000000Z", "issued": "20210101000000Z", "expired": False, "subject": {"O": None, "CN": "y"}}, "versions": None})
        first, _, _ = run_rows([a, b])
        second, _, _ = run_rows([b, a])
        self.assertEqual((first[0]["country_code"], first[0]["cert_subject_cn"]), (second[0]["country_code"], second[0]["cert_subject_cn"]))

    def test_certificate_year_edges(self):
        """Years 1990 and 2100 are kept; 1989 and 2101 are nulled and flagged invalid."""
        rows, _, _ = run_rows([
            cert_row(1, "19900101000000Z", "19900101000000Z"), cert_row(2, "21001231235959Z", "21001231235959Z"),
            cert_row(3, "19891231235959Z", "19891231235959Z"), cert_row(4, "21010101000000Z", "21010101000000Z"),
        ])
        by_port = {r["port"]: r for r in rows}
        self.assertEqual((by_port[1]["cert_expires"].year, by_port[1]["cert_issued"].year, by_port[1]["cert_date_invalid"]), (1990, 1990, False))
        self.assertEqual((by_port[2]["cert_expires"].year, by_port[2]["cert_issued"].year, by_port[2]["cert_date_invalid"]), (2100, 2100, False))
        self.assertEqual((by_port[3]["cert_expires"], by_port[3]["cert_issued"], by_port[3]["cert_date_invalid"]), (None, None, True))
        self.assertEqual((by_port[4]["cert_expires"], by_port[4]["cert_issued"], by_port[4]["cert_date_invalid"]), (None, None, True))

    def test_vuln_cap_literal_values(self):
        """The vuln count is 49 for 49 CVEs, 50 for 50 and 51 and 5000 (cap pinned at 50, not read from the constant)."""
        def vulns(n):
            """Return n synthetic CVE entries."""
            return {f"CVE-2020-{i}": {"cvss": 5.0, "kev": False} for i in range(n)}
        rows, _, _ = run_rows([make_row(port=1, vulns=vulns(49)), make_row(port=2, vulns=vulns(50)), make_row(port=3, vulns=vulns(51)),
                               make_row(port=4, vulns=vulns(5000))])
        self.assertEqual({r["port"]: r["vuln_count"] for r in rows}, {1: 49, 2: 50, 3: 50, 4: 50})


class CliRobustnessTests(unittest.TestCase):
    """QA findings 2, 7, 8 for the clean stage: zero rows, UTF-8 report under cp1252, output path guard."""

    def run_lines(self, lines, env=None):
        """Run the stage CLI on the given JSON lines; return (process, output path, rows in the output)."""
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp, "in.jsonl"), Path(tmp, "out.parquet")
            src.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in lines), encoding="utf-8")
            result = run_cli(["--input", src, "--output", out], env=env)
            rows = duckdb.connect().execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchone()[0] if out.exists() else None
            return result, rows

    def test_empty_input_file(self):
        """An empty input file completes with exit code 0 and a zero-row output and report."""
        result, rows = self.run_lines([])
        self.assertEqual((result.returncode, rows), (0, 0), result.stderr[-500:])
        self.assertIn("rows: 0", result.stdout)

    def test_all_noise_all_infrastructure_and_null_org(self):
        """Inputs that are all noise, all infrastructure or all blank-org complete with exit code 0."""
        cases = {
            "noise": [make_row(ip_str=f"8.8.4.{i}", tags=["honeypot"]) for i in range(1, 4)],
            "infra": [make_row(ip_str=f"8.8.4.{i}", tags=["cloud"], cloud={"provider": "aws"}) for i in range(1, 4)],
            "null_org": [make_row(ip_str="8.8.4.1", org=None), make_row(ip_str="8.8.4.2", org=""), make_row(ip_str="8.8.4.3", org="   ")],
        }
        for name, lines in cases.items():
            result, rows = self.run_lines(lines)
            self.assertEqual((result.returncode, rows), (0, 3), (name, result.stderr[-500:]))

    def test_cjk_org_under_cp1252_pipe(self):
        """A CJK org name does not break the report under the default Windows pipe encoding."""
        result, rows = self.run_lines([make_row(org="\u682a\u5f0f\u4f1a\u793e\u30c6\u30b9\u30c8")], env={"PYTHONIOENCODING": "cp1252"})
        self.assertEqual((result.returncode, rows), (0, 1), result.stderr[-500:])

    def test_output_under_raw_or_dataset_folder_refused(self):
        """Outputs (and reports) under scratch stand-ins for data/raw and the dataset folder, in every path form, are refused and nothing is written."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "in.jsonl")
            src.write_text(json.dumps(make_row()) + "\n", encoding="utf-8")
            GUARD_SUPPORT.assert_stage_refuses(self, STAGE, ["--input", src], with_report=False, safe_dir=tmp)


if __name__ == "__main__":
    unittest.main()
