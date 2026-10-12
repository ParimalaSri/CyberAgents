# Hosts layer review (2026-10-11), data-quality-engineer

Verdict: FAIL (1 of 84 contract checks fails: denylist leakage in name_norm, 3 rows, see DQ-001). Contract: context/contracts/hosts.yml.
Generic report: outputs/dq/hosts_2026-10-11.md. Data: spread sample (100,000 raw rows), NOT the full file. Names-only review by a single reviewer.

## Output of check_hosts_extra.py (recomputation and open-choice counts)
## Denylist on identity_source = 'org' rows (org and name_norm, shared rules)
- distinct (org, name_norm) pairs checked: 5,638; hits: 0

## Recomputation (author number vs mine)
- raw lines 100,000; parsed rows 100,000; rows with host_ip 100,000; distinct keys 97,758; hosts rows 97,758; removed 2,242
- duplicate groups 1,098 covering 3,340 rows; groups with a single distinct timestamp (true copies) 0
- raw keys missing from hosts 0; hosts keys not in raw 0; kept row not the latest timestamp 0
- infrastructure before dedupe (my matcher run, raw rows with host_ip): 85,798 of 100,000 = 85.80%
- infrastructure after dedupe (parquet): 83,740 of 97,758 = 85.66%
- per-row disagreement between my flags (matcher + D4 rules applied in Python) and the parquet: {'infra_reason': 0, 'is_noise': 0, 'identity_source': 0, 'missing': 0}; examples []
- infra_reason mix (parquet): [('cloud_provider', 39572, 40.48), ('tag_rule', 21289, 21.78), ('org_exact', 20895, 21.37), ('(null)', 14018, 14.34), ('org_keyword', 1799, 1.84), ('org_prefix', 122, 0.12), ('org_pattern', 63, 0.06)]; shares sum 99.99
- identity_source mix (parquet): [('infrastructure_unresolved', 82074, 83.96), ('org', 13755, 14.07), ('noise', 1089, 1.11), ('cert_o', 644, 0.66), ('null_org', 196, 0.2)]; shares sum 100.00

## Open choices, measured
- RAT module (ends 'rat'): raw rows 505; hosts rows 505; flagged is_noise 505
  modules (module, rows, noise rows): [('xiaongmai-backdoor', 183, 0), ('darktrack-rat', 152, 152), ('remcos-pro-rat', 145, 145), ('orcus-rat', 80, 80), ('nuclear-rat', 48, 48), ('njrat', 41, 41), ('poison-ivy-rat', 36, 36), ('njrat78', 2, 0), ('ghost-rat', 2, 2), ('nanocore-122-rat', 1, 1)]
  not-noise rows whose module name contains rat/c2/backdoor/trojan: [('xiaongmai-backdoor', 183), ('njrat78', 2)]
- cert O present, by identity_source (source, rows, org null, infrastructure): [('org', 875, 0, 0), ('cert_o', 644, 7, 637), ('infrastructure_unresolved', 537, 0, 537), ('noise', 12, 0, 8), ('null_org', 1, 1, 0)]
  org rows that also carry a cert O (kept as evidence only per D4): 875
- vuln_count == 50 in hosts: 755 (max 50); raw rows with >= 50 CVEs 761 (before dedupe)
- raw cert dates outside 1990..2100 or unparseable (before dedupe): expires 23, issued 26 (of which 1970 epoch placeholders 24)
  hosts rows with cert_expires null but cert_expired (boolean) present: 23
- dedupe: groups whose copies carry different hostnames arrays 976, extra distinct arrays dropped 2105


## Judgement checks
- 10 random rows (seeded): Aliyun, Incapsula (cdn tag), Huawei Public Cloud, Hetzner, Amazon Technologies (cloud_provider), China Mobile, GoDaddy are infrastructure_unresolved
  with a plausible infra_reason; Cogent Communications - IPENG and Wal-Mart Stores are identity_source org. Cogent is an ISP that survived (DQ-002).
- Top 10 non-infrastructure, non-noise orgs: Egnyte 330, Fiserv Solutions 328, Wal-Mart 248, Avago 236, (null org) 203, Salesforce 176, TGS Management 148, Netflix Streaming 141,
  Los Angeles Municipal Court 86, ServiceNow 85. All real organisations (consistent with D5).
- Rows per identity_source: infrastructure_unresolved 82,074 (83.96%), org 13,755 (14.07%), noise 1,089 (1.11%), cert_o 644 (0.66%), null_org 196 (0.20%); sum 100.00%.
- Null rates (% of 97,758): org 0.21, isp/asn 8.90, product 80.99, version 93.67, os 97.50, cpe 76.79, tags 34.41, cloud_provider 59.52, cert_expires/issued 90.90, cert_subject_o 97.88,
  max_cvss 96.94, infra_reason 14.34, name_norm 85.27, host_ip/port/transport/flags 0. These agree with the raw profile (outputs/profile_spread_100k.md section 3) within dedupe effects.
  The author's own null table was not in my brief, so I compared against the profile, not against the author's printout.
- Leakage (org rows, top 50 by rows): see DQ-002; ISP / hosting looking names, 20 orgs, 537 rows.
- False exclusions (infrastructure only through cloud_provider or cdn/cloud tag while the org is not on the denylist; 26 distinct orgs, 94 rows): HubSpot, Inc. 14, Trans Union, LLC 2,
  Capitec Bank 1, Netflix Inc 1, Bigcommerce 1, Armis 2, Render 3. These follow D4 rule 2 / D5 as written (tag and cloud.provider rules stay), so they are not contract violations. The big D5 names
  (Egnyte, Fiserv, Wal-Mart, Avago, TGS) are correctly NOT excluded (0 rows with a cloud or cdn reason for Egnyte, Fiserv, Wal-Mart, Salesforce, ServiceNow, Netflix Streaming).
- cert_o: 637 of 644 rows are infrastructure, 7 have a null org; implementation matches the stated rule (infrastructure OR null org) and usable cert O. Some cert O values are device vendors or cloud
  brands (DQ-001).
