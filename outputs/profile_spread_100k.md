# Profile: data/sample/spread_100k.jsonl (seek-spread sample, decision D3)

Produced by data-integrator on branch `feat/data-integrator/spread-sample`. Builder: `scripts/build_spread_sample.py`
(`--positions 1000 --lines 100 --seed 42`). Figures come from DuckDB queries (read_json_auto, sample_size=20000,
maximum_object_size=33554432, ignore_errors=true) and the rules in `context/denylist*.txt` applied through
`scripts/denylist_match.py`. Percentages are of 100,000 rows. The head-sample column is the same queries re-run on
`data/raw/sample_100k.jsonl` (so it can differ slightly from `outputs/profile_sample_100k.md`, which used the old 225-entry exact list).

## 1. Sample build and verification
- Source: decompressed `D:/Cyber_DataSet/2026-09-14T10-00-00.json`, 84,607,841,578 bytes. 1,000 positions at stride
  84,607,841 bytes, each jittered by a seeded random 0 to half a stride (first position is byte 0, last is 84,532,939,917 = 99.91% of the file).
  At each position: skip to the next newline, read 100 complete lines. Build time 4.3 s; output 1,019,584,854 bytes.
- Rows 100,000; invalid JSON lines 0; duplicate lines 0 (md5 per line); rebuild with the same seed is byte-identical.
- Coverage: block timestamps run 2026-09-14 09:59:27 (block 1) via 10:14, 10:26, 10:44 (blocks 251, 501, 751) to 10:59:55 (block 1000).
  Row timestamps span 09:54:53 to 11:05:46 (about 71 minutes; the architecture doc says 61 minutes from a probe).
  738 of 999 consecutive block pairs go forward in time, as expected for a file that is only locally interleaved.
- The script refuses output paths under `data/raw/` and under the source dataset folder (both tested).

## 2. Headline comparison (head sample vs spread sample)
| metric | head 100K | spread 100K | note |
|---|---|---|---|
| rows / top-level columns | 100,000 / 78 | 100,000 / 85 | 14 rare protocol structs only in spread, 7 only in head (see ISSUES RAW-011) |
| timestamp range | 09:54:28 - 10:06:32 | 09:54:53 - 11:05:46 | head covers about 12 min, spread about 71 min |
| Infrastructure share, D4 rule | 90,566 (90.57%) | 87,632 (87.63%) | D4: org/isp/cloud.provider on exact, prefix or pattern list, OR cloud.provider set, OR cloud/cdn tag |
| Rows surviving (not infrastructure) | 9,415 (9.41%) | 12,336 (12.34%) | 12,290 (12.29%) after dropping noise rows |
| org on denylist (exact+prefix+pattern) | 87.41% | 83.76% | org column only |
| org on denylist, exact list only | 86.85% | 83.28% | prefix rules add 0.48 pt in spread |
| port 12304 | 10,608 (10.61%) | 218 (0.22%) | expected about 2% was not reproduced, see 3 |
| module `auto` | 58.47% | 52.71% | |
| org == isp (exact) | 59,257 (59.26%) | 60,630 (60.63%) | 66.3% vs 66.5% of rows with both set (89,343 / 91,134) |
| org null / isp null | 0.17% / 10.53% | 0.20% / 8.72% | |
| distinct org (exact string) | 5,535 | 6,579 | |
| rows with vulns / KEV | 3,220 / 1,819 | 3,076 / 1,807 | |
| cert expired / expires within 30 d | 468 / 239 | 598 / 362 | of 7,910 vs 9,833 rows with a cert |
| eol-product or eol-os tag | 1,550 | 1,582 | |
| legacy TLS offered (SSLv2/3, TLS1.0/1.1) | 1,384 | 1,268 | |
| risky-port rows (20 ports, see 5) | 2,049 | 3,335 | 1433, 25, 161, 5985 are larger in spread |
| honeypot tag / RAT module rows | 679 / 739 | 583 / 505 | |
| distinct IPv4 / IPv6 rows | 86,450 / 587 | 83,301 / 1,468 | |
| repeated ip:port:transport rows | 4,109 | 2,224 | fewer in spread; consistent with duplicates being local (hypothesis) |

