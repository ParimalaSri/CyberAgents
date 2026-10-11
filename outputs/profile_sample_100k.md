# Profile: data/raw/sample_100k.jsonl (first 100,000 lines of the full dump)

Produced by data-integrator on branch `feat/data-integrator/profile-raw`. All figures come from DuckDB queries
over the sample (read_json_auto, sample_size=20000, maximum_object_size=33554432, ignore_errors=true) and a narrow
flattened table kept outside the repo. Percentages are of 100,000 rows unless stated.
This is a one-sample profile: nothing here was checked against the full 84 GB file.

## 1. Shape
- 100,000 rows (one per service banner on one IP:port), 78 top-level columns, 1.11 GB.
- 8 columns are present on every row (data, opts, port, timestamp, hash, transport, location, _shodan); hostnames and domains too (maybe empty arrays).
- Most of the 78 columns are protocol-specific structs that are more than 92% null (ssl 92.09%, ssh 99.43%, snmp 99.61%,
  and so on; full list in `context/schema.md`).
- Rows are IPv4 (99,413) or IPv6 (587). The 587 IPv6 rows have `ip` and `ip_str` null and the address in `ipv6`.
- `timestamp` spans one 12-minute window: 2026-09-14 09:54:28 to 10:06:32. No recency signal exists inside this sample.

## 2. Null rates (key columns)
| column | null % | note |
|---|---|---|
| org | 0.17 | 173 rows |
| isp | 10.53 | identical rows as asn (10,534 rows null in both) |
| asn | 10.53 | string like `AS396982` |
| product | 82.61 | |
| version | 93.58 | 31 rows are empty string |
| os | 97.72 | |
| cpe23 / cpe | 78.61 / 78.60 | |
| devicetype | 99.94 | |
| info | 96.61 | |
| top-level `title` | about 100 | `http.title` is present on 21.08% instead |
| tags | 32.25 | null, not empty array |
| hostnames / domains | 0 null, 24.62% empty array | 75,382 rows non-empty; hostnames and domains are non-empty on exactly the same rows |
| cloud (struct) | 58.04 | cloud.service 91.63 null, cloud.region 60.52 null |
| location.country_code | 0.02 | |
| vulns | 96.78 | 3,220 rows have at least one CVE |
| ssl (struct) | 92.09 | 7,910 rows; same count for ssl.cert |
| http (struct) | 68.13 | 31,873 rows |
| ssh (struct) | 99.43 | 570 rows |
| ip_str | 0.59 | IPv6 rows |

Note on two false starts: a first pass computed `ssl IS NOT NULL` as a boolean and reported 0% null; that is a boolean
column being tested for null, not the struct. The figures above use the raw struct and are correct.

## 3. Entity question
- Usable org value: 99.83% of rows have a non-null org (99,827 rows). Org is almost never missing, but most values are
  infrastructure owners, not customers (see below).
- org equals isp (exact): 59,257 rows = 59.3% of all rows, 66.3% of the 89,343 rows where both are set.
  Case-insensitive: 59,911. org set and isp null: 10,484 rows. org null and isp set: 123 rows. Both null: 50 rows.
- Distinct values: org 5,535 (5,462 after lowercase+trim), isp 3,421, asn 3,663, IPv4 addresses 86,450,
  country 160, cloud provider 11.
- Concentration: top 5 orgs = 61,559 rows (61.6%); top 10 = 68,496 (68.5%); top 100 = 84,938 (84.9%).
  3,656 orgs (66% of distinct orgs) appear in exactly one row.
- Name variants of one owner are common: `Incapsula Inc` (17,906) / `Incapsula Inc.` (584) / `Incapsula Network` (48);
  `Aliyun Computing Co., LTD` (3,508) / `Aliyun Computing Co.LTD` (1,143); Amazon has `Amazon.com, Inc.`,
  `Amazon Technologies Inc.`, and at least 12 `Amazon Data Services <region>` values; Scaleway has at least 6 spellings;
  OVH has at least 6. Casing-only collapses 73 org values, but the semantic variants need rules.
