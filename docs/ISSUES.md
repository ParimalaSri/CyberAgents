# Issues log

Format: symptom, root cause (labelled hypothesis where unconfirmed), fix idea, contract rule that should catch it.
Entries below were raised by data-integrator from profiling `data/raw/sample_100k.jsonl`. Owner of status: data-quality-engineer.

## RAW-001 Most rows belong to infrastructure owners, not companies
- Symptom: Google LLC is the org on 33,149 rows (33.1%), Incapsula Inc on 17,906 (17.9%); top 10 orgs cover 68.5% of rows.
  86.8% of rows have an org on the denylist candidates; only 9.5% have no org, isp or cloud.provider on the list.
- Root cause (hypothesis): `org` is the registered owner of the IP block; tenants of cloud/CDN ranges are not visible in it.
- Fix idea: denylist plus `cloud`/`cdn` tag filter before company grouping; look for tenant identity in cert subject O/CN
  and non-provider hostnames.
- Contract rule: no companies row whose normalised name is on the denylist (denylist leakage check).

## RAW-002 Same owner spelled many ways
- Symptom: Incapsula Inc / Inc. / Network; Aliyun Computing Co., LTD / Co.LTD; at least 12 `Amazon Data Services <region>`;
  Scaleway and OVH have 6+ spellings each. 5,535 raw org values, 5,462 after lowercase and trim.
- Root cause (hypothesis): org text comes from regional internet registries, entered by each network operator.
- Fix idea: normalise (case, punctuation, legal suffix) then rule-based prefix families for denylist; precision over recall.
- Contract rule: company names are unique after normalisation.

## RAW-003 IPv6 rows have no ip_str
- Symptom: 587 rows (0.59%) have ip and ip_str null; address is in `ipv6`.
- Root cause (hypothesis): collector stores IPv6 in a separate field.
- Fix idea: `host_ip = coalesce(ip_str, ipv6)` in stage 1.
- Contract rule: host_ip not null.

## RAW-004 Repeated ip:port:transport rows
- Symptom: 4,109 IPv4 rows (4.1%) repeat an ip:port:transport already present.
- Root cause (hypothesis): several banners for one endpoint (different hostnames/SNI or module, or re-crawl). Not verified.
- Fix idea: inspect examples, then dedupe on (host_ip, port, transport) keeping the latest timestamp.
- Contract rule: hosts key unique after stage 1.

## RAW-005 Timestamp has no spread
- Symptom: all 100,000 rows fall in 2026-09-14 09:54:28 to 10:06:32 (about 12 minutes).
- Root cause (hypothesis): sample is the first 100K lines of a crawl-ordered dump; full dump may cover a longer range.
- Fix idea: check the timestamp range of the full file before designing any recency signal.
- Contract rule: none yet; add a range check once the full-file range is known.

## RAW-006 Vulnerability lists look inferred, not verified
- Symptom: 877 rows carry an identical long list of old CVEs on Apache httpd banners; `verified=true` on 28 of 148,562 CVE
  entries; EPSS median of row max 0.99957 (saturated); rows with vulns average 46 CVEs, max 778.
- Root cause (hypothesis): CVEs are matched from the banner version string, so any backported package shows all CVEs.
- Fix idea: weight by KEV, CVSS and presence, not by CVE count; cap counts.
- Contract rule: vuln_count capped, score uses max CVSS and KEV.

## RAW-007 Certificate date sentinels and text dates
- Symptom: `ssl.cert.expires` is text `YYYYMMDDHHMMSSZ`; 1 value `0001...`, 2 values `4096...`; 1 issued `0001...`.
- Root cause (hypothesis): malformed or placeholder certificates.
- Fix idea: parse with try_strptime, null out years below 1990 or above 2100.
- Contract rule: cert_expires between 1990 and 2100 or null.

## RAW-008 Noise and non-customer traffic in the sample
- Symptom: tag `honeypot` on 679 rows, RAT/C2 collector modules on 739 rows, `compromised` 1, `c2` 1, `tor` 1;
  port 12304 holds 10.6% of rows (7,154 for Google LLC) under module `auto`.
- Root cause (hypothesis): honeypots and attacker infrastructure are indexed alongside real hosts; port 12304 is a cloud/proxy range artefact.
- Fix idea: exclusion flags in stage 1; look at port 12304 and other `auto` high ports before using port as a signal.
- Contract rule: rows tagged honeypot/c2/tor are excluded from companies.

## RAW-009 profile_table.py cannot read this file with defaults
- Symptom (not verified by running): the skill script calls `read_json_auto(path)` with no options; this file needs
  `sample_size`, `maximum_object_size=33554432` and `ignore_errors=true`.
- Root cause (hypothesis): script written for csv/parquet-sized rows. Also a hook blocked running it against `data/raw/`
  from the shell, so the check was not run.
- Fix idea: add json options to the script (owner: whoever maintains the skill).
- Contract rule: none.

## RAW-010 DQ denylist check only understands the exact list
- Status: CLOSED on branch `feat/data-quality/contract-matcher` (2026-10-11).
- Symptom: `.claude/skills/data-quality-check/scripts/check_contract.py` `check_denylist` read one list from the contract and compared
  `lower(trim(name))`; it had no word-boundary prefix rule, no pattern rule (CIDR/glob), no keyword rule and no accent or punctuation normaliser.
  Measured on the 6,579 distinct non-null orgs of `data/sample/spread_100k.jsonl`: the old logic flagged 205; the shared rules flag 897.
