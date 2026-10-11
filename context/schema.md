# Schema: raw layer (DRAFT, proposed by data-integrator, not yet approved)

Source file: `data/sample/spread_100k.jsonl` (seek-spread dev sample, decision D3, built by `scripts/build_spread_sample.py`; full file is 84.6 GB, outside the repo).
Numbers below are from the spread sample (updated 2026-10-11); the first-100K head sample (`data/raw/sample_100k.jsonl`) is kept only to reproduce `outputs/profile_sample_100k.md`. Comparison: `outputs/profile_spread_100k.md`.
| Rows: 100,000 | Produced by: external crawler (no script in this repo) | Grain: one row per service banner on one IP:port (+ transport)

Read with DuckDB `read_json_auto(path, sample_size=20000, maximum_object_size=33554432, ignore_errors=true)`: 85 top-level columns in the spread sample (78 in the head sample; the set of rare protocol structs varies by sample, so stage 1 must name its columns).
Array length: use `len()`. Map size: `cardinality(vulns)` (cardinality works on MAPs only). Null % are of 100,000 rows.
Struct fields are addressed as `ssl.cert.expires` etc. Null % for nested fields is the share of ROWS where the field is null.

## Core columns (documented in full)
| column | type | null % | meaning | used for |
|---|---|---|---|---|
| ip_str | VARCHAR | 1.47 | IPv4 dotted string; null on the 1,468 IPv6 rows | key |
| ip | BIGINT | 1.47 | IPv4 as integer, matches ip_str on all rows | ignore |
| ipv6 | VARCHAR | 98.53 | IPv6 address (set only when ip_str is null) | key |
| port | BIGINT | 0 | service port; 80 13.9%, 443 6.6%, 179 2.1%, 12304 0.22% | urgency (risky ports) |
| transport | VARCHAR | 0 | tcp 98.82%, udp 1.18% | ignore |
| timestamp | VARCHAR | 0 | ISO scan time; whole sample spans 2026-09-14 09:54 to 11:05 (about 71 min) | urgency (weak here) |
| org | VARCHAR | 0.20 | registered owner of the IP block; 6,579 distinct; mostly hosting/cloud/CDN | entity, fit |
| isp | VARCHAR | 8.72 | ISP/provider; null exactly when asn is null | entity (denylist) |
| asn | VARCHAR | 8.72 | autonomous system `AS<n>`; 4,240 distinct | entity (secondary) |
| product | VARCHAR | 80.62 | detected software (nginx, Apache httpd, OpenSSH ...) | fit, urgency |
| version | VARCHAR | 93.63 | free-text version of product; 16 empty strings | urgency |
| os | VARCHAR | 97.54 | detected OS | fit |
| devicetype | VARCHAR | 99.93 | device class (router, webcam ...) | fit (weak) |
| info | VARCHAR | 96.97 | extra banner info | ignore |
| cpe23 / cpe | VARCHAR[] | 75.83 / 75.82 | CPE identifiers for product/os | urgency (version match) |
| hostnames | VARCHAR[] | 0 (27.07 empty) | reverse-DNS names; use `len()` | entity |
| domains | VARCHAR[] | 0 (27.07 empty) | registrable domains of hostnames; mostly provider domains | entity (weak) |
| tags | VARCHAR[] | 34.17 | Shodan labels: cloud, cdn, eol-product, self-signed, honeypot ... | fit, urgency, exclusion |
| location.country_code | VARCHAR | 0.02 | ISO country of the IP; 177 distinct, US 51% | fit |
| location.city | VARCHAR | 0.02 | city | ignore |
| cloud.provider | VARCHAR | 59.46 | cloud vendor name (Google, Amazon, Azure ...), 11 values | exclusion |
| cloud.service / cloud.region | VARCHAR | 91.81 / 61.87 | cloud product and region | ignore |
| vulns | MAP(CVE -> STRUCT) | 96.92 | CVE map; struct has cvss, cvss_version, epss, kev, verified, summary, references | urgency |
| vulns[*].cvss | DOUBLE | 0 of entries | CVSS score; row max median 9.8 | urgency |
| vulns[*].kev | BOOLEAN | n/a | on CISA KEV list; 1,807 rows contain one | urgency |
| ssl | STRUCT | 90.17 | TLS data; 9,833 rows | urgency |
| ssl.cert.expires / issued | VARCHAR | 90.17 | `YYYYMMDDHHMMSSZ` text; sentinels 0001... and 4096... exist (spread: 2 x 4096, no 0001 in expires) | urgency |
| ssl.cert.expired | BOOLEAN | 90.17 | expired relative to scan time; 598 true | urgency |
| ssl.cert.subject.CN / O | VARCHAR | 90.29 / 97.85 | cert common name and organisation | entity (secondary) |
| ssl.cert.issuer.O | VARCHAR | 91.08 | issuing CA | ignore |
| ssl.versions | VARCHAR[] | 90.17 | TLS versions; `-` prefix = refused | urgency |
| http | STRUCT | 66.83 | HTTP data: status, title, host, server, waf, headers, components, html | fit (weak) |
| http.title / host / server / waf | VARCHAR | 77.32 / 66.83 / 76.03 / 87.21 | page title, vhost, server header, WAF | fit (weak) |
| _shodan.module | VARCHAR | 0 | collector module; auto 52.7%, includes RAT/C2 modules | exclusion |
| ntlm.dns_domain_name / netbios_domain_name | VARCHAR | 99.82 (dns_domain_name) | Windows domain names | entity (rare) |
| data | VARCHAR | 0 | raw banner text (often empty; max 43,349 chars) | ignore |
| hash | HUGEINT | 0 | banner hash | ignore |
| opts | MAP | 0 | collector options | ignore |
| title, html, screenshot | VARCHAR / STRUCT | 99.99 / 99.94 / 99.98 | page title, HTML, screenshot | ignore |