- Google LLC as org (33,149 rows, 33.1%) is Google Cloud VM address space, not Google as a prospect: 28,464 distinct IPs,
  99.5% US, reverse names `<ip>.bc.googleusercontent.com`, ASN mostly AS396982 (21,347), 7,475 of these rows have no
  ASN/ISP. A single port, 12304, carries 7,154 of them with `shodan_module=auto`.
- The domains column mostly holds the infrastructure owner's reverse-DNS domain: googleusercontent.com 32,910,
  incapdns.net 16,158, amazonaws.com 4,194, cloudfront.net 2,788. Domains are therefore not a clean customer identifier.

### Denylist coverage (exact match against the 225-entry candidate list in `context/denylist.txt`)
- Rows whose org is on the list: 86,817 (86.8%). Rows whose org, isp or cloud.provider is on the list: 90,493 (90.5%).
- Rows with none of the three on the list: 9,507 (9.5%). These span 4,607 distinct orgs; only 18 orgs have 20 or more rows.
- Row counts by group (org match only, rows): hyperscaler/public cloud 48,917; CDN/edge/security proxy 23,575;
  hosting/VPS/website builders 8,134; ISP/telecom 6,191. These are hand-picked top values; the long tail is not covered.

Top denylist candidates by org rows (count is rows in the sample):
Google LLC 33,149; Incapsula Inc 17,906 (+ Incapsula Inc. 584); Amazon.com, Inc. 3,869; Aliyun Computing Co., LTD 3,508
(+ Aliyun Computing Co.LTD 1,143); Cloudflare, Inc. 3,127; ACEVILLE PTE.LTD. 1,853; Internet Rimon 1,415;
Amazon Technologies Inc. 1,403; Korea Telecom 1,123; Fly.io, Inc. 829; Microsoft Corporation 722; Akamai Technologies, Inc. 702;
Linode 697; Hetzner Online GmbH 545; Zscaler, Inc. 513; Amazon Data Services NoVa 450; Alibaba Cloud - HK 443;
Uzbektelekom Joint Stock Company 411; A100 ROW GmbH 407; DigitalOcean, LLC 341; Vultr Holdings, LLC 283.

Top isp values (rows): Google LLC 24,550; Incapsula Inc 18,063; Amazon.com, Inc. 7,610; Hangzhou Alibaba Advertising 4,615;
Cloudflare, Inc. 3,187; Level 3 Parent, LLC 2,754; Internet Rimon LTD 1,415; Korea Telecom 1,124.

Top cloud.provider (rows): Google 29,387; Amazon 7,600; Alibaba Cloud 2,273; Linode 838; Azure 768; Vultr 437;
DigitalOcean 365; Tencent Cloud 157; Oracle Cloud Infrastructure 128. Null 58.04%.
Tags: `cloud` on 41,960 rows, `cdn` on 26,098 rows (both usable as additional exclusion flags).

Rows that look like possible customers (org not on the list), examples with sample counts: Fiserv Solutions 280,
Egnyte 269, Avago Technologies 244, Los Angeles Municipal Court 104, The Prudential Insurance Company of America 81,
Equifax 73, Wal-Mart Stores 42, KeyBank National Association 41, Adobe 41, OCLC 40, Salesforce.com 31, HubSpot 25.
Per-org volumes are small (tens to hundreds of banners) so volume is a weak size proxy.

Borderline, left for the human: IBM, Oracle Corporation, Microsoft Corporation (listed as hyperscaler for their cloud
address space; the same names could also be real accounts), Shopify / Squarespace / Wix / Vercel / Bitly (SaaS platforms
listed as hosting), Fastly, Palo Alto Networks, Zscaler (security vendors that are also competitors or channel).

