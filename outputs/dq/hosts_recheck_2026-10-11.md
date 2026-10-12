# Hosts layer recheck after D6/D7 (2026-10-11), data-quality-engineer

Verdict: PASS on the spread sample (97,758 rows, commit e4c3867). NOT the full file; a PASS here does not authorise prod. Names-only judgement, single reviewer.
Contract: `context/contracts/hosts.yml` (94 checks, 94 pass; report `outputs/dq/hosts_2026-10-11.md`). Extra checks: `check_hosts_extra.py --narrow <scratch parquet of the raw sample>` RESULT PASS. Tests: 27 pass.
Mutation test (copies in the scratchpad, never the data file): breaking `njrat`/`xiaongmai-backdoor` noise flags, a cert_o `name_norm`, a `dup_count` made the contract fail 4 and 5 checks as designed.

## Recomputation, author vs mine
| item | author | mine | match |
|---|---|---|---|
| raw rows | 100,000 | 100,000 (all have a host_ip) | yes |
| kept rows | 97,758 | 97,758 | yes |
| removed by dedupe | 2,242 | 2,242 (1,098 groups, 3,340 rows; 0 groups of one-timestamp copies = all true re-scans; kept row latest in all) | yes |
| sum(dup_count - 1) | 2,242 | 2,242; dup_count equals my per-key count on all rows | yes |
| infrastructure | 84,696 = 86.64% | 84,696 = 86.64% | yes |
| infra_reason mix | cloud_provider 39,572; tag_rule 21,289; org_exact 20,895; org_keyword 2,140; org_prefix 737; org_pattern 63; none 13,062 | identical | yes |
| identity_source | infrastructure_unresolved 83,064; org 12,804; noise 1,136; cert_o 557; null_org 197 | identical (shares sum 100.00%; resolved 13.67%) | yes |
| is_noise rows | 1,136 | 1,136 | yes |
| cert_date_invalid | 46 | 46 (my own date parser) | yes |
| per-row agreement (infra_reason, is_noise, identity_source, name_norm, cert_date_invalid), 97,758 rows | 0 expected | 0 disagreements on each, 0 missing | yes |
| cert_o usability | | 557 by me, 557 by stage; only-mine 0, only-stage 0, name differs 0; cert_o names in cert defaults 0 | yes |

Caveat: my reimplementation uses the shared matcher (as asked), so it proves the stage applies the decided rules, not that the rules are right.

## DQ-001..004
- DQ-001 FIXED: 0 of 428 distinct cert_o names hit any shared rule or cert default; the three named telecom names, Huawei, Sierra Wireless, Comcast, dis, Meta, Facebook, Apple, Netflix have 0 cert_o rows.
- DQ-002 ACCEPTED (D7.2), recorded; decision not edited. DQ-003 unchanged (measurement). DQ-004 CLOSED by design (D6.1): 552 rows match the new pattern, all noise; njrat78 (2) and xiaongmai-backdoor (183) not noise.
- New: DQ-005 (tail of operators among one-row org names, about 9 of 20 sampled, names only), plus PIPE-004 measurement.

## Judgement checks (eyes)
- 10 random rows (reservoir seed 11): Cloudflare, Incapsula, Amazon rows are infrastructure_unresolved with plausible reasons; Hosting Ukraine caught by keyword; org rows Avago, Digital Core, PDR, Blazing SEO; `TIM S/A` and `IP hosted by Host-Unlimited.de` are org (operators that survive, DQ-005).
- Top 20 names by rows: Egnyte 330, Fiserv Solutions 328, Wal-Mart 248, Avago 236, Salesforce 181, ServiceNow 155, TGS 148, Zoho 95, LA Municipal Court 86, Equifax 70, Guangzhoushi Guangbodianshiwangluo 64 (broadcast network), Prudential 58, Ultimate Software 53, NYMEX 42, Huawei International 34 (Huawei own estate, doubtful), ... Netflix and Meta are gone from the list (D7.1).
- 20 random single-row org names (seed 5): 9 of 20 read as operator, host or research network by name (DQ-005).
- No score columns exist at this layer, so top and bottom 20 by score is not applicable.

