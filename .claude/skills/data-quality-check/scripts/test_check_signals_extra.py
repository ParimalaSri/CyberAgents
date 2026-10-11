"""Tests for check_signals_extra.py and context/contracts/signals.yml: unit cases, a clean synthetic layer, and injected-fault mutations."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_contract as runner  # noqa: E402
import check_signals_extra as extra  # noqa: E402

CONTRACT_PATH = extra.REPO_ROOT / "context" / "contracts" / "signals.yml"
HOSTS_PLACEHOLDER = "data/silver/hosts.parquet"
COMPANIES_PLACEHOLDER = "data/silver/companies.parquet"
TS = datetime(2026, 10, 11, 10, 0, 0)
HOST_SCHEMA = ("identity_source VARCHAR, name_norm VARCHAR, host_ip VARCHAR, port BIGINT, transport VARCHAR, timestamp TIMESTAMP, "
               "tags VARCHAR[], ssl_versions VARCHAR[], cert_expires TIMESTAMP, cert_expired BOOLEAN, max_cvss DOUBLE, has_kev BOOLEAN")


def host(source, name, ip, port, transport="tcp", tags=(), ssl=(), expires=None, expired=False, cvss=None, kev=False):
    """Build one synthetic hosts row tuple."""
    return (source, name, ip, port, transport, TS, list(tags), list(ssl), expires, expired, cvss, kev)


SYNTHETIC_HOSTS = [
    # acme: org, several risks on different hosts; one host is risky AND eol (exposed_and_outdated on the same host)
    host("org", "acme", "1.1.1.1", 22, ssl=["TLSv1"], expired=True, cvss=9.8, kev=True),
    host("org", "acme", "1.1.1.2", 3389, tags=["eol-os"], cvss=7.0),
    host("org", "acme", "1.1.1.3", 80, tags=["database"], cvss=5.0),
    # gamma: cert_o only, every host cdn-tagged: host-blind, but the cert signal still uses its hosts
    host("cert_o", "gamma", "2.2.2.1", 443, tags=["cdn"], expires=TS + timedelta(days=10), cvss=9.9, kev=True),
    host("cert_o", "gamma", "2.2.2.2", 443, tags=["cdn"]),
    # delta: cert_o, one counted host; cert_expires exactly 30 days ahead (inclusive edge); risky port 445; cvss 8.9
    host("cert_o", "delta", "3.3.3.3", 445, expires=TS + timedelta(days=30), cvss=8.9),
    # beta: org singleton; cert_expires equal to the scan time (exclusive edge, not counted); '-SSLv3' is not offered
    host("org", "beta", "4.4.4.1", 22, ssl=["-SSLv3", "TLSv1.2"], expires=TS),
    # epsilon servers: T1 name; risky 6379 host is eol and cvss 9.0; port 22 over udp is not risky; null country
    host("org", "epsilon servers", "5.5.5.1", 6379, tags=["eol-product"], cvss=9.0),
    host("org", "epsilon servers", "5.5.5.2", 22, transport="udp"),
    # rackhost: T2-only name; sensitive tag; cvss 6.9 (band 1); port 9200 risky but no eol and cvss below 7
    host("org", "rackhost", "6.6.6.1", 80, tags=["iot"], cvss=6.9),
    host("org", "rackhost", "6.6.6.2", 9200),
    # quiet corp: nothing at all
    host("org", "quiet corp", "7.7.7.1", 80),
    # mixed cert: one clean counted host plus one cdn-tagged host with kev and a risky port (must not count)
    host("cert_o", "mixed cert", "8.8.8.1", 80),
    host("cert_o", "mixed cert", "8.8.8.2", 3389, tags=["cdn"], cvss=9.9, kev=True),
    # kappa: cvss exactly 7.0 (band 2 edge)
    host("org", "kappa", "9.9.9.1", 80, cvss=7.0),
    # hosts that never join: noise and infrastructure rows carry no name_norm
    host("noise", None, "10.0.0.1", 23, kev=True, cvss=10.0),
    host("infrastructure_unresolved", None, "10.0.0.2", 3389, kev=True, cvss=10.0),
] + [host("org", "bigco", f"11.0.0.{i}", 80) for i in range(25)] + [host("org", "midco", f"12.0.0.{i}", 80) for i in range(8)]

# name_norm -> (company_name, country_code, noise_host_count)
SYNTHETIC_COMPANIES = {
    "acme": ("Acme Inc.", "US", 1), "gamma": ("Gamma Corp", "FR", 0), "delta": ("Delta Ltd", "DE", 0), "beta": ("Beta LLC", "DE", 0),
    "epsilon servers": ("Epsilon Servers", None, 0), "rackhost": ("Rackhost Zrt.", "JP", 0), "quiet corp": ("Quiet Corp", "US", 0),
    "mixed cert": ("Mixed Cert Ltd", "GB", 0), "kappa": ("Kappa SA", "BR", 0), "bigco": ("BigCo", "US", 0), "midco": ("MidCo", "CA", 0),
}

COMPANIES_SQL = """
CREATE TABLE c AS
SELECT substr(sha256(m.name_norm), 1, 16) AS company_id, k.company_name, m.name_norm,
       CASE WHEN m.o > 0 THEN 'org' ELSE 'cert_o' END AS identity_source, CASE WHEN m.o > 0 THEN 'high' ELSE 'low' END AS identity_confidence,
       m.n::INTEGER AS host_count, m.ips::INTEGER AS distinct_host_ips, k.country_code, k.noise::INTEGER AS noise_host_count,
       k.noise::DOUBLE / (k.noise + m.n) AS noise_host_share