Expected values in the brief were "about 86%" infrastructure, "about 10%" surviving and "about 2%" port 12304.
Measured: 87.63% (block-clustered standard error 0.39 pt), 12.34% and 0.22%. Infrastructure and surviving shares are
1.6 and 2.3 points off the expectation, which is outside two standard errors for the infrastructure share; the
architecture probe itself saw 3.6% to 20.2% survival per window, so 12% is within that range. Port 12304 is 0.22% (SE 0.08 pt),
well below 1.7% from the probe: it occurs in only 53 of the 1,000 blocks, in bursts (one block holds 59 such rows).
Conclusion: D3 works (the 12304 burst no longer dominates), but the "about 2%" expectation was too high.

## 3. Null rates, key columns (spread, % of 100,000 rows)
| column | null % (head) | null % (spread) |
|---|---|---|
| org | 0.17 | 0.20 |
| isp / asn | 10.53 | 8.72 |
| product | 82.61 | 80.62 |
| version | 93.58 | 93.63 (16 empty strings) |
| os | 97.72 | 97.54 |
| cpe23 | 78.61 | 75.83 |
| tags | 32.25 | 34.17 |
| hostnames / domains empty array | 24.62 | 27.07 |
| cloud.provider | 58.04 | 59.46 |
| location.country_code | 0.02 | 0.02 |
| vulns | 96.78 | 96.92 |
| ssl (struct) / ssl.cert.expires | 92.09 | 90.17 |
| ssl.cert.subject.O | 98.29 | 97.85 (2,152 rows, 849 distinct) |
| http (struct) | 68.13 | 66.83 |
| ip_str (null = IPv6) | 0.59 | 1.47 |

## 4. Entity question
- 6,579 distinct org strings (6,500 after lowercase+trim). Top 5 orgs 58,221 rows (58.2%), top 10 64,237 (64.2%), top 100 82,209 (82.2%);
  4,369 orgs (66.4% of distinct) appear once. Head: 61.6%, 68.5%, 84.9%, 66%.
- Surviving rows come from 5,507 distinct orgs (head 4,568) and 11,847 distinct IPv4 addresses.
- Infrastructure share by reason: 87,626 rows hit a denylist rule on org/isp/cloud.provider/IP; 6 more rows are infrastructure only
  through a cloud/cdn tag; 0 only through cloud.provider. So the tag and cloud.provider rules add almost nothing on top of the lists in this sample,
  but 25,095 list-matched rows carry no cloud/cdn tag and no cloud.provider, so the lists are doing real work.
- Only 6 rows are tagged cloud/cdn while off the lists; 87,632 rows are infrastructure in total.
- Top orgs: Google LLC 31,328; Incapsula Inc 16,431; Cloudflare, Inc. 3,896; Amazon.com, Inc. 3,697; Aliyun Computing Co., LTD 2,869;
  ACEVILLE PTE.LTD. 1,490; Amazon Technologies Inc. 1,350; Korea Telecom 1,173; Internet Rimon 1,124; Aliyun Computing Co.LTD 879;
  METEVERSE LIMITED 868 (+ `Meteverse Limited.` 804); Microsoft Corporation 800; Akamai Technologies 648; Alibaba Cloud - HK 627.
- Top isp: Google LLC 25,212; Incapsula Inc 16,539; null 8,717; Amazon.com 7,322; Cloudflare 3,952; Hangzhou Alibaba Advertising 3,734.
- cloud.provider: null 59,463; Google 28,382; Amazon 7,322; Alibaba Cloud 2,173; Azure 869; Linode 718; Vultr 458; DigitalOcean 298;
  Tencent Cloud 173; Oracle Cloud Infrastructure 134.
- Top surviving orgs (rows): Salesforce.com 175; null org 154; Netflix Streaming Services 144; Los Angeles Municipal Court 89;
  ServiceNow (`ServiceNow, Inc.` 85 + `SERVICENOW, INC.` 70); Internet Service Provider 65; The Prudential Insurance Company of America 58;
  Weebly 49; ZOHO 45 + Zoho Corp 37; TELEFONICA BRASIL 39; Administracion Nacional de Telecomunicaciones 36; Mullvad VPN AB 35.
