# Extra checks of hosts, companies and signals, rerun after D12 (2026-10-11)

## check_hosts_extra.py

## Denylist on identity_source = 'org' rows (org and name_norm, shared rules)
- distinct (org, name_norm) pairs checked: 5,508; hits: 0

## Recomputation (author number vs mine)
- raw lines 100000; parsed rows 100,000; rows with host_ip 100,000; distinct keys 97,758; hosts rows 97,758; removed 2,242
- duplicate groups 1,098 covering 3,340 rows; groups with a single distinct timestamp (true copies) 0
- raw keys missing from hosts 0; hosts keys not in raw 0; kept row not the latest timestamp 0
- sum(dup_count - 1) = 2,242; raw rows with host_ip minus hosts rows = 2,242; dup_count differing from my per-key count: 0
- infrastructure before dedupe (my matcher run, raw rows with host_ip): 86,806 of 100,000 = 86.81%
- infrastructure after dedupe (parquet): 84,743 of 97,758 = 86.69%
- per-row disagreement between my flags (matcher + D4/D6 rules in Python) and the parquet over 97,758 rows: {'infra_reason': 0, 'is_noise': 0, 'identity_source': 0, 'name_norm': 0, 'cert_date_invalid': 0, 'missing': 0}; examples []
- is_noise rows 1,136; cert_date_invalid rows 46 (mine: 46)
- infra_reason mix (parquet): [('cloud_provider', 39572, 40.48), ('tag_rule', 21289, 21.78), ('org_exact', 20895, 21.37), ('(null)', 13015, 13.31), ('org_keyword', 2140, 2.19), ('org_prefix', 784, 0.8), ('org_pattern', 63, 0.06)]; shares sum 99.99
- identity_source mix (parquet): [('infrastructure_unresolved', 83110, 85.02), ('org', 12757, 13.05), ('noise', 1136, 1.16), ('cert_o', 558, 0.57), ('null_org', 197, 0.2)]; shares sum 100.00

## cert_o assertions (D6.4)
- (a) cert_o rows whose name is in the cert defaults: 0 rows over 0 names; []
- (b) cert_o rows by my recomputation 558, by the stage 558; only mine 0, only stage 0, name_norm differs 0; examples []

## Open choices, measured
- RAT module (D6.1 pattern): raw rows 552; hosts rows 552; flagged is_noise 552
  modules (module, rows, noise rows): [('xiaongmai-backdoor', 183, 0), ('darktrack-rat', 152, 152), ('remcos-pro-rat', 145, 145), ('orcus-rat', 80, 80), ('nuclear-rat', 48, 48), ('njrat', 41, 41), ('poison-ivy-rat', 36, 36), ('njrat78', 2, 0), ('ghost-rat', 2, 2), ('nanocore-122-rat', 1, 1)]
  not-noise rows whose module name contains rat/c2/backdoor/trojan: [('xiaongmai-backdoor', 183), ('njrat78', 2)]
- cert O present, by identity_source (source, rows, org null, infrastructure): [('org', 815, 0, 0), ('infrastructure_unresolved', 682, 0, 682), ('cert_o', 558, 6, 552), ('noise', 12, 0, 8), ('null_org', 2, 2, 0)]
  org rows that also carry a cert O (kept as evidence only per D4): 815
- vuln_count == 50 in hosts: 755 (max 50); raw rows with >= 50 CVEs 761 (before dedupe)
- raw cert dates outside 1990..2100 or unparseable (before dedupe): expires 23, issued 26 (of which 1970 epoch placeholders 24)
  hosts rows with cert_expires null but cert_expired (boolean) present: 23

RESULT: PASS

## check_companies_extra.py

**PASS**: 5/5 extra checks passed

| result | check | evidence |
|---|---|---|
| PASS | reconciliation hosts = never-create + member; member rows group into companies | hosts 97,758 = never-create 84,443 + member 13,315; sum(host_count) 13,315; companies 5,790 vs distinct member name_norm 5,790; unexpected identity_source {} |
| PASS | independent recompute of every company column from hosts: 0 disagreements | 5,790 reference companies vs 5,790 rows; missing 0, extra 0, duplicate name_norm 0; column disagreements {}; examples [] [] [] |
| PASS | company_id equals hashlib sha256(name_norm)[:16] on every row | 0 mismatches; e.g. [] |
| PASS | denylist leakage in company_name and name_norm (shared rules, org text) | 0 hits over 5,790 companies; none |
| PASS | resolved share 5.0% to 20.0% | resolved 13,315 of 97,758 = 13.62%; headline unresolved 86.38% |

## Recomputed numbers (mine)
- companies: 5,790
- member rows: 13,315
- singletons: 4,169
- host_count 2: 687
- host_count 3-5: 568
- host_count 6-20: 337
- host_count 21-100: 22
- host_count over 100: 7
- median: 1
- p90: 4
- p99: 16
- max: 330
- confidence high: 5,387
- confidence low: 403
- named under both sources: 18
- cert_o-only singletons: 347
- companies with noise: 24
- noise rows attributed: 33
- companies noise share >= 0.5: 4
- noise-only names: 94
- noise-only rows: 1,103
- raw org spellings: 5,508
- raw cert O spellings: 429
- distinct host_ip all: 84,648
- distinct host_ip members: 12,338

