# Schema: raw layer (DRAFT, proposed by data-integrator, not yet approved)

Source file: `data/raw/sample_100k.jsonl` (first 100,000 lines of a Shodan-style dump; full file is 84 GB, outside the repo)
| Rows: 100,000 | Produced by: external crawler (no script in this repo) | Grain: one row per service banner on one IP:port (+ transport)

Read with DuckDB `read_json_auto(path, sample_size=20000, maximum_object_size=33554432, ignore_errors=true)`: 78 top-level columns.
Array length: use `len()`. Map size: `cardinality(vulns)` (cardinality works on MAPs only). Null % are of 100,000 rows.
Struct fields are addressed as `ssl.cert.expires` etc. Null % for nested fields is the share of ROWS where the field is null.

## Core columns (documented in full)
| column | type | null % | meaning | used for |
|---|---|---|---|---|
| ip_str | VARCHAR | 0.59 | IPv4 dotted string; null on the 587 IPv6 rows | key |
| ip | BIGINT | 0.59 | IPv4 as integer, matches ip_str on all rows | ignore |
| ipv6 | VARCHAR | 99.41 | IPv6 address (set only when ip_str is null) | key |
| port | BIGINT | 0 | service port; 80 14.3%, 12304 10.6%, 443 7.2% | urgency (risky ports) |
| transport | VARCHAR | 0 | tcp 98.94%, udp 1.06% | ignore |
| timestamp | VARCHAR | 0 | ISO scan time; whole sample spans 2026-09-14 09:54 to 10:06 | urgency (weak here) |
| org | VARCHAR | 0.17 | registered owner of the IP block; 5,535 distinct; mostly hosting/cloud/CDN | entity, fit |
| isp | VARCHAR | 10.53 | ISP/provider; null exactly when asn is null | entity (denylist) |
| asn | VARCHAR | 10.53 | autonomous system `AS<n>`; 3,663 distinct | entity (secondary) |
| product | VARCHAR | 82.61 | detected software (nginx, Apache httpd, OpenSSH ...) | fit, urgency |
| version | VARCHAR | 93.58 | free-text version of product; 31 empty strings | urgency |
| os | VARCHAR | 97.72 | detected OS | fit |
| devicetype | VARCHAR | 99.94 | device class (router, webcam ...) | fit (weak) |
| info | VARCHAR | 96.61 | extra banner info | ignore |
| cpe23 / cpe | VARCHAR[] | 78.61 / 78.60 | CPE identifiers for product/os | urgency (version match) |
| hostnames | VARCHAR[] | 0 (24.62 empty) | reverse-DNS names; use `len()` | entity |
| domains | VARCHAR[] | 0 (24.62 empty) | registrable domains of hostnames; mostly provider domains | entity (weak) |
| tags | VARCHAR[] | 32.25 | Shodan labels: cloud, cdn, eol-product, self-signed, honeypot ... | fit, urgency, exclusion |
| location.country_code | VARCHAR | 0.02 | ISO country of the IP; 160 distinct, US 51% | fit |
| location.city | VARCHAR | 0.02 | city | ignore |
| cloud.provider | VARCHAR | 58.04 | cloud vendor name (Google, Amazon, Azure ...), 11 values | exclusion |
| cloud.service / cloud.region | VARCHAR | 91.63 / 60.52 | cloud product and region | ignore |
| vulns | MAP(CVE -> STRUCT) | 96.78 | CVE map; struct has cvss, cvss_version, epss, kev, verified, summary, references | urgency |
| vulns[*].cvss | DOUBLE | 0 of entries | CVSS score; row max median 9.8 | urgency |
| vulns[*].kev | BOOLEAN | n/a | on CISA KEV list; 1,819 rows contain one | urgency |
| ssl | STRUCT | 92.09 | TLS data; 7,910 rows | urgency |
| ssl.cert.expires / issued | VARCHAR | 92.09 | `YYYYMMDDHHMMSSZ` text; sentinels 0001... and 4096... exist | urgency |
| ssl.cert.expired | BOOLEAN | 92.09 | expired relative to scan time; 468 true | urgency |
| ssl.cert.subject.CN / O | VARCHAR | 92.18 / 98.29 | cert common name and organisation | entity (secondary) |
| ssl.cert.issuer.O | VARCHAR | 92.71 | issuing CA | ignore |
| ssl.versions | VARCHAR[] | 92.09 | TLS versions; `-` prefix = refused | urgency |
| http | STRUCT | 68.13 | HTTP data: status, title, host, server, waf, headers, components, html | fit (weak) |
| http.title / host / server / waf | VARCHAR | 78.92 / 68.13 / 77.46 / 88.51 | page title, vhost, server header, WAF | fit (weak) |
| _shodan.module | VARCHAR | 0 | collector module; auto 58.5%, includes RAT/C2 modules | exclusion |
| ntlm.dns_domain_name / netbios_domain_name | VARCHAR | 99.92 | Windows domain names | entity (rare) |
| data | VARCHAR | 0 | raw banner text (often empty; max 37,228 chars) | ignore |
| hash | HUGEINT | 0 | banner hash | ignore |
| opts | MAP | 0 | collector options | ignore |
| title, html, screenshot | VARCHAR / STRUCT | about 100 / 99.99 / 99.98 | page title, HTML, screenshot | ignore |

## Sparse protocol structs (all more than 92% null; not profiled in depth)
ssh 99.43, dns 99.79, mac 99.70, snmp 99.61, ntp 99.87, ftp 99.91, telnet 99.92, mysql 99.93, vnc 99.93, ntlm 99.92,
hikvision 99.83, rdp_encryption 99.94, isakmp 99.95, smb 99.98, mdns 99.99, mqtt 99.99, redis 99.99, mongodb 100.0,
ldap 100.0, bgp 100.0, fortinet 99.98, hp_ilo 100.0, kubernetes 99.97, node_exporter 99.97, open_dir 99.95,
mikrotik_routeros 99.98, mikrotik_winbox 99.98, dahua / dahua_dvr_web / ip_camera 99.94 to 99.99, and 20 more single-protocol
structs (pptp, plex, mysqlx, msrpc, synology_dsm, cisco_ipsla, fast_reverse_proxy, mcp, draytek_vigor, ntrip, philips_hue,
oracle_tnslsnr, spotify_connect, ipp_cups, dav, minecraft, ...). Role: urgency (exposed service) where a risky service is
the finding, otherwise ignore. cpe23_hash is 80.97 null.

## Key
No single-column key. Proposed row key: (coalesce(ip_str, ipv6), port, transport). It is NOT unique in the sample:
4,109 IPv4 rows repeat an ip:port:transport (4.1%). Company key (`company_id`) is to be built in stage 2.

## Known issues
- See `docs/ISSUES.md` entries RAW-001 to RAW-008.
- Majority of rows belong to infrastructure owners: 86.8% of rows have an org on the denylist candidates.

## Denylist candidates
- Proposed in `context/denylist.txt` (225 entries, exact lowercase match on org, isp or cloud.provider). Top: google llc,
  incapsula inc, amazon.com, inc., aliyun computing co., ltd, cloudflare, inc., aceville pte.ltd., internet rimon, korea telecom.
- Not approved; the long tail needs rule-based matching (cloud/cdn tags, name patterns).