- Root cause: the check was written for a single exact list and re-implemented matching instead of using the pipeline's matcher, so the checker and
  the pipeline could disagree.
- Fix: `check_denylist` now imports `scripts/denylist_match.py` (path derived from the script location, works from any directory). New contract
  form `denylist: {column, rules: shared}` applies exact, prefix, pattern and keyword rules on the org text only (D5) and reports up to 5 examples with
  the rule type; the old `{column, file}` form still works but normalises both sides with `normalise()` (205 to 241 on the same orgs). A missing matcher or rule file
  FAILS with a message. Also added: `infra_reason` value check (must be in `INFRA_REASONS`, `isp_*` fails) and a generic `shares` check (D4 share rules).
  20 tests in `test_check_contract.py`; report `outputs/dq/checker_upgrade_2026-10-11.md`.
- Contract rule now catching it: `denylist: {column: company_name, rules: shared}` in the companies contract (any value matching any of the four
  rule types fails); `infra_reason: {}` on hosts. Not yet wired into `context/contracts/*.yml` because no layer contract exists yet.
- Residual: the keyword rules are applied as the pipeline applies them; some matched orgs look like real ISPs/hosts by name only (see report), that is the
  gate decision in RAW-013, not a checker bug.

## RAW-011 Raw column set differs between samples
- Symptom: head sample has 78 top-level columns, spread sample 85. 14 columns only in the spread sample (microsoft_exchange, openflow,
  checkpoint, device, netbios, vendor, radius, qnap, rsync, afp, airplay, ipmi, ethereum_p2p, neo4j_browser, 1 to 20 rows each); 7 only in
  the head sample (oracle_tnslsnr, philips_hue, ipp_cups, spotify_connect, ldap, fast_reverse_proxy, ntrip).
- Root cause: read_json_auto infers the schema from the rows it samples; rare protocol structs appear in some rows only.
- Fix idea: `1_clean` selects named columns with an explicit schema; do not rely on inference. Full-file column set is unknown.
- Contract rule: hosts contract lists columns explicitly; unknown raw columns are ignored, not errors.

## RAW-012 org field sometimes holds an address or a hostname pattern
- Symptom: org = `139.162.0.0/16` on 62 spread rows (Linode / Akamai Connected Cloud space, reverse names `*.ip.linodeusercontent.com`);
  63 rows have org or isp containing `se5-ptk` or `se3-ptk`.
- Root cause (hypothesis): registry records without a proper organisation name.
- Fix: those entries moved from `denylist.txt` to `context/denylist_patterns.txt` (CIDR matched on host IP and org text; globs on org/isp).
- Contract rule: company names must not parse as an IP/CIDR (add to companies contract).

## RAW-013 List-based denylist still leaks ISPs and hosting on the long tail
- Status: PARTLY FIXED on branch `feat/data-integrator/isp-keywords` (proposed, owner approval pending). Keyword gate run on 2026-10-11.
- Symptom: after exact + prefix + pattern + D4 tag rules, 12,368 rows survive (12.37%; the profile printed 12,336); a keyword scan of org text
  (telecom, telekom, telefon, broadband, internet service, chinanet, communications, mobile, cable, vpn, hosting, weebly, cloud, server)
  matched 2,778 of them. Examples: Internet Service Provider 65, Weebly 49, Mullvad VPN 35, Bretagne Telecom 29,
  CHINANET jiangsu province network 27, EGIHosting 20, WHG Hosting Services 20.
- Root cause: ISP/hosting names outside the hand-picked list; `cloud.provider` and `cloud`/`cdn` tags add only 6 rows beyond the lists.
- Fix applied (proposed): `context/denylist_keywords.txt` with 11 whole-word keywords that passed a hand-review gate (>= 90% INFRA of up to 50 orgs):
  chinanet, hosting, vpn, internet service provider, broadband, web hosting, vps, telecommunications, cable, fibre, dedicated. `weebly` and `jimdo` added
  to the prefix list (D2). Effect on the spread sample: infrastructure 87.63% to 88.80%, surviving 12.37% to 11.20%, surviving distinct orgs 5,519 to 5,113,
  1,170 rows newly excluded. Details: `outputs/denylist_keyword_review.md`.
- Update 2026-10-11, branch `feat/data-integrator/org-only-keywords` (proposed): field-scoped keywords added (`org: phrase` = org text only; unscoped
  unchanged; unknown scope rejected; 28 test cases pass). Org-only gate passed for telecom 49/50, telekom 32/35, telecommunication 20/20, telefonica 20/21,
  telephone 20/20, telecomunicacoes 25/27, telecoms 3/3, telkom 5/5, telcom 4/4, accented telefônica 1/1 and telefónica 3/3; failed: telecomunicaciones 13/19,
  telecomunicações 13/15, telecomunicazioni 2/5, telekommunikation 5/6, telekomunikasi 2/3, telco 0/1. Effect (spread sample): infrastructure 88.80% to
  89.45% (88,802 to 89,446 rows), surviving 11,198 to 10,554, surviving distinct orgs 5,112 to 4,838. The 32-row gap (profile 12,336 vs 12,368) is the 32
  survivors with null `ip_str` (IPv6) dropped by NULL logic in the profile query (strongly supported, not proven). Details: `outputs/denylist_orgonly_review.md`.
  Still open: one-word compound brands (rostelecom, kazakhtelecom) not matched.
