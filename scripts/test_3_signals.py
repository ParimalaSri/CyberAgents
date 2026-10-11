"""Unit tests for pipeline/3_signals.py on tiny synthetic hosts and companies parquet files (stdlib unittest, DuckDB, no pandas)."""
import datetime
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

STAGE_PATH = Path(__file__).resolve().parent.parent / "pipeline" / "3_signals.py"
SPEC = importlib.util.spec_from_file_location("signals_stage", STAGE_PATH)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)

TS = datetime.datetime(2026, 9, 14, 10, 0, 0)
HOST_DDL = (
    "name_norm VARCHAR, identity_source VARCHAR, tags VARCHAR[], transport VARCHAR, port BIGINT, has_kev BOOLEAN, max_cvss DOUBLE, "
    "cert_expired BOOLEAN, cert_expires TIMESTAMP, timestamp TIMESTAMP, ssl_versions VARCHAR[], host_ip VARCHAR"
)
COMPANY_DDL = (
    "company_id VARCHAR, company_name VARCHAR, name_norm VARCHAR, identity_source VARCHAR, identity_confidence VARCHAR, host_count INTEGER, "
    "distinct_host_ips INTEGER, country_code VARCHAR, noise_host_count INTEGER, noise_host_share DOUBLE"
)
HOST_DEFAULTS = {"identity_source": "org", "tags": None, "transport": "tcp", "port": 443, "has_kev": False, "max_cvss": None,
                 "cert_expired": None, "cert_expires": None, "timestamp": TS, "ssl_versions": None}
HOST_ORDER = ("name_norm", "identity_source", "tags", "transport", "port", "has_kev", "max_cvss", "cert_expired", "cert_expires",
              "timestamp", "ssl_versions", "host_ip")


def host(name, **over):
    """Return a hosts row dict for company `name` with defaults and overrides."""
    row = dict(HOST_DEFAULTS, name_norm=name)
    row.update(over)
    return row