## cert_o tail (PIPE-004 input)
557 cert_o rows, 428 distinct cert O strings (the author counted 420 after normalising). My regex (vendor words, hostname shape, long random uppercase, digits, underscores) flagged 57 names / 67 rows; I reviewed all of them, then 60 distinct unflagged names drawn with `random.Random(7).sample(sorted(names), 60)` (76 rows).
- Flagged, classified: TENANT 7 names / 8 rows (PostNord, Advantive, CTIA, Gemadept, NETSTARS, Samsung SDS, Tecnogest); UNSURE 4 / 7 (FIT2CLOUD 4 rows, FH, SMP_Portals, TMC); NOT-TENANT 46 / 52. Examples: device vendors Dell Inc., Grandstream, UBNT, ZTE, NETGEAR, Dahua, Foscam, Cradlepoint, Avigilon, Super Micro Computer, Hanwha Techwin, ASUSTeK, Samsung Electronics; firmware strings `OpenWrt16ef7d1c`, `Teltonika38b8a02e`, `ZenWiFi_XD4-58D0`, `ASUSWRT-Merlin-KoolShare`; hostnames `*.esecuritel.com`, `mail.kavzesmail.com`, `mail.89-96-141-44.ip12.fastwebnet.it`, `Historia.org.pl`; random strings `AHMHAFVKNR`, `JFYRFHEOWRJUWYDM`, `ZVZOWZYKN`; placeholders `Dummy`, `Internal`; operators/hosts `Aruba S.p.A.`, `o2switch`, `ispgateway`, `Beijing Baidu Netcom`, `AnchorFree`.
- Unflagged sample of 60: TENANT 52, UNSURE 6 (EOMA, Odin, Netlify, Heimdall Zone, SmartThings, cVuUnit), NOT-TENANT 2 (TIM S A, Dropcam). Tenants include JPMorgan, Morgan Stanley, UnitedHealth, Siemens, BBC, Ernst & Young (10 rows), Disney, Starbucks, BASF Digital Solutions.
- Estimate (unflagged part scaled from the sample: 371 names / 490 rows):
  - UNSURE counted NOT-TENANT (the stated rule): about 99.5 of 428 names = 23.2%; about 117 of 557 rows = 21.0% NOT-TENANT. TENANT share about 77% of names, 79% of rows.
  - UNSURE counted as tenant (lower bound): 13.6% of names, 11.7% of rows NOT-TENANT, TENANT share about 86% to 88%.
  - The sample of 60 has a wide interval (8 of 60 is 13% with a 95% interval of about 6% to 24%). Either way cert_o does not pass a 90% TENANT bar on this review. Informational; the decision belongs to the senior engineer. Cert_o is 0.57% of rows, so the effect on the account list is small, but the flagged classes are the ones a rep would see as obvious junk.

## Not verified
Not the full file (a PASS on the sample does not authorise prod; replace the 100000 constant in the contract with the full raw count). Names-only review by one reviewer (classes are judgement, no external lookup). The recompute ran from a narrow parquet of the same raw sample, not a second independent read of the 1 GB file. No stage-3/4 checks.

## Runner output (check_hosts_extra.py)
## Denylist on identity_source = 'org' rows (org and name_norm, shared rules)
- distinct (org, name_norm) pairs checked: 5,516; hits: 0

## Recomputation (author number vs mine)
- raw lines (narrow parquet used); parsed rows 100,000; rows with host_ip 100,000; distinct keys 97,758; hosts rows 97,758; removed 2,242
- duplicate groups 1,098 covering 3,340 rows; groups with a single distinct timestamp (true copies) 0
- raw keys missing from hosts 0; hosts keys not in raw 0; kept row not the latest timestamp 0
- sum(dup_count - 1) = 2,242; raw rows with host_ip minus hosts rows = 2,242; dup_count differing from my per-key count: 0
- infrastructure before dedupe (my matcher run, raw rows with host_ip): 86,759 of 100,000 = 86.76%
- infrastructure after dedupe (parquet): 84,696 of 97,758 = 86.64%
- per-row disagreement between my flags (matcher + D4/D6 rules in Python) and the parquet over 97,758 rows: {'infra_reason': 0, 'is_noise': 0, 'identity_source': 0, 'name_norm': 0, 'cert_date_invalid': 0, 'missing': 0}; examples []
- is_noise rows 1,136; cert_date_invalid rows 46 (mine: 46)
- infra_reason mix (parquet): [('cloud_provider', 39572, 40.48), ('tag_rule', 21289, 21.78), ('org_exact', 20895, 21.37), ('(null)', 13062, 13.36), ('org_keyword', 2140, 2.19), ('org_prefix', 737, 0.75), ('org_pattern', 63, 0.06)]; shares sum 99.99
- identity_source mix (parquet): [('infrastructure_unresolved', 83064, 84.97), ('org', 12804, 13.1), ('noise', 1136, 1.16), ('cert_o', 557, 0.57), ('null_org', 197, 0.2)]; shares sum 100.00

## cert_o assertions (D6.4)
- (a) cert_o rows whose name is in the cert defaults: 0 rows over 0 names; []
- (b) cert_o rows by my recomputation 557, by the stage 557; only mine 0, only stage 0, name_norm differs 0; examples []

## Open choices, measured
- RAT module (D6.1 pattern): raw rows 552; hosts rows 552; flagged is_noise 552
  modules (module, rows, noise rows): [('xiaongmai-backdoor', 183, 0), ('darktrack-rat', 152, 152), ('remcos-pro-rat', 145, 145), ('orcus-rat', 80, 80), ('nuclear-rat', 48, 48), ('njrat', 41, 41), ('poison-ivy-rat', 36, 36), ('njrat78', 2, 0), ('ghost-rat', 2, 2), ('nanocore-122-rat', 1, 1)]
  not-noise rows whose module name contains rat/c2/backdoor/trojan: [('xiaongmai-backdoor', 183), ('njrat78', 2)]
- cert O present, by identity_source (source, rows, org null, infrastructure): [('org', 831, 0, 0), ('infrastructure_unresolved', 667, 0, 667), ('cert_o', 557, 6, 551), ('noise', 12, 0, 8), ('null_org', 2, 2, 0)]
  org rows that also carry a cert O (kept as evidence only per D4): 831
- vuln_count == 50 in hosts: 755 (max 50); raw CVE count not in the narrow parquet
- raw cert dates outside 1990..2100 or unparseable (before dedupe): expires 23, issued 26 (of which 1970 epoch placeholders 24)
  hosts rows with cert_expires null but cert_expired (boolean) present: 23

RESULT: PASS