- Update 2026-10-11, branch `feat/data-integrator/accent-folding` (proposed): `normalise()` now folds Latin accents (NFKD, marks dropped only on Latin bases;
  CJK, Cyrillic and Arabic untouched, 0 empty results on the sample); all loaders and `matches_pattern()` use the same folded form; 59 test cases pass.
  Accented keyword entries removed (merged into telefonica). Re-gate after merging: telefonica 23/24 (95.8%) ENABLED, telecom 47/50 ENABLED, telecomunicacoes merged
  36/42 (85.7%) FAILED and DISABLED (it was enabled at 25/27); all other keyword row sets unchanged (telekom 91.4%, chinanet 90.0% stay). Spread sample: infrastructure
  89,446 to 89,398 rows (89.40%), surviving 10,554 to 10,602 (10.60%), surviving distinct orgs 4,838 to 4,863; folding alone moves 24 rows to infrastructure.
  Details: `outputs/denylist_accent_folding.md`. Still true: `check_contract.py` applies none of the prefix, pattern, keyword or normalisation rules (RAW-010); the
  data-quality-engineer must import `scripts/denylist_match.py`. Quirk: "S.A." normalises to "s a" and is not dropped as a legal suffix.
- Update 2026-10-11, branch `feat/data-integrator/denylist-cleanup` (proposed): (1) `automattic` and `tumblr` added as prefixes (D2; 27 rows). (2) Owner removed
  the generic keywords `telephone`, `cable`, `dedicated` (`fibre` kept; 162 rows return to surviving). (3) ISP-field decision by measurement: 3,516 rows
  (798 distinct non-null orgs, plus 50 null-org rows) were excluded ONLY through isp text (3,331 exact, 120 keyword, 15 prefix, 0 pattern, non-null org rows);
  hand review of 50 orgs found 22 INFRA (44%), gate 90% FAILED. Decision: isp text no longer excludes by itself; `cloud.provider`, `cloud`/`cdn` tags and the IP
  CIDR rule are unchanged. `infrastructure_reason(row, rules, isp_matching="ignore")` in `scripts/denylist_match.py` ("exclude" reproduces the old behaviour;
  85 tests pass). Spread sample: infrastructure 89,398 to 85,747 (89.40% to 85.75%), surviving 10,602 to 14,253, surviving distinct orgs 4,863 to 5,664.
  The D4 wording in ARCHITECTURE.md must change from "org, isp or cloud.provider" to org text only (owner/senior-data-engineer). Details:
  `outputs/denylist_cleanup_review.md`. Item (3) below (Automattic / Tumblr) is done.
- Update 2026-10-11, branch `feat/data-integrator/d5-wording` (proposed; D5 follow-up decided by senior-data-engineer): (1) wording that still said the isp text is
  matched was fixed in the denylist files, `context/schema.md` and `scripts/denylist_match.py` (no behaviour change); `isp_matching="exclude"` is documented as
  reproducing old counts only. (2) `org: ovh` keyword enabled: gate 6/6 (only 6 distinct orgs newly matched; whole word, so OVHTECH is not matched). (3) `webflow`
  added as a D2 prefix family (10 rows, 1 IP). (4) `INFRA_REASONS` pinned by a test: cloud_provider, tag_rule, ip_pattern, org_exact, org_prefix, org_pattern,
  org_keyword; `2_companies` is not built yet and must follow it. Spread sample: infrastructure 85,747 to 85,798 (85.80%), surviving 14,253 to 14,202 (14.20%),
  surviving distinct orgs 5,664 to 5,657; 106 tests pass. Details: `outputs/denylist_cleanup_review.md` section 7.
- Update 2026-10-11, branch `feat/data-integrator/d6-denylist` (proposed; D6.4 and D6.7 decided by senior-data-engineer): (1) device-vendor, carrier and name-guard entries plus `dis` (10 rows of
  self-signed mail-server template certs) added to `context/cert_default_names.txt`. (2) Gates on the spread sample: org prefixes facebook / meta platforms / netflix FAILED 0/4 by name
  (not added; the 176 rows look like cache and edge nodes of the organisation itself, evidence outside the gate), `org: unicom` 46/47, `org: province network` 38/38, compound `org: *hosting` 30/30,
  13 named operator or hosting prefixes (racknerd, ntt america, ionos, telstra, vodafone, fastweb, uninet, cliente antel, administracion nacional de telecomunicaciones, web com, psinet, comcast, cloudfly) 39/40.
  (3) New matcher syntax: a leading `*` on a one-word keyword matches one token that ends with the word (webhosting, EGIHosting); not a substring match; `ghosting` excluded. (4) Spread sample:
  infrastructure 85,798 to 86,583 (86.58%), surviving 14,202 to 13,417, surviving distinct orgs 5,657 to 5,539; top-50 surviving orgs that read as ISP, hosting or telecom by name 20 (538 rows) to 9 (171 rows);
  207 tests pass. Residual stays: the operator long tail (True Internet, Taiwan Fixed Network, Orange, Rogers, IDC Frontier, Leaseweb) is above the D6.7 10% reopen threshold if it holds on the full run.
  Details: `outputs/denylist_cleanup_review.md` section 8.