## 4. Other columns
- port: top 80 (14.33%), 12304 (10.61%), 443 (7.15%), 14903 (2.32%), 18113 (2.04%), 8568, 5503, 1023, 3333, 9188.
  Many high ports are tied to Google LLC / Zscaler / Uzbektelekom with `shodan_module=auto` (58.47% of rows); likely
  scanner-observed noise or proxy ports rather than customer services (hypothesis).
- transport: tcp 98.94%, udp 1.06%.
- country: US 50.95%, SG 18.78% (Incapsula 16,357 + Aceville 1,452 of 18,778), CN 6.18%, DE 2.79%, GB 2.31%, JP 1.90%,
  IL 1.82%, FR 1.41%, KR 1.39%, HK 1.24%.
- product (top, of 17,394 non-null): nginx 4,347; CloudFront httpd 2,221; Apache httpd 2,082; AWS ELB 1,145; OpenSSH 1,045;
  AkamaiGHost 831; OpenResty 656; Microsoft IIS httpd 585; CloudFlare 391. Many products are CDN/proxy front ends.
- version (top): 2.0 (1,327), 10.0 (457), 1.24.0 (318), 7.4 (303), 1.18.0 (253). Version strings are free text and
  product-specific (for example `9.6p1 Ubuntu 3ubuntu13.19`), so they cannot be compared numerically without parsing.
- os (top): Windows 866, Ubuntu 633, Linux 465. Only 2,280 rows have an os.
- tags (rows): cloud 41,960; cdn 26,098; eol-product 1,527; self-signed 804; honeypot 679; proxy 580; starttls 286;
  iot 181; vpn 140; database 99; eol-os 23; compromised 1; c2 1; tor 1. 67,746 rows have at least one tag.
- shodan_module: auto 58,467; http 14,597; https 7,460; http-simple-new 6,420; https-simple-new 2,743; also RAT/C2
  fingerprint modules (darktrack-rat 217, remcos-pro-rat 182, orcus-rat 142; 739 rows end in `rat`): attacker infrastructure, not customers.
- http: status present on 31,873 rows (200: 9,078; 301: 4,423; 403: 4,321; 404: 3,361); title 21,081; waf 11,495.

## 5. Vulnerabilities
- 3,220 rows (3.22%) have a non-empty vulns map; 96,780 null; no empty maps.
- Highest CVSS per row: 4.0-6.9 244 rows, 7.0-8.9 1,118 rows, 9.0+ 1,858 rows; none below 4.0. Median of row max = 9.8,
  10th percentile 7.5. CVSS is non-null on all 148,562 CVE entries.
- 1,819 rows (1.82%) contain at least one CVE flagged KEV (2,361 KEV CVE entries).
- EPSS (max per row) is saturated: median 0.99957, 90th and 99th percentile 0.99999. Little discriminating power as a row score.
- Rows with vulns average 46.1 CVEs, max 778. 877 rows share an identical list of old CVEs (CVE-2012-4001, CVE-2013-0941 ...)
  on Apache httpd 2.0.54 / 2.4.x banners, which indicates CVEs inferred from banner version, not confirmed (hypothesis).
  `verified=true` appears on 28 of 148,562 CVE entries.
- Top CVEs: CVE-2023-44487 1,018 rows; CVE-2025-23419 1,001; CVE-2026-42535 787.
- Which orgs carry vulns: Aliyun 320 + 106, Amazon Technologies 160, DigitalOcean 97, Amazon.com 95, Hetzner 92,
  Google 57. Vulnerable rows are concentrated in hosting providers, which are denylisted; the exposure belongs to
  tenants who are not visible as the org.
- Product of vulnerable rows: nginx 1,106, Apache httpd 879, OpenSSH 490, null 320.
- `eol-product` tag: 1,527 rows (nginx 1,288, Apache httpd 115, MySQL 25) across 512 distinct orgs (with eol-os).