def run_signals(hosts, companies=None, ips=None, country="US"):
    """Run the stage on synthetic hosts; derive one company per name_norm unless given; return {name_norm: signals row dict} and the names."""
    with tempfile.TemporaryDirectory() as tmp:
        con = duckdb.connect()
        con.execute(f"CREATE TABLE h ({HOST_DDL})")
        for i, row in enumerate(hosts):
            row = dict(row, host_ip=row.get("host_ip", f"10.0.0.{i}"))
            con.execute("INSERT INTO h VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [row[k] for k in HOST_ORDER])
        con.execute(f"COPY h TO '{Path(tmp, 'hosts.parquet').as_posix()}' (FORMAT PARQUET)")
        con.execute(f"CREATE TABLE c ({COMPANY_DDL})")
        if companies is None:
            companies = {}
            for r in hosts:
                companies.setdefault(r["name_norm"], []).append(r)
            companies = {n: {"host_count": len(rs), "distinct_host_ips": ips.get(n, len(rs)) if ips else len(rs),
                             "source": "org" if any(r["identity_source"] == "org" for r in rs) else "cert_o"} for n, rs in companies.items()}
        for n, spec in companies.items():
            conf = "high" if spec["source"] == "org" else "low"
            con.execute("INSERT INTO c VALUES (?,?,?,?,?,?,?,?,?,?)",
                        [f"id_{n}", n.title(), n, spec["source"], conf, spec["host_count"], spec["distinct_host_ips"], spec.get("country", country), 0, 0.0])
        con.execute(f"COPY c TO '{Path(tmp, 'companies.parquet').as_posix()}' (FORMAT PARQUET)")
        out = Path(tmp, "out", "signals.parquet")
        counts = STAGE.run_stage(con, Path(tmp, "hosts.parquet"), Path(tmp, "companies.parquet"), out)
        cur = con.execute(f"SELECT * FROM read_parquet('{out.as_posix()}') ORDER BY company_id")
        names = [d[0] for d in cur.description]
        return {r[2]: dict(zip(names, r)) for r in cur.fetchall()}, names, counts


def one(**over):
    """Run one single-host company named `acme` with host overrides; return its signals row."""
    rows, _, _ = run_signals([host("acme", **over)])
    return rows["acme"]


class SignalStageTests(unittest.TestCase):
    """Behaviour of each signal on handcrafted hosts."""

    def test_kev_and_counts(self):
        """kev_exposed fires on any counted KEV host and kev_host_count counts them; absent KEV does not fire."""
        rows, _, _ = run_signals([host("a", has_kev=True), host("a", has_kev=True), host("a"), host("b")])
        self.assertTrue(rows["a"]["kev_exposed"])
        self.assertEqual(rows["a"]["kev_host_count"], 2)
        self.assertFalse(rows["b"]["kev_exposed"])
        self.assertEqual(rows["b"]["kev_host_count"], 0)

    def test_max_cvss_band_edges(self):
        """max_cvss_band: null 0, 6.9 1, 7.0 2, 8.9 2, 9.0 3; max_cvss is the maximum over hosts."""
        for cvss, band in ((None, 0), (0.0, 1), (6.9, 1), (7.0, 2), (8.9, 2), (9.0, 3), (10.0, 3)):
            row = one(max_cvss=cvss)
            self.assertEqual(row["max_cvss_band"], band, cvss)
            self.assertEqual(row["max_cvss"], cvss)
        rows, _, _ = run_signals([host("a", max_cvss=5.0), host("a", max_cvss=9.8)])
        self.assertEqual(rows["a"]["max_cvss"], 9.8)

    def test_cdn_rule_on_cert_o_host(self):
        """A cdn-tagged cert_o host is not counted (company is blind); the same tag on an org host is counted."""
        rows, _, _ = run_signals([host("c", identity_source="cert_o", tags=["cdn"], has_kev=True, port=22, max_cvss=9.8),
                                  host("o", identity_source="org", tags=["cdn"], has_kev=True)])
        self.assertTrue(rows["c"]["host_signals_blind"])
        self.assertEqual(rows["c"]["counted_host_count"], 0)
        for flag in ("kev_exposed", "risky_service_exposed", "eol_stack", "legacy_tls", "sensitive_stack", "exposed_and_outdated"):
            self.assertFalse(rows["c"][flag], flag)
        self.assertIsNone(rows["c"]["max_cvss"])
        self.assertEqual(rows["c"]["kev_host_count"], 0)
        self.assertFalse(rows["o"]["host_signals_blind"])
        self.assertTrue(rows["o"]["kev_exposed"])

    def test_cert_o_without_cdn_is_counted(self):
        """A cert_o host without the cdn tag (cloud tag only) is counted."""
        rows, _, _ = run_signals([host("c", identity_source="cert_o", tags=["cloud"], has_kev=True)])
        self.assertEqual(rows["c"]["counted_host_count"], 1)
        self.assertTrue(rows["c"]["kev_exposed"])

    def test_cert_signal_uses_cdn_hosts_too(self):
        """Certificate signals use every member host, so a cdn-tagged cert_o host fires cert_expired_or_soon while the company stays blind."""
        rows, _, _ = run_signals([host("c", identity_source="cert_o", tags=["cdn"], cert_expired=True)])
        self.assertTrue(rows["c"]["cert_expired_or_soon"])
        self.assertEqual(rows["c"]["cert_issue_host_count"], 1)
        self.assertTrue(rows["c"]["host_signals_blind"])

    def test_cert_condition_branches(self):
        """Boolean first, then valid date within 30 days after the host's own timestamp; edges and non-firing cases."""
        day = datetime.timedelta(days=1)
        cases = {
            "boolean true, no date": (dict(cert_expired=True), True),
            "boolean true, far date": (dict(cert_expired=True, cert_expires=TS + 400 * day), True),
            "date in 10 days": (dict(cert_expired=False, cert_expires=TS + 10 * day), True),
            "date null boolean null": (dict(), False),
            "date in 30 days exactly": (dict(cert_expired=False, cert_expires=TS + 30 * day), True),
            "date in 30 days and 1 second": (dict(cert_expired=False, cert_expires=TS + 30 * day + datetime.timedelta(seconds=1)), False),
            "date in 400 days": (dict(cert_expired=False, cert_expires=TS + 400 * day), False),
            "date in the past but boolean false": (dict(cert_expired=False, cert_expires=TS - 5 * day), False),
            "date equal to timestamp, boolean false": (dict(cert_expired=False, cert_expires=TS), False),
            "date soon, boolean null": (dict(cert_expires=TS + 3 * day), True),
        }
        for label, (over, expected) in cases.items():
            row = one(**over)
            self.assertEqual(row["cert_expired_or_soon"], expected, label)
            self.assertEqual(row["cert_issue_host_count"], int(expected), label)

    def test_cert_window_uses_own_timestamp(self):
        """The 30 day window is measured from each host's own timestamp, not a global time."""
        later = TS + datetime.timedelta(days=100)
        row = one(cert_expires=TS + datetime.timedelta(days=20), timestamp=later)
        self.assertFalse(row["cert_expired_or_soon"])

    def test_legacy_tls(self):
        """legacy_tls fires on an offered old version and not on refused ('-' prefix) or modern versions."""
        self.assertTrue(one(ssl_versions=["TLSv1", "TLSv1.2"])["legacy_tls"])
        self.assertTrue(one(ssl_versions=["-TLSv1.2", "SSLv3"])["legacy_tls"])
        self.assertTrue(one(ssl_versions=["TLSv1.1"])["legacy_tls"])
        self.assertTrue(one(ssl_versions=["SSLv2"])["legacy_tls"])
        self.assertFalse(one(ssl_versions=["-SSLv2", "-SSLv3", "-TLSv1", "-TLSv1.1", "TLSv1.2", "TLSv1.3"])["legacy_tls"])
        self.assertFalse(one(ssl_versions=None)["legacy_tls"])
        self.assertFalse(one(ssl_versions=[])["legacy_tls"])
        self.assertEqual(one(ssl_versions=["TLSv1"])["legacy_tls_host_count"], 1)

    def test_eol_and_sensitive_tags(self):
        """eol_stack fires on eol-product or eol-os; sensitive_stack on database, ics, medical or iot; other tags do not."""
        self.assertTrue(one(tags=["eol-product"])["eol_stack"])
        self.assertTrue(one(tags=["eol-os", "cloud"])["eol_stack"])
        self.assertFalse(one(tags=["self-signed", "cloud"])["eol_stack"])
        for tag in ("database", "ics", "medical", "iot"):
            self.assertTrue(one(tags=[tag])["sensitive_stack"], tag)
        self.assertFalse(one(tags=["vpn", "proxy"])["sensitive_stack"])
        self.assertFalse(one(tags=None)["sensitive_stack"])
        self.assertEqual(one(tags=["eol-product"])["eol_host_count"], 1)

    def test_risky_ports_and_ssh_split(self):
        """Every listed tcp port is risky; 22 is risky but not non-SSH; udp, port 12304 and 80 are not risky."""
        for port in STAGE.RISKY_PORTS:
            row = one(port=port)
            self.assertTrue(row["risky_service_exposed"], port)
            self.assertEqual(row["risky_non_ssh_exposed"], port != 22, port)
            self.assertEqual(row["risky_ports"], [port])
        for port in (80, 443, 12304, 8080):
            self.assertFalse(one(port=port)["risky_service_exposed"], port)
        self.assertFalse(one(port=3389, transport="udp")["risky_service_exposed"])

    def test_risky_ports_list_sorted_distinct_counted_only(self):
        """risky_ports is the sorted distinct list of counted risky hosts; host count counts hosts; empty list when none."""
        rows, _, _ = run_signals([host("a", port=3389), host("a", port=22), host("a", port=3389), host("a", port=80),
                                  host("c", identity_source="cert_o", tags=["cdn"], port=445), host("n", port=80)])
        self.assertEqual(rows["a"]["risky_ports"], [22, 3389])
        self.assertEqual(rows["a"]["risky_service_host_count"], 3)
        self.assertEqual(rows["c"]["risky_ports"], [])
        self.assertEqual(rows["n"]["risky_ports"], [])

    def test_exposed_and_outdated_same_host(self):
        """exposed_and_outdated needs one counted host that is risky and (eol or cvss >= 7); two separate hosts do not count."""
        self.assertTrue(one(port=3389, tags=["eol-product"])["exposed_and_outdated"])
        self.assertTrue(one(port=22, max_cvss=7.0)["exposed_and_outdated"])
        self.assertFalse(one(port=22, max_cvss=6.9)["exposed_and_outdated"])
        self.assertFalse(one(port=80, tags=["eol-product"], max_cvss=9.8)["exposed_and_outdated"])
        rows, _, _ = run_signals([host("a", port=3389), host("a", port=80, tags=["eol-product"], max_cvss=9.8),
                                  host("b", port=3389, tags=["eol-product"]), host("b", port=80)])
        self.assertTrue(rows["a"]["risky_service_exposed"] and rows["a"]["eol_stack"])
        self.assertFalse(rows["a"]["exposed_and_outdated"])
        self.assertTrue(rows["b"]["exposed_and_outdated"])

    def test_footprint_edges(self):
        """footprint_band 0 for 1 IP, 1 for 2 to 5, 2 for 6 to 20, 3 above 20; footprint_size is capped at 50."""
        for ips, band in ((1, 0), (2, 1), (5, 1), (6, 2), (20, 2), (21, 3), (500, 3)):
            rows, _, _ = run_signals([host("a")], companies={"a": {"host_count": ips, "distinct_host_ips": ips, "source": "org"}})
            self.assertEqual(rows["a"]["footprint_band"], band, ips)
            self.assertEqual(rows["a"]["footprint_size"], min(ips, 50), ips)

    def test_carried_and_flag_columns(self):
        """is_singleton, named_registrant, in_territory (null on null country) and carried columns follow D9.4."""
        rows, _, _ = run_signals(
            [host("a"), host("b", identity_source="cert_o"), host("b", identity_source="cert_o"), host("d"), host("e")],
            companies={"a": {"host_count": 1, "distinct_host_ips": 1, "source": "org", "country": "US"},
                       "b": {"host_count": 2, "distinct_host_ips": 2, "source": "cert_o", "country": "DE"},
                       "d": {"host_count": 1, "distinct_host_ips": 1, "source": "org", "country": None},
                       "e": {"host_count": 1, "distinct_host_ips": 1, "source": "org", "country": "us"}})
        self.assertTrue(rows["a"]["is_singleton"] and rows["a"]["named_registrant"] and rows["a"]["in_territory"])
        self.assertFalse(rows["b"]["is_singleton"] or rows["b"]["named_registrant"] or rows["b"]["in_territory"])
        self.assertIsNone(rows["d"]["in_territory"])
        self.assertFalse(rows["e"]["in_territory"])
        self.assertEqual(rows["a"]["company_id"], "id_a")
        self.assertEqual(rows["b"]["identity_confidence"], "low")

    def test_operator_regexes_positive(self):
        """T1 and T2 flag the named operator shapes and the union column equals T1 or T2."""
        t1_names = ["acme hosting", "big telecom", "telekom austria", "network solutions", "my data center inc", "foo cloud", "internet services",
                    "dedicated servers", "broadband one", "comunicaciones sa", "fixed network ltd", "xyz idc", "cable one", "hosted by foo"]
        t2_names = ["cloudradium", "hostpoint", "datacenter gmbh", "strato rechenzentrum", "omni fiber", "omni fibre", "my isp", "colo space", "vps shop",
                    "dedicated line co", "xxxtelecom", "xxxhost", "xxxhosting", "xxxserver", "xxxservers", "rackhost zrt", "sibirtelecom", "cloud9 ltd"]
        rows, _, _ = run_signals([host(n) for n in t1_names + t2_names])
        for n in t1_names:
            self.assertTrue(rows[n]["operator_shape_t1"], n)
            self.assertTrue(rows[n]["operator_name_shape"], n)
        for n in t2_names:
            self.assertTrue(rows[n]["operator_shape_t2"], n)
            self.assertTrue(rows[n]["operator_name_shape"], n)
        self.assertFalse(rows["cloudradium"]["operator_shape_t1"])
        self.assertFalse(rows["hostpoint"]["operator_shape_t1"])
        self.assertTrue(rows["acme hosting"]["operator_shape_t1"])

    def test_operator_regexes_negative(self):
        """Near-miss names are not flagged by either regex."""
        names = ["kent state university", "autozone", "salesforce", "bank of testing", "rooster", "acme", "colorado university",
                 "reverse", "retail group", "oil and gas", "gerondata", "bellnet", "newsnet ag",
                 "ente nazionale ellenico per il turismo public subnet", "planet", "magnet corp", "internetx", "cabinet"]
        rows, _, _ = run_signals([host(n) for n in names])
        for n in names:
            self.assertFalse(rows[n]["operator_shape_t1"], n)
            self.assertFalse(rows[n]["operator_shape_t2"], n)
            self.assertFalse(rows[n]["operator_name_shape"], n)

    def test_operator_regex_edge_cases(self):
        """T1 needs whole words (hostels is not hosting); T2 only-names are flagged by T2 and not T1; the `net` suffix is no longer flagged (D11.1)."""
        rows, _, _ = run_signals([host(n) for n in ("hostels inc", "research lab", "planet", "magnet corp", "acme servers", "cloud", "bellnet")])
        self.assertFalse(rows["hostels inc"]["operator_shape_t1"])
        self.assertTrue(rows["hostels inc"]["operator_shape_t2"])
        self.assertTrue(rows["research lab"]["operator_shape_t1"])
        for n in ("planet", "magnet corp", "bellnet"):
            self.assertFalse(rows[n]["operator_shape_t2"], n)
            self.assertFalse(rows[n]["operator_name_shape"], n)
        self.assertTrue(rows["acme servers"]["operator_shape_t1"])
        self.assertTrue(rows["cloud"]["operator_shape_t1"])

    def test_no_fan_out_and_rows_equal_companies(self):
        """A company with many hosts and a merged org plus cert_o company give exactly one signals row; counts equal companies."""
        hosts = [host("big", port=p, host_ip=f"1.1.1.{p % 250}") for p in range(100)]
        hosts += [host("m", identity_source="org"), host("m", identity_source="cert_o", tags=["cdn"]), host("m", identity_source="cert_o")]
        rows, names, counts = run_signals(hosts)
        self.assertEqual(counts["signals_rows"], counts["companies_rows"])
        self.assertEqual(counts["signals_rows"], len(rows))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows["big"]["host_count"], 100)
        self.assertEqual(rows["m"]["host_count"], 3)
        self.assertEqual(rows["m"]["counted_host_count"], 2)
        self.assertFalse(rows["m"]["host_signals_blind"])

    def test_non_member_hosts_never_join(self):
        """Hosts whose identity_source is noise or infrastructure, or whose name_norm is null, add nothing to any company."""
        rows, _, counts = run_signals(
            [host("a"), host("a", identity_source="noise", has_kev=True), host("a", identity_source="infrastructure_unresolved", port=3389),
             host(None, identity_source="null_org", has_kev=True)],
            companies={"a": {"host_count": 1, "distinct_host_ips": 1, "source": "org"}})
        self.assertEqual(counts["member_rows"], 1)
        self.assertFalse(rows["a"]["kev_exposed"])
        self.assertFalse(rows["a"]["risky_service_exposed"])

    def test_output_columns_and_types(self):
        """The output has the 36 D9.4 columns in order, with the specified types, and no raw payload columns."""
        _, names, _ = run_signals([host("a")])
        self.assertEqual(len(names), 36)
        self.assertEqual(tuple(names), STAGE.KEY_COLUMNS)
        for banned in ("tags", "ssl_versions", "cert_expires", "hostnames", "domains", "org", "cpe", "vulns", "product", "version", "data", "html"):
            self.assertNotIn(banned, names)
        con = duckdb.connect()
        with tempfile.TemporaryDirectory() as tmp:
            con.execute(f"CREATE TABLE h ({HOST_DDL})")
            con.execute("INSERT INTO h VALUES ('a','org',NULL,'tcp',22,false,NULL,NULL,NULL,'2026-09-14 10:00:00',NULL,'1.1.1.1')")
            con.execute(f"COPY h TO '{Path(tmp, 'h.parquet').as_posix()}' (FORMAT PARQUET)")
            con.execute(f"CREATE TABLE c ({COMPANY_DDL})")
            con.execute("INSERT INTO c VALUES ('id','A','a','org','high',1,1,'US',0,0.0)")
            con.execute(f"COPY c TO '{Path(tmp, 'c.parquet').as_posix()}' (FORMAT PARQUET)")
            STAGE.run_stage(con, Path(tmp, "h.parquet"), Path(tmp, "c.parquet"), Path(tmp, "o.parquet"))
            types = {r[0]: r[1] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{Path(tmp, 'o.parquet').as_posix()}')").fetchall()}
        self.assertEqual(types, dict(STAGE.OUTPUT_COLUMNS))

    def test_full_paths_are_separate(self):
        """The full-run paths differ from the sample paths and the placeholder territory is labelled and fixed to US."""
        self.assertNotEqual(STAGE.FULL_OUTPUT_PATH, STAGE.OUTPUT_PATH)
        self.assertEqual(STAGE.FULL_OUTPUT_PATH.name, "signals_full.parquet")
        self.assertEqual(STAGE.FULL_HOSTS_PATH.name, "hosts_full.parquet")
        self.assertEqual(STAGE.FULL_COMPANIES_PATH.name, "companies_full.parquet")
        self.assertEqual(STAGE.TERRITORY_COUNTRIES, ("US",))

    def test_fan_out_assertion_fires(self):
        """A duplicated company row in the spine trips the stage's no-fan-out assertion."""
        with tempfile.TemporaryDirectory() as tmp:
            con = duckdb.connect()
            con.execute(f"CREATE TABLE h ({HOST_DDL})")
            con.execute("INSERT INTO h VALUES ('a','org',NULL,'tcp',22,false,NULL,NULL,NULL,'2026-09-14 10:00:00',NULL,'1.1.1.1')")
            con.execute(f"COPY h TO '{Path(tmp, 'h.parquet').as_posix()}' (FORMAT PARQUET)")
            con.execute(f"CREATE TABLE c ({COMPANY_DDL})")
            con.execute("INSERT INTO c VALUES ('id','A','a','org','high',1,1,'US',0,0.0), ('id','A','a','org','high',1,1,'US',0,0.0)")
            con.execute(f"COPY c TO '{Path(tmp, 'c.parquet').as_posix()}' (FORMAT PARQUET)")
            with self.assertRaises(AssertionError):
                STAGE.run_stage(con, Path(tmp, "h.parquet"), Path(tmp, "c.parquet"), Path(tmp, "o.parquet"))


ROOT_DIR = Path(__file__).resolve().parent.parent


def run_cli(args, env=None):
    """Run the stage script as a subprocess and return the completed process (text output, UTF-8 decoded)."""
    return subprocess.run([sys.executable, str(STAGE_PATH), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=dict(os.environ, **(env or {})))


def dq_listing(prefix):
    """Return (name, mtime) pairs of the committed stage reports so a test can prove they were not touched."""
    dq = ROOT_DIR / "outputs" / "dq"
    return sorted((f.name, f.stat().st_mtime_ns) for f in dq.glob(prefix + "_stage_*.md")) if dq.exists() else []


def write_inputs(tmp, hosts, companies):
    """Write hosts dicts (run_signals shape) and company tuples (company_id, name, name_norm, host_count) as the two input parquet files."""
    con = duckdb.connect()
    con.execute(f"CREATE TABLE h ({HOST_DDL})")
    for i, row in enumerate(hosts):
        row = dict(row, host_ip=row.get("host_ip", f"10.0.0.{i}"))
        con.execute("INSERT INTO h VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [row[k] for k in HOST_ORDER])
    con.execute(f"COPY h TO '{Path(tmp, 'hosts.parquet').as_posix()}' (FORMAT PARQUET)")
    con.execute(f"CREATE TABLE c ({COMPANY_DDL})")
    for cid, name, norm, count in companies:
        con.execute("INSERT INTO c VALUES (?,?,?,?,?,?,?,?,?,?)", [cid, name, norm, "org", "high", count, count, "US", 0, 0.0])
    con.execute(f"COPY c TO '{Path(tmp, 'companies.parquet').as_posix()}' (FORMAT PARQUET)")
    return Path(tmp, "hosts.parquet"), Path(tmp, "companies.parquet")


class PinnedSpecTests(unittest.TestCase):
    """QA finding 6: the risky-port list pinned with literal values, not read from the constant."""

    def test_risky_port_list_literal(self):
        """Exactly the D9.4 ports are risky over tcp: 22, 3389, 445, 3306, 6379, 27017, 9200, 5900, 23 and 2375; nothing else tested is."""
        for port in (22, 3389, 445, 3306, 6379, 27017, 9200, 5900, 23, 2375):
            self.assertTrue(one(port=port)["risky_service_exposed"], port)
            self.assertEqual(one(port=port)["risky_non_ssh_exposed"], port != 22, port)
        for port in (21, 25, 80, 110, 443, 2376, 3307, 6380, 8080, 27018, 9201, 5901, 24, 2374, 1433, 5432, 11211):
            self.assertFalse(one(port=port)["risky_service_exposed"], port)
        self.assertEqual(sorted(STAGE.RISKY_PORTS), [22, 23, 445, 2375, 3306, 3389, 5900, 6379, 9200, 27017])


class CliRobustnessTests(unittest.TestCase):
    """QA findings 2, 3, 7, 8 for the signals stage: zero rows, report path, UTF-8 report, output path guard."""

    def test_zero_row_batches_complete(self):
        """Empty hosts with empty companies, and hosts but no member companies, complete with exit code 0 and a zero-row output."""
        for hosts in ([], [host("loner", identity_source="null_org")]):
            with tempfile.TemporaryDirectory() as tmp:
                src, comp = write_inputs(tmp, hosts, [])
                out = Path(tmp, "signals.parquet")
                result = run_cli(["--hosts", src, "--companies", comp, "--output", out])
                self.assertEqual(result.returncode, 0, result.stderr[-500:])
                self.assertEqual(duckdb.connect().execute(f"SELECT count(*) FROM read_parquet('{out.as_posix()}')").fetchone()[0], 0)
                self.assertTrue(Path(tmp, "signals_stage_report.md").exists())
                self.assertIn("rows: 0", result.stdout)

    def test_report_goes_next_to_scratch_output(self):
        """With a non-default --output and no --report the report sits beside the output; --report overrides; the committed reports are untouched."""
        before = dq_listing("signals")
        with tempfile.TemporaryDirectory() as tmp:
            src, comp = write_inputs(tmp, [host("acme")], [("id_acme", "Acme", "acme", 1)])
            out = Path(tmp, "sub", "signals.parquet")
            self.assertEqual(run_cli(["--hosts", src, "--companies", comp, "--output", out]).returncode, 0)
            self.assertTrue(Path(tmp, "sub", "signals_stage_report.md").exists())
            custom = Path(tmp, "elsewhere", "my_report.md")
            self.assertEqual(run_cli(["--hosts", src, "--companies", comp, "--output", out, "--report", custom]).returncode, 0)
            self.assertTrue(custom.exists())
        self.assertEqual(before, dq_listing("signals"))

    def test_default_output_keeps_committed_report_path(self):
        """With the default output the report path is the committed outputs/dq path."""
        guard = STAGE.load_guard()
        default_report = STAGE.REPORT_DIR / "signals_stage_2026-01-01.md"
        self.assertEqual(guard.choose_report_path(str(STAGE.OUTPUT_PATH), STAGE.OUTPUT_PATH, None, default_report, "signals"), default_report)

    def test_cjk_name_under_cp1252_pipe(self):
        """A CJK company name does not break the report under the default Windows pipe encoding."""
        name = "\u682a\u5f0f\u4f1a\u793e\u30c6\u30b9\u30c8"
        with tempfile.TemporaryDirectory() as tmp:
            src, comp = write_inputs(tmp, [host(name)], [("id_x", name, name, 1)])
            out = Path(tmp, "signals.parquet")
            result = run_cli(["--hosts", src, "--companies", comp, "--output", out], env={"PYTHONIOENCODING": "cp1252"})
            self.assertEqual(result.returncode, 0, result.stderr[-500:])
            self.assertTrue(out.exists())

    def test_output_under_raw_or_dataset_folder_refused(self):
        """Outputs under data/raw (plain, with .., upper case) and under the dataset folder are refused and nothing is written."""
        with tempfile.TemporaryDirectory() as tmp:
            src, comp = write_inputs(tmp, [host("acme")], [("id_acme", "Acme", "acme", 1)])
            targets = [ROOT_DIR / "data" / "raw" / "qa_guard_test.parquet",
                       str(ROOT_DIR / "data" / "silver" / ".." / "raw" / "qa_guard_test.parquet"),
                       str(ROOT_DIR / "DATA" / "RAW" / "qa_guard_test.parquet"),
                       "D:/Cyber_DataSet/qa_guard_test.parquet", "d:/CYBER_DATASET/sub/../qa_guard_test.parquet"]
            for target in targets:
                result = run_cli(["--hosts", src, "--companies", comp, "--output", target])
                self.assertNotEqual(result.returncode, 0, str(target))
                self.assertIn("refusing to write", result.stderr, str(target))
                self.assertFalse(Path(target).exists(), str(target))


if __name__ == "__main__":
    unittest.main()
