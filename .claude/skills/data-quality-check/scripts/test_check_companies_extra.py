"""Tests for check_companies_extra.py and context/contracts/companies.yml: unit cases, a clean synthetic layer, and injected-fault mutations."""
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_companies_extra as extra  # noqa: E402
import check_contract as runner  # noqa: E402

CONTRACT_PATH = extra.REPO_ROOT / "context" / "contracts" / "companies.yml"
HOSTS_PLACEHOLDER = "data/silver/hosts.parquet"
HOST_SCHEMA = ("identity_source VARCHAR, name_norm VARCHAR, host_ip VARCHAR, port BIGINT, country_code VARCHAR, org VARCHAR, "
               "org_norm VARCHAR, cert_subject_o VARCHAR, is_noise BOOLEAN")
SYNTHETIC_HOSTS = [
    ("org", "acme", "1.1.1.1", 80, "US", "Acme Inc.", "acme", None, False),
    ("org", "acme", "1.1.1.1", 443, "US", "Acme Inc.", "acme", None, False),
    ("org", "acme", "1.1.1.2", 80, "CA", "ACME INC.", "acme", None, False),
    ("cert_o", "acme", "2.2.2.2", 443, "US", "Amazon.com, Inc.", "amazon com", "Acme Inc.", False),
    ("noise", None, "1.1.1.3", 23, "US", "Acme Inc.", "acme", None, True),
    ("org", "beta", "3.3.3.1", 22, "DE", "BETA LLC", "beta", None, False),
    ("org", "beta", "3.3.3.2", 22, "AT", "Beta LLC", "beta", None, False),
    ("cert_o", "gamma", "4.4.4.4", 443, "FR", "OVH SAS", "ovh sas", "Gamma Corp", False),
    ("org", "delta", "5.5.5.5", 80, None, "Delta Ltd", "delta", None, False),
    ("noise", None, "6.6.6.2", 23, "US", "Amazon.com, Inc.", "amazon com", None, True),
    ("null_org", None, "7.7.7.7", 80, "US", None, None, None, False),
] + [("infrastructure_unresolved", None, f"8.8.{i // 250}.{i % 250}", 80, "US", "Amazon.com, Inc.", "amazon com", None, False) for i in range(40)]

# Independent stand-in for the stage, written as plain SQL over the synthetic hosts table (a second implementation of D8).
STAGE_SQL = """
CREATE TABLE c AS
WITH m AS (SELECT * FROM h WHERE identity_source IN ('org', 'cert_o')),
g AS (SELECT name_norm, count(*) FILTER (WHERE identity_source = 'org') AS o, count(*) FILTER (WHERE identity_source = 'cert_o') AS k,
      count(DISTINCT host_ip) AS ips, count(DISTINCT port) AS ports, count(DISTINCT country_code) AS cc FROM m GROUP BY 1),
txt AS (SELECT name_norm, CASE WHEN identity_source = 'org' THEN org ELSE cert_subject_o END AS t, identity_source FROM m),
pick AS (SELECT name_norm, arg_min(t, (-n, t = upper(t), t)) AS nm FROM
         (SELECT x.name_norm, x.t, count(*) AS n FROM txt x JOIN g USING (name_norm)
          WHERE x.identity_source = CASE WHEN g.o > 0 THEN 'org' ELSE 'cert_o' END GROUP BY 1, 2) GROUP BY 1),
ctry AS (SELECT name_norm, arg_min(country_code, (-n, country_code)) AS cty FROM
         (SELECT name_norm, country_code, count(*) AS n FROM m WHERE country_code IS NOT NULL GROUP BY 1, 2) GROUP BY 1),
nz AS (SELECT org_norm AS name_norm, count(*) AS z FROM h WHERE is_noise AND org_norm IS NOT NULL GROUP BY 1)
SELECT substr(sha256(g.name_norm), 1, 16) AS company_id, pick.nm AS company_name, g.name_norm,
       CASE WHEN g.o > 0 THEN 'org' ELSE 'cert_o' END AS identity_source, CASE WHEN g.o > 0 THEN 'high' ELSE 'low' END AS identity_confidence,
       g.o::INTEGER AS org_host_count, g.k::INTEGER AS cert_o_host_count, (g.o + g.k)::INTEGER AS host_count, g.ips::INTEGER AS distinct_host_ips,
       g.ports::INTEGER AS distinct_port_count, ctry.cty AS country_code, g.cc::INTEGER AS country_count,
       coalesce(nz.z, 0)::INTEGER AS noise_host_count, coalesce(nz.z, 0)::DOUBLE / (coalesce(nz.z, 0) + g.o + g.k) AS noise_host_share
FROM g JOIN pick USING (name_norm) LEFT JOIN ctry USING (name_norm) LEFT JOIN nz USING (name_norm)
"""