## 6. SSL / certificates
- 7,910 rows (7.91%) carry ssl.cert. Cert subject CN present on 7,817 rows; subject O only on 1,711 rows (1.71%);
  issuer O on 7,289 rows (7.29%).
- Expiry field `ssl.cert.expires` is text `YYYYMMDDHHMMSSZ`. `expired` boolean: true 468 (5.9% of cert rows, 0.47% overall),
  false 7,442. The boolean agrees with expires < timestamp on all 7,910 rows checked.
- Time to expiry relative to row timestamp: expired 468; under 30 days 239; 30-90 days 3,844; over 90 days 3,359.
- Sentinel dates: 1 cert with expires `0001...`, 2 with `4096...`, 1 issued `0001...`.
- Offered legacy protocols (ssl.versions without leading minus): SSLv3 49, SSLv2 5, TLSv1 1,289, TLSv1.1 1,366;
  1,384 rows enable at least one of SSLv2, SSLv3, TLSv1, TLSv1.1. `-` prefixed entries mean the version was refused.
- Top cert subject O values are vendor defaults and platforms (Google Inc 153, Microsoft 76, Plesk 35, Acme Co 30).
  Cert org could name the real owner for a few thousand rows at most.

## 7. Risky exposed services (row counts, any org)
22: 524; 161 (SNMP): 382; 53: 222; 21: 139; 25: 115; 3389 (RDP): 96; 3306: 93; 5060: 60; 5432: 46; 445: 40; 9200: 40;
11211: 38; 5985: 38; 6379: 37; 27017: 36; 502 (Modbus): 32; 5900: 32; 23: 30; 2375: 25; 1433: 24.
Small counts per service in this sample; recency and per-company counts are not available without entity grouping.

## 8. Duplicates and structure
- 4,109 IPv4 rows are extra rows for an ip:port:transport already seen (4.1%). Cause not established.
- 86,450 distinct IPv4 across 99,413 IPv4 rows; most IPs appear once, 6,522 appear twice.
- `data` (banner text) is empty at the median; 99th percentile 2,153 characters; max 37,228.
- The sample is the first 100K lines of the dump, not a random sample; its 12-minute timestamp window suggests the dump
  is in crawl order. Whether the full file covers more dates is unknown.

## 9. Candidate columns (proposal, for human approval)
Fit (is this our buyer):
- Strong: `org` (after denylist and normalisation), `ssl.cert.subject.O` (small coverage, high precision).
- Medium: `location.country_code`, `hostnames`/`domains` (only after dropping infrastructure domains),
  `product`/`os`/`cpe23` (stack proxy, 78 to 98% null), tags `database`, `ics`, `medical`, `iot`.
- Weak or biased: `asn`/`isp` (identify the provider, not the tenant), row/IP counts per org (hosting providers dominate),
  `cloud.provider` (exclusion flag only), http.title.
Urgency (do they need help now):
- Strong: `vulns` max CVSS and KEV flag (3.2% and 1.8% of rows), `ssl.cert.expired`/`expires` (7.9% coverage),
  tags `eol-product`/`eol-os` (1.5%), legacy ssl.versions, exposed risky ports (22, 3389, 445, 3306, 6379, 27017, 9200, 5900, 23, 2375).
- Medium: product + version (outdated version needs a version table; version 93.58% null), `ssh`, `ntlm` (0.08% only).
- Weak: `timestamp` (12-minute window, no variation), EPSS (saturated), `verified` flag (28 entries).
- Exclusion flags: tags `honeypot` (679), `compromised`, `c2`, `tor`, RAT modules (739).
Entity grouping:
- `org` normalised (strip legal suffix, punctuation, case, merge regional variants) is the primary key; `asn` secondary
  grouping and denylist aid; `ssl.cert.subject.O`/CN and non-infrastructure `domains` as secondary evidence;
  `ntlm.dns_domain_name` is rare (85 rows).
- Confidence: org normalised, high for coverage (99.83% non-null), low for customer identity (86.8% of rows are denylisted).
