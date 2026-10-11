"""Unit tests for pipeline/1_clean.py on a tiny synthetic JSONL (stdlib unittest, no pandas)."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import duckdb

STAGE_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "1_clean.py"
SPEC = importlib.util.spec_from_file_location("clean_stage", STAGE_PATH)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)

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


if __name__ == "__main__":
    unittest.main()