# (name, SQL statements on table c, detectors that must fail). Detector "contract" is companies.yml, "extra" is check_companies_extra.
MUTATIONS = [
    ("duplicate company_id", ["UPDATE c SET company_id = (SELECT company_id FROM c WHERE name_norm = 'acme') WHERE name_norm = 'delta'"], ("contract", "extra")),
    ("wrong hash", ["UPDATE c SET company_id = '0123456789abcdef' WHERE name_norm = 'acme'"], ("contract", "extra")),
    ("host_count off by one", ["UPDATE c SET host_count = host_count + 1 WHERE name_norm = 'acme'"], ("contract", "extra")),
    ("host_count and org_host_count off by one together", ["UPDATE c SET host_count = host_count + 1, org_host_count = org_host_count + 1 "
                                                          "WHERE name_norm = 'beta'"], ("contract", "extra")),
    ("denylisted name_norm", ["UPDATE c SET name_norm = 'cloudflare', company_id = substr(sha256('cloudflare'), 1, 16), "
                              "company_name = 'Cloudflare, Inc.' WHERE name_norm = 'delta'"], ("contract", "extra")),
    ("confidence high with org_host_count 0", ["UPDATE c SET identity_confidence = 'high' WHERE name_norm = 'gamma'"], ("contract",)),
    ("sum(host_count) mismatch by a missing company", ["DELETE FROM c WHERE name_norm = 'delta'"], ("contract", "extra")),
    ("source label flipped", ["UPDATE c SET identity_source = 'cert_o' WHERE name_norm = 'acme'"], ("contract", "extra")),
    ("noise attribution dropped (share consistent)", ["UPDATE c SET noise_host_count = 0, noise_host_share = 0 WHERE name_norm = 'acme'"], ("extra",)),
    ("noise on a company with no org host", ["UPDATE c SET noise_host_count = 1, noise_host_share = 0.5 WHERE name_norm = 'gamma'"], ("contract", "extra")),
    ("noise_host_share above 1", ["UPDATE c SET noise_host_share = 1.5 WHERE name_norm = 'acme'"], ("contract", "extra")),
    ("country majority wrong", ["UPDATE c SET country_code = 'ZZ' WHERE name_norm = 'acme'"], ("extra",)),
    ("company_name tie-break wrong", ["UPDATE c SET company_name = 'BETA LLC' WHERE name_norm = 'beta'"], ("extra",)),
    ("phantom company absent from hosts", ["INSERT INTO c SELECT substr(sha256('ghost'), 1, 16), 'Ghost', 'ghost', identity_source, identity_confidence, "
                                           "org_host_count, cert_o_host_count, host_count, distinct_host_ips, distinct_port_count, country_code, "
                                           "country_count, noise_host_count, noise_host_share FROM c WHERE name_norm = 'delta'"], ("contract", "extra")),
    ("distinct_host_ips above host_count", ["UPDATE c SET distinct_host_ips = 9 WHERE name_norm = 'delta'"], ("contract", "extra")),
    ("empty company_name", ["UPDATE c SET company_name = ' ' WHERE name_norm = 'delta'"], ("contract", "extra")),
]


def write_layers(directory, mutation_sql=()):
    """Write synthetic hosts.parquet and companies.parquet (with optional mutation statements) into a directory; return both paths."""
    con = duckdb.connect()
    con.execute(f"CREATE TABLE h ({HOST_SCHEMA})")
    con.executemany("INSERT INTO h VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", SYNTHETIC_HOSTS)
    con.execute(STAGE_SQL)
    for statement in mutation_sql:
        con.execute(statement)
    hosts_path = Path(directory) / "hosts.parquet"
    companies_path = Path(directory) / "companies.parquet"
    con.execute(f"COPY h TO '{hosts_path.as_posix()}' (FORMAT PARQUET)")
    con.execute(f"COPY c TO '{companies_path.as_posix()}' (FORMAT PARQUET)")
    return hosts_path, companies_path


def run_contract(hosts_path, companies_path):
    """Run companies.yml against a companies file, with the hosts path of the cross-file checks pointed at hosts_path; return results."""
    text = CONTRACT_PATH.read_text(encoding="utf-8").replace(HOSTS_PLACEHOLDER, Path(hosts_path).as_posix())
    contract = yaml.safe_load(text)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM {runner.source_sql(companies_path)}")
    results = []
    for step in (runner.check_columns, runner.check_key, runner.check_row_rule, runner.check_denylist, runner.check_infra_reason,
                 runner.check_shares, runner.check_custom):
        step(con, contract, results)
    return results