- What remains: (1) 18 candidates failed the gate in the first round and are not applied, including communications (78.0%), isp, idc, fiber,
  mobile, cloud, internet, network (telecom and telekom are now handled org-only, see the update above); an org-only scope for the others might pass
  but needs its own review (owner decision). (2) Classification was from org names only, by one reviewer. (3) Automattic / Tumblr added (see the denylist-cleanup update). (4) The checker now enforces the shared rules (RAW-010 closed); `2_companies` is not built yet. (5) Not yet run on the full file.
- Contract rule: companies row share outside 5-20% flagged (already planned); keyword-leakage check once `check_contract.py` calls `matches_keyword`.
- Update 2026-10-11, D7 step 1 (branch `feat/data-integrator/d7-prefixes`, proposed; decided by senior-data-engineer): `netflix`, `meta platforms`, `facebook` added as D2/D7.1 cache-operator
  prefixes (gate (a) in `outputs/denylist_cleanup_review.md` 8.2 superseded by D7.1; hostname evidence Netflix 143/143 on nflxvideo.net, Meta and Facebook 27/27 on facebook.com or fbcdn.net;
  Apple Inc. not excluded). Matcher on `data/silver/hosts.parquet` (97,758 rows): 173 rows change status, infrastructure 84,523 to 84,696 (86.46% to 86.64%). Not added: True Internet, Taiwan Fixed
  Network, Leaseweb and the other residual names (accepted long tail, D7.2). 212 tests pass.
- Update 2026-10-11, D8.2 (branch `feat/data-integrator/d8-huawei`, proposed; decided by senior-data-engineer): `huawei` added as an org prefix (family completion; no other names added).
  Gate on `data/silver/hosts.parquet` (97,758 rows): 8 distinct names newly matched, 47 surviving rows, all Huawei group entities by name (HUAWEI INTERNATIONAL PTE. LTD. 34, Huawei Clouds Chile 5, others 8).
  `Owner: HUAWEI DO BRASIL ...` (4 rows) is not matched (normalised name starts with `owner`). Not added: TIM S/A, Host-Unlimited, True Internet, Taiwan Fixed Network. Details: `outputs/denylist_cleanup_review.md` section 9.
  Expected after the stage rerun: org 12,757, infrastructure_unresolved 83,111, resolved share (org plus cert_o) 13.62%. 217 matcher cases and 16 stage tests pass.

## RAW-014 Expectations in D3/section 10 not reproduced on the spread sample
- Symptom: port 12304 is 0.22% (expected about 2%); infrastructure share 87.63% (expected about 86%); surviving 12.34% (expected about 10%).
  Timestamp range 09:54:53 to 11:05:46 (about 71 min), the architecture doc says about 61 min.
- Root cause (hypothesis): the 21-window probe (9,239 rows) was a small, clustered sample; the port-sweep burst is in only 53 of 1,000 blocks.
- Fix idea: update ARCHITECTURE.md section 10/15 expectations (owner or senior-data-engineer). Full-file run will give the true values.
- Contract rule: none; resolved-share range check stays 5% to 20%.

## PIPE-001 Certificate date sentinels are more common than RAW-007 recorded
- Symptom: on the spread sample (100,000 rows) 23 `ssl.cert.expires` values and 26 `ssl.cert.issued` values fall outside 1990..2100 or do not parse. Expiry examples:
  `40960101000000Z` (2), `99991231235959Z` (2), `30200822072305Z`, `77641212080202Z`, a dozen 2117 to 2297, and `19710101000129Z`, `19030107085804Z`. Issued:
  almost all `1970010100000x` (epoch placeholders), plus `19750101000000Z`. RAW-007 listed only 3 expiry and 1 issued sentinels (head sample).
- Root cause (hypothesis): devices with no clock write epoch or far-future placeholder dates.
- Fix applied in `pipeline/1_clean.py`: `cert_expires` and `cert_issued` are nulled outside 1990..2100 (the spec rule); the count is printed in the stage report.
  `cert_expired` (the raw boolean) is kept as delivered, so it can disagree with a nulled date. Decision open for the owner: whether a 1970 issue date should count as a
  "self-signed device without clock" signal instead of being thrown away.
- Contract rule: `cert_expires` and `cert_issued` between 1990 and 2100 or null (the hosts contract has the range for cert_expires; add cert_issued).

## PIPE-002 Dedupe on (host_ip, port, transport) discards alternative hostnames
- Symptom: 1,098 duplicate groups (3,340 rows, 2,242 removed) in the spread sample. Every group has distinct timestamps; 976 of 1,098 groups have different `hostnames`
  arrays across the copies; 8 groups differ in `_shodan.module`.
- Root cause (hypothesis, supported by the counts): the same endpoint is banner-scanned again with another hostname or SNI, so the copies are not exact duplicates.
- Effect: keeping only the latest row loses hostnames and domains seen on the earlier copies (evidence for stage 2 only; no flag or score depends on it today).
- Fix idea: if domain evidence turns out to matter (D4 rule 3b), aggregate hostnames across duplicates before dedupe. Not done: the spec says keep latest.
- Contract rule: key unique after stage 1 (already in the plan).