FROM (SELECT name_norm, count(*) AS n, count(DISTINCT host_ip) AS ips, sum(CASE WHEN identity_source = 'org' THEN 1 ELSE 0 END) AS o
      FROM h WHERE identity_source IN ('org', 'cert_o') AND name_norm IS NOT NULL GROUP BY 1) m JOIN k USING (name_norm)
"""

# A second implementation of D9.4 in SQL (scalar sums), used only to build clean and faulty synthetic signals files.
SIGNALS_SQL = """
CREATE TABLE s AS
WITH f AS (
  SELECT name_norm, port, max_cvss, coalesce(has_kev, false) AS kev, {counted} AS ctd,
         list_has_any(coalesce(tags, []::VARCHAR[]), ['eol-product', 'eol-os']) AS eol,
         list_has_any(coalesce(tags, []::VARCHAR[]), ['database', 'ics', 'medical', 'iot']) AS sens,
         list_has_any(coalesce(ssl_versions, []::VARCHAR[]), ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']) AS leg,
         (transport = 'tcp' AND port IN (22, 3389, 445, 3306, 6379, 27017, 9200, 5900, 23, 2375)) AS rk,
         (transport = 'tcp' AND port IN (3389, 445, 3306, 6379, 27017, 9200, 5900, 23, 2375)) AS rk2,
         (coalesce(cert_expired, false) OR (cert_expires > timestamp AND cert_expires <= timestamp + INTERVAL 30 DAY)) AS cert
  FROM h WHERE identity_source IN ('org', 'cert_o') AND name_norm IS NOT NULL),
a AS (
  SELECT name_norm, sum(CASE WHEN ctd THEN 1 ELSE 0 END) AS n_ctd, sum(CASE WHEN ctd AND sens THEN 1 ELSE 0 END) AS n_sens,
         sum(CASE WHEN ctd AND kev THEN 1 ELSE 0 END) AS n_kev, max(CASE WHEN ctd THEN max_cvss END) AS cvss,
         sum(CASE WHEN cert THEN 1 ELSE 0 END) AS n_cert, sum(CASE WHEN ctd AND eol THEN 1 ELSE 0 END) AS n_eol,
         sum(CASE WHEN ctd AND leg THEN 1 ELSE 0 END) AS n_leg, sum(CASE WHEN ctd AND rk THEN 1 ELSE 0 END) AS n_rk,
         sum(CASE WHEN ctd AND rk2 THEN 1 ELSE 0 END) AS n_rk2,
         list_sort(list_distinct(list(port) FILTER (WHERE ctd AND rk))) AS ports,
         sum(CASE WHEN ctd AND rk AND (eol OR coalesce(max_cvss, 0) >= 7.0) THEN 1 ELSE 0 END) AS n_eo
  FROM f GROUP BY 1)
SELECT c.company_id, c.company_name, c.name_norm, c.identity_source, c.identity_confidence, c.host_count, c.distinct_host_ips, c.country_code,
       c.noise_host_count, c.noise_host_share,
       coalesce(a.n_ctd, 0)::INTEGER AS counted_host_count, coalesce(a.n_ctd, 0) = 0 AS host_signals_blind, c.host_count = 1 AS is_singleton,
       CASE WHEN c.country_code IS NULL THEN NULL ELSE c.country_code = 'US' END AS in_territory, c.identity_confidence = 'high' AS named_registrant,
       least(c.distinct_host_ips, 50)::INTEGER AS footprint_size,
       (CASE WHEN c.distinct_host_ips = 1 THEN 0 WHEN c.distinct_host_ips <= 5 THEN 1 WHEN c.distinct_host_ips <= 20 THEN 2 ELSE 3 END)::SMALLINT AS footprint_band,
       coalesce(a.n_sens, 0) > 0 AS sensitive_stack,
       regexp_matches(c.name_norm, '(^| )(internet|telekom|communications|hosting|hosted|servers?|broadband|cable|mobile|idc|infrastructure|research|telecom[a-z0-9]*|comunica[a-z0-9]*|network[a-z0-9]*)( |$)|data center|fixed network|(cloud|hosting)( |$)') AS operator_shape_t1,
       regexp_matches(c.name_norm, '(^| )(cloud[a-z0-9]*|host[a-z0-9]*|datacent[a-z0-9]*|rechenzentrum|fiber|fibre|isp|colo|vps|dedicated)( |$)|[a-z0-9]+(telecom|host|hosting|net|servers?)( |$)') AS operator_shape_t2,
       false AS operator_name_shape,
       coalesce(a.n_kev, 0) > 0 AS kev_exposed, coalesce(a.n_kev, 0)::INTEGER AS kev_host_count, a.cvss AS max_cvss,
       (CASE WHEN a.cvss IS NULL THEN 0 WHEN a.cvss >= 9 THEN 3 WHEN a.cvss >= 7 THEN 2 ELSE 1 END)::SMALLINT AS max_cvss_band,
       coalesce(a.n_cert, 0) > 0 AS cert_expired_or_soon, coalesce(a.n_cert, 0)::INTEGER AS cert_issue_host_count,
       coalesce(a.n_eol, 0) > 0 AS eol_stack, coalesce(a.n_eol, 0)::INTEGER AS eol_host_count,
       coalesce(a.n_leg, 0) > 0 AS legacy_tls, coalesce(a.n_leg, 0)::INTEGER AS legacy_tls_host_count,
       coalesce(a.n_rk, 0) > 0 AS risky_service_exposed, coalesce(a.n_rk2, 0) > 0 AS risky_non_ssh_exposed,
       coalesce(a.n_rk, 0)::INTEGER AS risky_service_host_count, coalesce(a.ports, []::BIGINT[])::INTEGER[] AS risky_ports,
       coalesce(a.n_eo, 0) > 0 AS exposed_and_outdated
FROM c LEFT JOIN a USING (name_norm) ORDER BY c.company_id
"""
FIX_UNION_SQL = "UPDATE s SET operator_name_shape = (operator_shape_t1 OR operator_shape_t2)"

# (name, SQL on table s, detectors that must fail, cdn_rule). Detector "contract" is signals.yml, "extra" is check_signals_extra.
MUTATIONS = [
    ("duplicated company row (join fan-out)", ["INSERT INTO s SELECT * FROM s WHERE name_norm = 'acme'"], ("contract", "extra"), True),
    ("missing company", ["DELETE FROM s WHERE name_norm = 'quiet corp'"], ("contract", "extra"), True),
    ("kev_exposed flipped", ["UPDATE s SET kev_exposed = false WHERE name_norm = 'acme'"], ("contract", "extra"), True),
    ("kev flipped consistently (bool and count)", ["UPDATE s SET kev_exposed = false, kev_host_count = 0 WHERE name_norm = 'acme'"], ("extra",), True),
    ("cert_expired_or_soon flipped", ["UPDATE s SET cert_expired_or_soon = false WHERE name_norm = 'gamma'"], ("contract", "extra"), True),
    ("cert flipped consistently (bool and count)", ["UPDATE s SET cert_expired_or_soon = false, cert_issue_host_count = 0 WHERE name_norm = 'gamma'"],
     ("extra",), True),
    ("cert 30-day upper edge dropped (delta)", ["UPDATE s SET cert_expired_or_soon = false, cert_issue_host_count = 0 WHERE name_norm = 'delta'"], ("extra",), True),
    ("cert lower edge counted (beta, cert_expires == timestamp)", ["UPDATE s SET cert_expired_or_soon = true, cert_issue_host_count = 1 WHERE name_norm = 'beta'"],
     ("extra",), True),
    ("cdn-tagged host counted for a cert_o company (rule removed)", [], ("contract", "extra"), False),
    ("legacy_tls false while the count is positive", ["UPDATE s SET legacy_tls = false WHERE name_norm = 'acme'"], ("contract", "extra"), True),
    ("-SSLv3 treated as offered (beta legacy count)", ["UPDATE s SET legacy_tls = true, legacy_tls_host_count = 1 WHERE name_norm = 'beta'"], ("extra",), True),
    ("max_cvss of 11", ["UPDATE s SET max_cvss = 11 WHERE name_norm = 'delta'"], ("contract", "extra"), True),
    ("band edge 8.9 labelled 3", ["UPDATE s SET max_cvss_band = 3 WHERE name_norm = 'delta'"], ("contract", "extra"), True),
    ("band edge 9.0 labelled 2", ["UPDATE s SET max_cvss_band = 2 WHERE name_norm = 'epsilon servers'"], ("contract", "extra"), True),
    ("band edge 7.0 labelled 1", ["UPDATE s SET max_cvss_band = 1 WHERE name_norm = 'kappa'"], ("contract", "extra"), True),
    ("max_cvss null but band 1", ["UPDATE s SET max_cvss_band = 1 WHERE name_norm = 'quiet corp'"], ("contract", "extra"), True),
    ("is_singleton wrong", ["UPDATE s SET is_singleton = false WHERE name_norm = 'beta'"], ("contract", "extra"), True),
    ("denylisted name_norm", ["UPDATE s SET name_norm = 'cloudflare', company_name = 'Cloudflare, Inc.' WHERE name_norm = 'quiet corp'"], ("contract", "extra"), True),
    ("carried company_name differs from companies", ["UPDATE s SET company_name = 'Acme Incorporated' WHERE name_norm = 'acme'"], ("contract", "extra"), True),
    ("carried host_count differs from companies", ["UPDATE s SET host_count = host_count + 1, is_singleton = false WHERE name_norm = 'beta'"], ("contract", "extra"), True),
    ("T1 flag flipped (union unchanged)", ["UPDATE s SET operator_shape_t1 = false WHERE name_norm = 'epsilon servers'"], ("contract", "extra"), True),
    ("union not equal to T1 or T2", ["UPDATE s SET operator_name_shape = false WHERE name_norm = 'rackhost'"], ("contract", "extra"), True),
    ("host-blind company with kev true", ["UPDATE s SET kev_exposed = true, kev_host_count = 1 WHERE name_norm = 'gamma'"], ("contract", "extra"), True),
    ("host_signals_blind false while counted is 0", ["UPDATE s SET host_signals_blind = false WHERE name_norm = 'gamma'"], ("contract", "extra"), True),
    ("risky_ports unsorted", ["UPDATE s SET risky_ports = [3389, 22] WHERE name_norm = 'acme'"], ("contract", "extra"), True),
    ("udp port 22 counted as risky", ["UPDATE s SET risky_ports = [22, 6379], risky_service_host_count = 2 WHERE name_norm = 'epsilon servers'"], ("extra",), True),
    ("exposed_and_outdated without a risky service", ["UPDATE s SET exposed_and_outdated = true WHERE name_norm = 'beta'"], ("contract", "extra"), True),
    ("exposed_and_outdated cleared on a same-host company", ["UPDATE s SET exposed_and_outdated = false WHERE name_norm = 'epsilon servers'"], ("extra",), True),
    ("in_territory wrong", ["UPDATE s SET in_territory = true WHERE name_norm = 'gamma'"], ("contract", "extra"), True),
    ("in_territory not null with a null country", ["UPDATE s SET in_territory = false WHERE name_norm = 'epsilon servers'"], ("contract", "extra"), True),
    ("footprint_band edge wrong", ["UPDATE s SET footprint_band = 1 WHERE name_norm = 'midco'"], ("contract", "extra"), True),
    ("risky_ports typed BIGINT[]", ["ALTER TABLE s ALTER risky_ports TYPE BIGINT[]"], ("contract",), True),
    ("extra raw column added", ["ALTER TABLE s ADD COLUMN banner VARCHAR"], ("contract",), True),
    ("max_cvss present for a blind company", ["UPDATE s SET max_cvss = 5.0, max_cvss_band = 1 WHERE name_norm = 'gamma'"], ("contract", "extra"), True),
]


def build_layers(directory, mutation_sql=(), cdn_rule=True):
    """Write synthetic hosts, companies and signals parquet files (signals with optional mutations) into a directory; return the three paths."""
    con = duckdb.connect()
    con.execute(f"CREATE TABLE h ({HOST_SCHEMA})")
    con.executemany("INSERT INTO h VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", SYNTHETIC_HOSTS)
    con.execute("CREATE TABLE k (name_norm VARCHAR, company_name VARCHAR, country_code VARCHAR, noise INTEGER)")
    con.executemany("INSERT INTO k VALUES (?, ?, ?, ?)", [(n, *v) for n, v in SYNTHETIC_COMPANIES.items()])
    con.execute(COMPANIES_SQL)
    counted = "(identity_source = 'org' OR NOT list_contains(coalesce(tags, []::VARCHAR[]), 'cdn'))" if cdn_rule else "true"
    con.execute(SIGNALS_SQL.format(counted=counted))
    con.execute(FIX_UNION_SQL)
    for statement in mutation_sql:
        con.execute(statement)
    paths = [Path(directory) / name for name in ("hosts.parquet", "companies.parquet", "signals.parquet")]
    for table, path in zip(("h", "c", "s"), paths):
        con.execute(f"COPY {table} TO '{path.as_posix()}' (FORMAT PARQUET)")
    return paths


def run_contract(hosts_path, companies_path, signals_path):
    """Run signals.yml against a signals file with the cross-file paths pointed at the temporary hosts and companies; return results."""
    text = CONTRACT_PATH.read_text(encoding="utf-8").replace(HOSTS_PLACEHOLDER, Path(hosts_path).as_posix())
    text = text.replace(COMPANIES_PLACEHOLDER, Path(companies_path).as_posix())
    contract = yaml.safe_load(text)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM {runner.source_sql(signals_path)}")
    results = []
    for step in (runner.check_columns, runner.check_key, runner.check_row_rule, runner.check_denylist, runner.check_infra_reason,
                 runner.check_shares, runner.check_custom):
        step(con, contract, results)
    return results


def run_extra(hosts_path, companies_path, signals_path):
    """Run the extra checks and return their results list."""
    return extra.run_checks(hosts_path, companies_path, signals_path)[0]


def failures(results):
    """Return the names of failed checks."""
    return [name for name, ok, _ in results if not ok]


class UnitTests(unittest.TestCase):
    """Small pure-function cases."""

    def test_cvss_band_edges(self):
        """Bands: null 0, 6.9 is 1, 7.0 is 2, 8.9 is 2, 9.0 is 3, 10.0 is 3."""
        self.assertEqual([extra.cvss_band(v) for v in (None, 0.0, 6.9, 7.0, 8.9, 9.0, 10.0)], [0, 1, 1, 2, 2, 3, 3])

    def test_footprint_band_edges(self):
        """Bands: 1 is 0, 2 and 5 are 1, 6 and 20 are 2, 21 is 3."""
        self.assertEqual([extra.footprint_band(v) for v in (1, 2, 5, 6, 20, 21, 500)], [0, 1, 1, 2, 2, 3, 3])

    def test_cert_condition_edges_and_boolean_first(self):
        """The boolean counts alone; the date counts when strictly after the scan time and at most 30 days after; a null date falls back to the boolean."""
        base = {"identity_source": "org", "tags": [], "ssl_versions": [], "port": 80, "transport": "tcp", "timestamp": TS}
        cases = [(None, False, False), (None, True, True), (TS, False, False), (TS + timedelta(seconds=1), False, True), (TS + timedelta(days=30), False, True),
                 (TS + timedelta(days=30, seconds=1), False, False), (TS - timedelta(days=1), False, False), (TS - timedelta(days=1), True, True)]
        for expires, expired, want in cases:
            with self.subTest(expires=expires, expired=expired):
                self.assertEqual(extra.host_flags({**base, "cert_expires": expires, "cert_expired": expired})["cert_issue"], want)

    def test_host_flags_cdn_legacy_and_risky(self):
        """cdn removes a cert_o host but never an org host; a leading minus is not offered; udp and sweep ports are not risky; 22 is not non-ssh."""
        base = {"tags": [], "ssl_versions": [], "port": 80, "transport": "tcp", "timestamp": TS, "cert_expires": None, "cert_expired": False}
        self.assertFalse(extra.host_flags({**base, "identity_source": "cert_o", "tags": ["cdn"]})["counted"])
        self.assertTrue(extra.host_flags({**base, "identity_source": "org", "tags": ["cdn"]})["counted"])
        self.assertTrue(extra.host_flags({**base, "identity_source": "cert_o", "tags": ["cloud"]})["counted"])
        self.assertFalse(extra.host_flags({**base, "identity_source": "org", "ssl_versions": ["-TLSv1", "TLSv1.2", "-SSLv3"]})["legacy"])
        self.assertTrue(extra.host_flags({**base, "identity_source": "org", "ssl_versions": ["TLSv1.1"]})["legacy"])
        ssh = extra.host_flags({**base, "identity_source": "org", "port": 22})
        self.assertEqual((ssh["risky"], ssh["risky_non_ssh"]), (True, False))
        self.assertFalse(extra.host_flags({**base, "identity_source": "org", "port": 22, "transport": "udp"})["risky"])
        self.assertFalse(extra.host_flags({**base, "identity_source": "org", "port": 12304})["risky"])

    def test_regexes_named_positives_and_near_misses(self):
        """T1 and T2 fire on operator names and not on near misses (D9.5; the suffix net also flags real words by design)."""
        for name in ("epsilon servers", "acme hosting", "telia telecom", "cloud nine", "strato rechenzentrum"):
            self.assertTrue(extra.T1.search(name) or extra.T2.search(name), name)
        self.assertTrue(extra.T2.search("rackhost") and not extra.T1.search("rackhost"))
        self.assertTrue(extra.T2.search("g2net sul provedor"))
        self.assertTrue(extra.T2.search("planet") and not extra.T1.search("planet"))
        for name in ("acme", "quiet corp", "internetworking", "serversmith", "hostage"):
            if name == "hostage":
                self.assertTrue(extra.T2.search(name))  # host[a-z0-9]* is a token prefix; documented over-flagging
            else:
                self.assertFalse(extra.T1.search(name) or extra.T2.search(name), name)

    def test_phi_perfect_and_constant(self):
        """phi is 1 for identical series, -1 for opposite series and 0 for a constant series."""
        self.assertAlmostEqual(extra.phi([(True, True), (False, False)] * 3), 1.0)
        self.assertAlmostEqual(extra.phi([(True, False), (False, True)] * 3), -1.0)
        self.assertEqual(extra.phi([(True, True)] * 4), 0.0)

    def test_reference_matches_hand_computed_values(self):
        """The reference gives the hand-computed rows for acme, gamma, delta, beta and mixed cert."""
        hosts = [dict(zip(("identity_source", "name_norm", "host_ip", "port", "transport", "timestamp", "tags", "ssl_versions", "cert_expires",
                           "cert_expired", "max_cvss", "has_kev"), row)) for row in SYNTHETIC_HOSTS]
        comps = [{"company_id": n, "name_norm": n, "host_count": 1, "distinct_host_ips": 1, "country_code": "US", "identity_confidence": "high"}
                 for n in SYNTHETIC_COMPANIES]
        ref = extra.reference_signals(hosts, comps)
        acme, gamma, delta, beta, mixed = ref["acme"], ref["gamma"], ref["delta"], ref["beta"], ref["mixed cert"]
        self.assertEqual((acme["kev_host_count"], acme["max_cvss"], acme["max_cvss_band"], acme["risky_ports"], acme["exposed_and_outdated"]), (1, 9.8, 3, [22, 3389], True))
        self.assertEqual((acme["legacy_tls_host_count"], acme["eol_host_count"], acme["cert_issue_host_count"], acme["sensitive_stack"]), (1, 1, 1, True))
        self.assertEqual((gamma["host_signals_blind"], gamma["kev_exposed"], gamma["max_cvss"], gamma["cert_expired_or_soon"]), (True, False, None, True))
        self.assertEqual((delta["cert_expired_or_soon"], delta["risky_non_ssh_exposed"], delta["max_cvss_band"]), (True, True, 2))
        self.assertEqual((beta["cert_expired_or_soon"], beta["legacy_tls"], beta["risky_service_exposed"], beta["risky_non_ssh_exposed"]), (False, False, True, False))
        self.assertEqual((mixed["counted_host_count"], mixed["kev_exposed"], mixed["risky_service_exposed"], mixed["_cdn_rows"]), (1, False, False, 1))
        self.assertTrue(ref["epsilon servers"]["exposed_and_outdated"] and not ref["rackhost"]["exposed_and_outdated"])


class CleanLayerTests(unittest.TestCase):
    """A correct synthetic layer must pass both detectors."""

    def test_clean_layer_passes_contract_and_extra(self):
        """Contract and extra checks both pass on a layer built by the independent SQL stand-in."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_layers(tmp)
            self.assertEqual(failures(run_contract(*paths)), [])
            self.assertEqual(failures(run_extra(*paths)), [])

    def test_synthetic_names_and_the_denylist_mutation_are_valid(self):
        """The mutation name is denylisted and no clean synthetic name is (guards the test itself)."""
        matcher = extra.load_matcher()
        rules = matcher.load_rules()
        self.assertIsNotNone(matcher.match_name("cloudflare", "org", rules))
        for name in SYNTHETIC_COMPANIES:
            self.assertIsNone(matcher.match_name(name, "org", rules), name)

    def test_constant_boolean_is_reported(self):
        """check_coverage fails when a boolean signal is constant and warns on a sparse undocumented one."""
        rows = [{n: False for n in extra.BOOLEANS} | {"max_cvss": None, "max_cvss_band": 0} for _ in range(200)]
        rows[0]["legacy_tls"] = True
        results, warnings = [], []
        extra.check_coverage({}, rows, results, warnings, None)
        self.assertFalse(results[0][1])
        self.assertTrue(any("legacy_tls" in w for w in warnings))


class MutationTests(unittest.TestCase):
    """Every injected fault must make the named detector fail."""

    def test_each_mutation_is_caught(self):
        """For each fault the detectors named in MUTATIONS report at least one failed check."""
        self.assertGreaterEqual(len(MUTATIONS), 8)
        for name, statements, detectors, cdn_rule in MUTATIONS:
            with self.subTest(fault=name), tempfile.TemporaryDirectory() as tmp:
                paths = build_layers(tmp, statements, cdn_rule)
                found = {"contract": failures(run_contract(*paths)), "extra": failures(run_extra(*paths))}
                for detector in detectors:
                    self.assertTrue(found[detector], f"{detector} did not catch: {name}")


if __name__ == "__main__":
    unittest.main()