def run_extra(hosts_path, companies_path):
    """Run the extra checks and return their results list."""
    return extra.run_checks(hosts_path, companies_path)[0]


def failures(results):
    """Return the names of failed checks."""
    return [name for name, ok, _ in results if not ok]


class UnitTests(unittest.TestCase):
    """Small pure-function cases."""

    def test_quantile_disc_returns_actual_values(self):
        """Discrete quantile picks element ceil(q n) - 1."""
        values = [1, 1, 1, 2, 10]
        self.assertEqual((extra.quantile_disc(values, 0.5), extra.quantile_disc(values, 0.9), extra.quantile_disc(values, 0.99)), (1, 10, 10))

    def test_display_name_prefers_frequent_then_mixed_case_then_bytes(self):
        """Most frequent wins; a tie goes to the not-all-upper text; then byte order."""
        self.assertEqual(extra.display_name([("org", "A Co"), ("org", "A Co"), ("org", "A CO")], True), "A Co")
        self.assertEqual(extra.display_name([("org", "BETA LLC"), ("org", "Beta LLC")], True), "Beta LLC")
        self.assertEqual(extra.display_name([("org", "b"), ("org", "a")], True), "a")

    def test_display_name_ignores_cert_text_when_an_org_host_exists(self):
        """With any org host the display name comes from org text only."""
        self.assertEqual(extra.display_name([("org", "Org Name"), ("cert_o", "Cert Name"), ("cert_o", "Cert Name")], True), "Org Name")
        self.assertEqual(extra.display_name([("cert_o", "Cert Name")], False), "Cert Name")

    def test_reference_matches_hand_computed_values(self):
        """The reference recomputation gives the hand-computed acme and beta rows."""
        rows = [dict(zip(("identity_source", "name_norm", "host_ip", "port", "country_code", "org", "org_norm", "cert_subject_o", "is_noise"), r))
                for r in SYNTHETIC_HOSTS]
        ref = extra.reference_companies(rows)
        acme = ref["acme"]
        self.assertEqual((acme["host_count"], acme["org_host_count"], acme["cert_o_host_count"], acme["distinct_host_ips"], acme["distinct_port_count"]),
                         (4, 3, 1, 3, 2))
        self.assertEqual((acme["country_code"], acme["country_count"], acme["noise_host_count"], acme["company_name"]), ("US", 2, 1, "Acme Inc."))
        self.assertAlmostEqual(acme["noise_host_share"], 0.2)
        self.assertEqual((ref["beta"]["country_code"], ref["beta"]["company_name"]), ("AT", "Beta LLC"))
        self.assertEqual((ref["gamma"]["identity_confidence"], ref["delta"]["country_code"], ref["delta"]["country_count"]), ("low", None, 0))
        self.assertEqual(set(ref), {"acme", "beta", "gamma", "delta"})


class CleanLayerTests(unittest.TestCase):
    """A correct synthetic layer must pass both detectors."""

    def test_clean_layer_passes_contract_and_extra(self):
        """Contract and extra checks both pass on a layer built by the independent SQL stand-in."""
        with tempfile.TemporaryDirectory() as tmp:
            hosts_path, companies_path = write_layers(tmp)
            self.assertEqual(failures(run_contract(hosts_path, companies_path)), [])
            self.assertEqual(failures(run_extra(hosts_path, companies_path)), [])

    def test_synthetic_denylist_names_are_really_denylisted(self):
        """The name used by the denylist mutation is matched by the shared rules (guards the test itself)."""
        matcher = extra.load_matcher()
        self.assertIsNotNone(matcher.match_name("cloudflare", "org", matcher.load_rules()))
        self.assertIsNone(matcher.match_name("acme inc.", "org", matcher.load_rules()))


class MutationTests(unittest.TestCase):
    """Every injected fault must make the named detector fail."""

    def test_each_mutation_is_caught(self):
        """For each fault the detectors named in MUTATIONS report at least one failed check."""
        self.assertGreaterEqual(len(MUTATIONS), 6)
        for name, statements, detectors in MUTATIONS:
            with self.subTest(fault=name), tempfile.TemporaryDirectory() as tmp:
                hosts_path, companies_path = write_layers(tmp, statements)
                found = {"contract": failures(run_contract(hosts_path, companies_path)), "extra": failures(run_extra(hosts_path, companies_path))}
                for detector in detectors:
                    self.assertTrue(found[detector], f"{detector} did not catch: {name}")


if __name__ == "__main__":
    unittest.main()