## PIPE-003 executemany fails on an empty parameter list
- Symptom: first run of `1_clean.py` stopped with `executemany requires a non-empty list of parameter sets` when no IPv6 value matched a CIDR pattern.
- Root cause: DuckDB rejects an empty list; the sample has no IPv6 CIDR hit.
- Fix: helper `insert_rows` skips empty lists. Test coverage: the synthetic tests run with no IPv6 hits.
- Contract rule: none (a crash, not a data defect).

## DQ-001 Denylist keyword names become company names through the cert O route
- Symptom: contract check "denylist leakage in 'name_norm' (shared rules)" fails on the hosts layer: 3 rows match, all `identity_source = 'cert_o'`:
  'bouygues telecom' (keyword: telecom), 'viettel telecom corporation branch of viettel group' (keyword: telecom), 'hrvatski telekom d d' (keyword: telekom).
  The same route also yields infrastructure or device-vendor names as `name_norm` (top cert_o values: 24 rows of a China Telecom Cloud cert O,
  Huawei 11 and Huawei Software Technologies 8, Sierra Wireless 13, a cert O of just 'Dis' 7, Comcast Corporation 5).
  The check on `identity_source = 'org'` rows (org and name_norm, 5,638 distinct pairs) finds 0 hits.
- Root cause (read from `pipeline/1_clean.py` lines 108 to 112, supported by the rows): a cert O is rejected as a vendor only when it hits an exact, prefix or
  pattern rule; keyword hits are deliberately let through (`vendor = bool(hit) and hit[0] != "keyword"`), and the keywords were gated on org text, not cert text.
  Whether a telecom as a cert tenant should count is a design question (hypothesis: the stage author wanted tenants kept); the contract says no ISP names as companies.
- Fix: owner / senior-data-engineer decision; either apply keyword rules to cert O, or accept and document an exception. Not applied by DQ.
- Contract rule: `denylist: {column: name_norm, rules: shared}` in `context/contracts/hosts.yml` (fails today); `check_hosts_extra.py` repeats it on org rows only (passes).
- Status: FIXED (re-validated 2026-10-11 on `pipeline/1_clean.py` at e4c3867, spread sample, 97,758 rows; owner of the check: data-quality-engineer). D6.4: `vendor = bool(hit)` (every rule type including keywords) plus the vendor and
  name-guard entries in `context/cert_default_names.txt`. Measured: 0 of 428 distinct cert_o names (557 rows) hit any shared rule or a cert default; the three named telecom names and Huawei, Sierra Wireless, Comcast, `dis`,
  Meta Platforms, Facebook, Apple and Netflix each have 0 cert_o rows; cert_o rows 644 to 557. The independent recompute of cert-O usability agrees with the stage on all 557 rows (0 only-mine, 0 only-stage, 0 name differences).
- Contract rules now catching it: `denylist: {column: name_norm, rules: shared}` (whole column, 0 hits, unchanged); `check_hosts_extra.py` assertion (a) no cert_o `name_norm` or cert O is in `cert_default_names.txt`
  and assertion (b) independent cert-O usability recompute equals the stage (both tested in `test_check_contract.py::CertOAssertionTests`). Completeness of the cert list is NOT caught, see PIPE-004.

## DQ-002 ISP and hosting orgs survive as identity_source = 'org' (long tail, residual of RAW-013)
- Symptom: among the 50 largest orgs with `identity_source = 'org'`, 20 orgs (537 rows) look like ISP, telecom or hosting by name (names only, one reviewer, crude keyword scan):
  China Unicom Henan province network 51, Uninet S.A. de C.V. 37, Administracion Nacional de Telecomunicaciones 36, CLIENTE ANTEL URUGUAY 33, Web.com Group 29,
  RackNerd LLC 28, PSINet 27, NTT America 26, IONOS Inc. 26, Vodafone Net Iletisim Hizmetler AS 25, Comcast IP Services 24, Fastweb SpA 23, Cloud Innovation Ltd 23,
  CloudFly Net Inc 23, China Unicom Shandong province network 22, Taiwan Fixed Network 21, Telstra Limited 20, EGIHosting 20, webhosting servers 20,
  Sichuan Yihu Data Technology 23 (unsure). The shared denylist check finds 0 hits on these rows, so this is a rule gap, not a matcher failure.
- Root cause: no exact, prefix, pattern or keyword rule covers them (whole-word keywords: 'EGIHosting' and 'webhosting' are one token; 'unicom', 'cogent', 'comcast' are not rules).
- Fix: owner decision on new rules through the existing 90% gate; stage code unchanged. A real fix is data-integrator work.
- Contract rule: none can catch an unlisted name. Mitigation in the contract: the resolved share of `identity_source` must stay inside 5% to 20% (measured 14.73%), and the
  denylist rule above fails as soon as a rule for these names is added to `context/denylist*.txt` and the stage is not rerun.
- Update 2026-10-11, D7 step 1 (branch `feat/data-integrator/d7-prefixes`, proposed; decided by senior-data-engineer): DQ-002 residual accepted under D7.2. The residual metric is now
  judged on the full run by the top 50 orgs by final `contact_score`; reopen if more than 5 of the 50 read as operators. Status: ACCEPTED (D7.2).