## Raw spellings: top 20 companies by distinct spellings
- zoho (5 spellings, 95 hosts): ['ZOHO', 'ZOHO Corp', 'ZOHO Corporation Private Limited', 'Zoho Corp', 'Zoho Corporation']
- true internet (4 spellings, 21 hosts): ['True Internet Co., Ltd.', 'True Internet Co.Ltd.', 'True Internet Corporation Co. Ltd.', 'True internet Co., Ltd.']
- blackline systems (3 spellings, 16 hosts): ['BLACKLINE SYSTEMS, INC.', 'BlackLine Systems, Inc.', 'Blackline Systems, Inc.']
- xtom (3 spellings, 16 hosts): ['xTom', 'xTom GmbH', 'xTom Pty Ltd']
- bharti airtel (3 spellings, 15 hosts): ['BHARTI Airtel Ltd.', 'BHARTI-AIRTEL', 'Bharti Airtel Limited']
- tim s a (3 spellings, 14 hosts): ['TIM S A', 'TIM S.A.', 'TIM S/A']
- softbank (3 spellings, 13 hosts): ['SOFTBANK CorP.', 'SOFTBANK Corp.', 'SoftBank Corp.']
- radware (3 spellings, 10 hosts): ['RADWARE INC.', 'Radware Limited', 'Radware Ltd']
- zen internet (3 spellings, 9 hosts): ['Zen Internet', 'Zen Internet Limited', 'Zen Internet Ltd']
- pt first media tbk (3 spellings, 5 hosts): ['PT. First Media, Tbk', 'PT. First Media, Tbk.', 'PT. First Media,Tbk']
- salesforce com (2 spellings, 181 hosts): ['SalesForce.com, Inc.', 'Salesforce.com, Inc.']
- servicenow (2 spellings, 155 hosts): ['SERVICENOW, INC.', 'ServiceNow, Inc.']
- tpg internet (2 spellings, 19 hosts): ['TPG Internet Pty Ltd', 'TPG Internet Pty Ltd.']
- arteria networks (2 spellings, 18 hosts): ['ARTERIA Networks Corp.', 'ARTERIA Networks Corporation']
- brander group (2 spellings, 17 hosts): ['Brander Group Inc', 'Brander Group Inc.']
- ewe tel (2 spellings, 16 hosts): ['EWE TEL GmbH', 'EWE-TEL']
- mittwald cm service gmbh und co kg (2 spellings, 16 hosts): ['Mittwald CM Service GmbH und Co. KG', 'Mittwald CM Service GmbH und Co.KG']
- spark new zealand trading (2 spellings, 16 hosts): ['SPARK NEW ZEALAND TRADING LIMITED', 'Spark New Zealand Trading Ltd']
- digital core technology (2 spellings, 15 hosts): ['Digital Core Technology Co., Limited', 'Digital Core Technology Co., Ltd']
- telia network services (2 spellings, 15 hosts): ['Telia Network Services', 'Telia Network services']

## check_signals_extra.py

**PASS**: 10/10 extra checks passed

| result | check | evidence |
|---|---|---|
| PASS | signals rows == companies rows, company_id unique, id sets equal both ways | signals 5,790, companies 5,790, duplicate ids 0, only in signals 0, only in companies 0 |
| PASS | independent recompute of all 26 signal columns from hosts + companies: 0 disagreements | 5,790 companies; missing 0, extra 0, duplicate 0; column disagreements {}; examples [] |
| PASS | regexes recomputed in Python: operator_shape_t1, operator_shape_t2 and the union | disagreements {'operator_shape_t1': 0, 'operator_shape_t2': 0, 'operator_name_shape': 0} |
| PASS | max_cvss_band edges (null=0, below 7.0=1, 7.0 to 8.9=2, 9.0 up=3) recomputed | band disagreements 0, max_cvss disagreements 0 |
| PASS | the 10 carried columns equal companies on every row | column differences none |
| PASS | join recount from hosts equals host_count and distinct_host_ips on every row | 0 rows differ; e.g. [] |
| PASS | host_signals_blind companies = exactly the companies whose every member host is cdn-tagged (all of them cert_o only) | stage blind 180, mine 180, only stage 0, only mine 0, blind but not cert_o 0 |
| PASS | denylist leakage in company_name and name_norm (shared rules, org text) | 0 hits over 5,790 companies; none |
| PASS | no boolean signal is constant | constant: none |
| PASS | company-level coverage recomputed equals the D9.4 sample table (mine, D9) | 27 figures compared; differences none |

## Warnings
- phi pair |phi|>=0.8: operator_shape_t1 with operator_name_shape = 0.896 (needs an explanation in the report)
- phi pair |phi|>=0.8: max_cvss >= 7 with max_cvss_band = 3 = 0.813 (needs an explanation in the report)

## Recomputed coverage (mine)
- host_signals_blind: 180
- is_singleton: 4,169
- in_territory: 1,346
- named_registrant: 5,387
- sensitive_stack: 55
- operator_shape_t1: 1,046
- operator_shape_t2: 309
- operator_name_shape: 1,248
- kev_exposed: 462
- cert_expired_or_soon: 373
- eol_stack: 352
- legacy_tls: 209
- risky_service_exposed: 226
- risky_non_ssh_exposed: 68
- exposed_and_outdated: 48
- max_cvss_band = 1: 70
- max_cvss_band = 2: 209
- max_cvss_band = 3: 460
- footprint_band = 0: 4,230
- footprint_band = 1: 1,215
- footprint_band = 2: 318
- footprint_band = 3: 27
- any CVSS: 739
- T2 only: 202
- risky_service_exposed SSH only: 158
- any urgency signal: 1,294
- strong urgency: 662

## Recomputed reconciliation (mine)
- member host rows: 13,315
- counted member rows: 13,067
- non-counted member rows (cdn-tagged cert_o): 248
- companies with at least one non-counted host: 192
- member rows meeting the cert condition via the boolean: 286
- member rows meeting it only via the 30-day window: 150
- member rows with max_cvss exactly 0.0 (band 1, not band 0; edge): 0
- member rows with cert_expires == timestamp + 30 days exactly (counted, upper edge inclusive): 0
- member rows with cert_expires == timestamp (not counted, lower edge exclusive): 0