## Sparse protocol structs (all more than 92% null; not profiled in depth)
ssh 99.43, dns 99.79, mac 99.70, snmp 99.61, ntp 99.87, ftp 99.91, telnet 99.92, mysql 99.93, vnc 99.93, ntlm 99.92,
hikvision 99.83, rdp_encryption 99.94, isakmp 99.95, smb 99.98, mdns 99.99, mqtt 99.99, redis 99.99, mongodb 100.0,
ldap 100.0, bgp 100.0, fortinet 99.98, hp_ilo 100.0, kubernetes 99.97, node_exporter 99.97, open_dir 99.95,
mikrotik_routeros 99.98, mikrotik_winbox 99.98, dahua / dahua_dvr_web / ip_camera 99.94 to 99.99, and 20 more single-protocol
structs (pptp, plex, mysqlx, msrpc, synology_dsm, cisco_ipsla, fast_reverse_proxy, mcp, draytek_vigor, ntrip, philips_hue,
oracle_tnslsnr, spotify_connect, ipp_cups, dav, minecraft, ...). Role: urgency (exposed service) where a risky service is
the finding, otherwise ignore. cpe23_hash is 78.16 null (spread). Structs present only in the spread sample: microsoft_exchange, openflow, checkpoint, netbios, radius, qnap, rsync, afp, airplay, ipmi, ethereum_p2p, neo4j_browser, plus string columns `device` and `vendor`; absent from it but in the head sample: oracle_tnslsnr, philips_hue, ipp_cups, spotify_connect, ldap, fast_reverse_proxy, ntrip. The sparse null percentages in this paragraph are from the head sample.

## Key
No single-column key. Proposed row key: (coalesce(ip_str, ipv6), port, transport). It is NOT unique in the sample:
2,224 IPv4 rows repeat an ip:port:transport in the spread sample (2.3%; head sample 4,109, 4.1%). Company key (`company_id`) is to be built in stage 2.

## Known issues
- See `docs/ISSUES.md` entries RAW-001 to RAW-012.
- Majority of rows belong to infrastructure owners: 83.8% of rows have an org on the denylist (exact + prefix + pattern); 87.6% of rows are infrastructure by the D4 rule (head sample: 87.4% and 90.6%).

## Denylist candidates
- Proposed in `context/denylist.txt` (222 exact entries), `context/denylist_prefixes.txt` (40 prefix families), `context/denylist_patterns.txt` (3 patterns) and `context/cert_default_names.txt` (57 default cert O values). Rule definitions are in the file headers; matcher in `scripts/denylist_match.py`. Original list was 225 entries, exact lowercase match on org, isp or cloud.provider. Top: google llc,
  incapsula inc, amazon.com, inc., aliyun computing co., ltd, cloudflare, inc., aceville pte.ltd., internet rimon, korea telecom.
- Not approved; the long tail needs rule-based matching (cloud/cdn tags, name patterns).