- Status (2026-10-11 recheck): ACCEPTED (D7.2) confirmed in the entry above; decision not edited. New measurement for the senior engineer: see DQ-005 (the long tail is wider than the row-count top 50 shows).

## DQ-003 Removed duplicate rows are re-scans, not copies (extends PIPE-002)
- Symptom: the stage report says "2,242 duplicate rows removed". Recomputed from the raw sample: 100,000 rows, 97,758 distinct keys, 1,098 key groups covering 3,340 rows;
  0 of the 1,098 groups consist of copies with one timestamp; 976 groups have different `hostnames` arrays (2,105 extra distinct arrays dropped).
  The kept row is the latest timestamp in all 97,758 groups (0 exceptions).
- Root cause: as PIPE-002 (same endpoint scanned again with another banner or hostname); this is a measurement, not a new defect.
- Fix: none required for correctness of the key; decision on aggregating hostnames stays open (owner).
- Contract rule: key (host_ip, port, transport) unique and non-null (passes). The "lost hostnames" effect has no rule; it is documented only.
- Status (2026-10-11 recheck): UNCHANGED, still a documented measurement. Recomputed on the D6/D7 output: 100,000 raw rows, 97,758 keys, 2,242 removed, 1,098 groups, 0 groups of one-timestamp copies, kept row is the latest in all groups;
  `dup_count` now records the group size: `sum(dup_count - 1)` = 2,242 = raw rows minus kept rows, and `dup_count` equals my per-key count on every row. Contract rules added: `dup_count` INTEGER, not null, >= 1, and the custom
  check `sum(dup_count - 1) + count(*) = 100000` (sample constant; replace with the full-file raw row count on the full run).

## DQ-004 RAT noise rule is suffix-based: 185 backdoor-module rows are not noise
- Symptom: `is_noise` flags 505 of 505 rows whose `shodan_module` ends in 'rat' (matches the stated rule exactly), but `xiaongmai-backdoor` (183 rows) and `njrat78` (2 rows)
  are not noise although the module names read as backdoor / njRAT (names only).
- Root cause: rule written as "module ends in rat" (`RAT_MODULE_SUFFIX`); the author lists this as an open choice.
- Fix: owner decision. If accepted as noise, extend the rule; if not, document the module names as accepted.
- Contract rule: "is_noise rows have a tag or a module ending rat" and "noise tags or RAT module imply is_noise" (both pass). A rule for 'backdoor' / 'rat' anywhere in the name is NOT added
  because it would fail on a decision that is still open; add it when the owner decides.
- Status: CLOSED by design (D6.1, 2026-10-11). The rule is now the explicit pattern `(^|-)rat$|^njrat$|^blackshades$`: noise rows 1,089 to 1,136 (the 47 added rows are `blackshades`, all flagged noise).
  `njrat78` (2 rows) and `xiaongmai-backdoor` (183 rows) are deliberately NOT noise; recomputed: 0 of the 185 are `is_noise` through the module. Contract rules replaced and added in `hosts.yml`: "D6.1 RAT module pattern implies
  is_noise", "is_noise rows have a noise tag or a module matching the D6.1 pattern", "njrat78 and xiaongmai-backdoor are not noise by module alone". Mutation test: flipping `njrat` rows to not-noise and `xiaongmai-backdoor` to noise fails all three.

## PIPE-004 Cert O still admits device-vendor, router-model, hostname and random-string values after D6 (residual of DQ-001)
- Symptom: after the D6 rules, 557 `cert_o` rows (420 distinct names) remain on the spread sample. A regex read of the cert O text (one reviewer, crude, so an upper bound) flags about 83 rows / 73 names that are not tenants: device vendors (Grandstream, Hanwha Techwin, Super Micro Computer, UBNT, NETGEAR, ZTE, Dahua, Foscam, Cradlepoint, Avigilon, Samsung Electronics, Dell Inc.), router or firmware strings (`RT-AX88U-AF80`, `ZenWiFi_XD4-58D0`, `OpenWrt16ef7d1c`, `Teltonika38b8a02e`, `ASUSWRT-Merlin-KoolShare`), hostnames used as O (`mail.kavzesmail.com`, `*.esecuritel.com`), random strings (`ZVZOWZYKN`, `JFYRFHEOWRJUWYDM`), placeholders (`Dummy`, `Internal`), and operators the keyword list does not cover (a ChinaNetCenter cert O, `Aruba S.p.A.`, `Beijing Baidu Netcom`).
- Root cause: the cert O check uses the shared org-name denylist plus `cert_default_names.txt`; those lists were built for registrant names, not for device certificate strings. D6.4 listed a fixed set of vendors; the long tail is open by design. Not a code error: `1_clean.py` applies `match_name` (all rule types) as decided.
- Fix: none in this stage (no rule added to make a check pass). Options for the owner/senior: extend `cert_default_names.txt` through the integrator's gate, or a name-shape guard at stage 2/4 (hostname-like or all-caps random string). D6.4 stage 3 rule already limits host-borne signals for cert_o companies.
- Contract rule: none catches it today; the `check_hosts_extra.py` recompute of `cert_usable` only proves the stage applies the rule, not that the rule is complete.
- Update (data-quality-engineer, 2026-10-11, measurement for the senior): by hand review of cert_o names only, about 21% of cert_o rows and 23% of distinct names are not plausible tenants counting UNSURE (12% and 14% if UNSURE counted as tenants), below a 90% tenant bar. See `outputs/dq/hosts_recheck_2026-10-11.md`.
- Status (2026-10-11, cross-reference only): decided by the senior in D8.1 (ARCHITECTURE section 15): cert_o stays an identity source, `identity_confidence = low` for companies with no org host, capped into `review` at M2; closed as "accepted, residual in section 11.2 item 14". The `companies.yml` contract now enforces the label (`identity_confidence` high exactly when `org_host_count > 0`); it still cannot catch an unlisted device name.