- Denylist leakage still present among survivors. A keyword scan (telecom, telekom, telefon, broadband, internet service, chinanet,
  communications, mobile, cable, vpn, hosting, weebly, datacenter, cloud, server in the org text) matches 2,778 surviving rows (22.5% of
  the 12,336). Examples: Internet Service Provider 65, Weebly 49, Mullvad VPN 35, Bretagne Telecom 29, CHINANET provincial networks,
  EGIHosting 20, WHG Hosting Services 20, Interserver 16, CloudFly Net 23. The keyword scan is a heuristic and not verified; it shows the
  hand-picked list plus prefix families do not cover the ISP/hosting long tail. Left for the owner and data-quality-engineer.
- Cert subject O: 2,152 rows; 1,271 of them are on infrastructure rows. Top: Salesforce, Inc. 190; Google Inc 144; Plesk 69; Microsoft 68;
  Cisco Systems 32; Incapsula 31; Fortinet 30; Acme Co 20; Default Company Ltd 14; Internet Widgits Pty Ltd 9.
  `context/cert_default_names.txt` has 57 entries built from these values.

## 5. Other columns
- port: 80 13,893 (13.89%); 443 6,640; 179 2,069 (2.07%, BGP); 7547 909; 81 855; 9443 753; 993 694; 8443 667; 587 619; 1433 606; 25 554; 22 551.
  The head sample's top ports (12304, 14903, 18113, 8568, 5503, 1023, 3333, 9188) were sweep bursts and are gone from the spread sample's top 12.
- country: US 50.92%, SG 17.38%, CN 5.32%, DE 2.96%, GB 2.20%, JP 1.84%, FR 1.69%, IL 1.51%, KR 1.46%, HK 1.44%. 177 distinct country codes (head 160).
- transport: tcp 98,824, udp 1,176.
- tags (rows): cloud 40,537; cdn 25,083; eol-product 1,560; self-signed 1,026; starttls 669; honeypot 583; proxy 477; iot 159; vpn 137; database 102.
- `data` (banner text): max 43,349 characters, 99th percentile 2,253.

## 6. Urgency signals (all rows, then rows that survive the denylist)
| signal | all rows | surviving rows (12,336) |
|---|---|---|
| has vulns | 3,076 (3.08%) | 1,010 |
| contains KEV CVE | 1,807 (1.81%) | 617 |
| max CVSS >= 9.0 / 7.0 to 8.9 | 1,709 / 1,108 | not split |
| cert present | 9,833 | not split |
| cert expired (boolean) | 598 | |
| cert not yet expired, expires within 30 days of scan | 362 | |
| expired or within 30 days | 960 | 348 |
| cert expires in 30 to 90 days | 4,906 | |
| eol-product or eol-os tag | 1,582 (eol-product 1,560, eol-os 22) | 457 |
| legacy TLS offered | 1,268 | 228 |
| risky port (22,23,21,25,53,161,445,3389,3306,5432,5900,5985,6379,27017,9200,11211,1433,2375,502,5060) | 3,335 | 1,114 |
Risky ports by rows: 1433 606; 25 554; 22 551; 161 394; 5985 259; 53 231; 21 158; 3389 89; 3306 86; 5060 60; 9200 47; 445 45.
Cert expiry dates are measured against each row's own timestamp. Sentinel dates: 2 certs with `4096...`, none with `0001...` (head: 1 and 2).
Most vulnerable, expired or legacy rows sit on infrastructure; only about a third (vulns 33%, KEV 34%, eol 29%, legacy TLS 18%) are on surviving rows.

## 7. What changed for development
- Use the spread sample, not the head sample, for any port-based signal or calibration.
- Expect about 12% of rows (about 5,500 distinct orgs per 100K rows) to survive; the list-based filter is not enough on its own.
- The raw column set is not stable between samples: 85 columns here, 78 in the head sample. Stage 1 must select named columns.