## DQ-005 The operator long tail is wider than the row-count top 50 shows (measurement for D7.2; two small leaks)
- Symptom: on `identity_source = 'org'` (12,804 rows, 5,395 distinct names, 3,834 of them with one row) a seeded sample (seed 5) of 20 single-row names read, by name only, as network operators, hosts or research networks for 9 of 20
  (Asian Internet Interconnection Initiatives, DFN research network, Cape Connect Internet, KatCloud, Binary Racks Cloud, MM Comunicaciones, AGE Telecomunicacoes Ltda, Itanetbahia Comunicacao Multimidia, EDIS Infrastructure), 3 more unsure.
  Top-20 by rows are mostly real companies (Egnyte, Fiserv, Wal-Mart, Avago, Salesforce, ServiceNow) but include Guangzhoushi Guangbodianshiwangluo 64 (a broadcast network) and Huawei International 34. Also: `Huawei Clouds Chile` (5 rows) is `org`
  while `Huawei Cloud Thailand Region` is a prefix hit; `TIM S/A` and `IP hosted by Host-Unlimited.de` are `org`.
- Root cause (hypothesis, labelled): the D6.7/D7.2 rules are word and prefix lists; a one-row operator name has no rule. The D7.2 trigger uses the top 50 by `contact_score`, which is biased to multi-row, multi-vulnerability orgs, so it may understate the tail that a rep scrolls to.
- Fix: none by DQ (decided D7.2: accepted, M2 `operator_name_shape` penalty). Informational for the senior: the tail share of one-row names is about 40% by a 20-name sample (names only, single reviewer, wide interval); re-measure on the full run.
- Contract rule: none can catch an unlisted name. The resolved-share range (5% to 20%, measured 13.67%) and the shared denylist on `name_norm` stay as the guards.
- Status (2026-10-11, cross-reference only): decided by the senior in D8.2: `huawei` org prefix (applied; hosts rerun, 94/94 contract checks pass), `operator_name_shape` penalty and review cap and the singleton cap are M2 requirements (stage 4), not stage 2. Nothing to enforce in `companies.yml` beyond the shared denylist on `name_norm` and `company_name`.

## PIPE-005 The `huawei` prefix moved 46 rows to infrastructure_unresolved and 1 row to cert_o, not 47 and 0 (D8.10 expectation off by one)
- Symptom: after the stage 1 rerun with the `huawei` prefix the sample shows `org` 12,757 (as expected) but `infrastructure_unresolved` 83,110 (D8 expected 83,111) and `cert_o` 558 (expected 557); stage 2 therefore gives 5,790 companies, not 5,789, and 13,315 member rows, not 13,314. Resolved share is 13.62% as expected.
- Root cause: one of the 47 Huawei rows (`159.138.6.93:9000`, org `Huawei HongKong Clouds`, reason `org_prefix`) carries a usable cert subject O (`美的集团股份有限公司`, Midea Group). D4 precedence in stage 1 sends an infrastructure row with a usable cert O to `cert_o` (as for any cloud-hosted tenant), so it became a one-row cert_o-only company. D8.10 counted all 47 as infrastructure_unresolved. Not a bug in either stage; an arithmetic oversight in the estimate.
- Fix: none needed. Numbers in the stage report are measured; D8.10 "after" column should read cert_o 558, infrastructure_unresolved 83,110, companies 5,790 (cert_o-only 403, singletons 4,169, member IPs 12,338).
- Contract rule: the companies reconciliation (sum(host_count) = member rows of hosts) catches any real divergence between the stages.
- Status (data-quality-engineer, 2026-10-11): CONSISTENT with D4 rule 3 as amended by D6.4(a) (cert_o applies when the row is infrastructure OR its org is null, and the cert O is usable). Measured: the row is `is_infrastructure` true, `infra_reason` org_prefix, `identity_source` cert_o, `name_norm` equal to its cert O; the independent per-row recompute agrees on all 97,758 rows (0 disagreements on `infra_reason`, `is_noise`, `identity_source`, `name_norm`, `cert_date_invalid`; cert_o 558 by my recompute and by the stage). No rule changed. Cross-checked: `huawei*` org_norm rows are 140 infrastructure_unresolved + 25 noise + 1 cert_o. Contract rules now catching a divergence: `companies.yml` cross-file sums and `check_companies_extra.py` reconciliation.

## DQ-006 Exact name_norm merging joins unrelated legal entities that differ only by legal suffix and country (intercom, data room)
- Symptom: of the 18 companies named under both sources, 2 look like false merges by name and country: `intercom` = `Intercom SRL` (org, AR, 1 host on port 8291) + `Intercom, Inc` (cert O, 3 hosts behind Amazon Technologies on port 443; the US SaaS company); `data room` = `Data Room SRL` (org, RO, 1 host) + `Data Room, Inc` (cert O, US, 1 host). The other 16 read as one company (Accenture, Adobe, Ernst & Young, Salesforce, Sony Corporation of America, University of Utah ...). Within the 123 companies with 2 or more raw spellings, all share a common stem; the only legal-suffix jurisdiction mixes are xTom (`xTom`, `xTom GmbH`, `xTom Pty Ltd`, one hosting group across DE, JP, HK, SG, NL, GB, US and AU, so benign), Electronic Arts GmbH + Electronic Arts, Inc. (same group), Proximus NV and NV/SA, and the two above. Names and countries only; one reviewer; no external lookup.
- Root cause (hypothesis, labelled): D1/D8.3 normalisation strips legal suffixes before the exact match, so `SRL` and `Inc` entities of one trade name get one `name_norm`. This is the precision-over-recall rule working at its weak point, not an implementation error: the stage output equals my independent recompute on all 5,790 companies.
- Fix: none by DQ. Decision for the senior/owner: accept (2 of 5,790 companies, 5 hosts) or keep the suffix family when the legal-suffix tokens differ across jurisdictions. Not changed.
- Contract rule: none can catch it without ground truth. `check_companies_extra.py --spellings 20` prints the companies with the most raw spellings for the standing false-merge review (D8.8 rule 10); a count of cross-source merges (18) is reported on every run.

## DQ-007 Spelling variants of one company are not merged (recall cost of exact name_norm, measured)
- Symptom: `Salesforce` (12 hosts, org `Salesforce` plus cert O) and `Salesforce.com, Inc.` (181 hosts) are two companies; likewise `Fiserv, Inc.` (1) and `Fiserv Solutions, LLC` (328), `Dattatec Corp` (19), `Dattatec.com` (15) and `DATTATEC.COM S.R.L.` (2), `Leaseweb USA, Inc.` (19) with its city variants (5 and 1). Three pairs differ only by a trailing ` com` (`salesforce`/`salesforce com`, `dattatec`/`dattatec com`, `servers`/`servers com`).
- Root cause: by design (D8.3: no fuzzy, no parent-subsidiary merging). Not a defect; the cost is split companies and understated host counts for the smaller halves.
- Fix: none; reported, not hidden. Reopen only if a stage 4 review shows duplicate accounts in the contact list.
- Contract rule: none; the raw-spelling table in `check_companies_extra.py` and the stage report section 6 show the merges that did happen, not the splits.

## DQ-008 A single honeypot row puts a one-host company at noise_host_share 0.5 (D8.6 preview threshold)
- Symptom: 4 companies have `noise_host_share >= 0.5`: `Civo LTD` (1 host, 1 noise), `Jummah-Mosque-Str` (1, 1), `WebSP - Comercio e Prestacao de Servicos Informaticos, Lda` (1, 1) and `SC Lithuanian Radio and TV Center` (2 hosts, 3 noise). Three of the four are one host plus one honeypot row on the same org name; `Civo LTD` is a cloud host not on the denylist. The honeypot rows of `SC Lithuanian Radio and TV Center` sit in LT while its two org hosts are in US.
- Root cause (hypothesis, labelled): the share is a ratio, so any singleton with one noise row reaches exactly 0.5 and the preview threshold `>= 0.5` excludes it; with 72% singleton companies the rule is dominated by one-row cases. Honeypot tags on a real org's address could also be an org that runs a honeypot (a security-relevant fact), not an attacker.
- Fix: none by DQ. For the data-analyst at calibration: require `noise_host_count >= 2` as well as the share, or a strict `> 0.5`. Not applied.
- Contract rule: `noise_host_share` equals its formula and lies in 0..1; `noise_host_count` is 0 when `org_host_count` is 0; `check_companies_extra.py` recomputes `noise_host_count` per company through `org_norm` (0 disagreements). The threshold itself is M2 and is not contracted.


## PIPE-006 `signal_stats.py` crashes on the `risky_ports` list column (array types pass its numeric filter)
- Symptom: `python .claude/skills/signal-engineering/scripts/signal_stats.py data/gold/signals.parquet` prints the coverage rows up to `risky_service_host_count`, then stops with `Conversion Error: Unimplemented type for cast (INTEGER[] -> DOUBLE) when casting from source column risky_ports`; the redundancy section never prints.
- Root cause: `pick_signals` selects every column whose type string starts with a numeric prefix (`INTEGER`, ...), and `INTEGER[]` starts with `INTEGER`, so the list column `risky_ports` (D9.4 column 35) is cast to DOUBLE. The helper lives under `.claude/skills/`, outside the data-engineer write scope; not edited.
- Fix: workaround in the stage hand-off, pass the columns explicitly with `--signals` (every BOOLEAN, INTEGER, SMALLINT and DOUBLE column whose type does not end in `]`). Suggested fix for the owner of the skill: skip types ending in `]` in `pick_signals`. The stage itself is not affected.
- Contract rule: none (a helper script, not a data layer).
