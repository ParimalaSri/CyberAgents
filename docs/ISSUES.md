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
- Symptom: `.claude/skills/data-quality-check/scripts/check_contract.py` `check_denylist` reads one list from the contract and
  compares names; it has no word-boundary prefix rule, no pattern rule (CIDR/glob) and no normaliser (read from source, not run).
  The denylist now has four files (exact, prefixes, patterns, cert defaults).
- Root cause: the check was written for a single exact list.
- Fix idea: data-quality-engineer extends the check to call `scripts/denylist_match.py` (normalise, load_exact, load_prefixes, matches_pattern).
  Not edited by data-integrator (file is not in its write scope).
- Contract rule: companies.company_name_normalised must match none of the four rule types.

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
- What remains: (1) 18 candidates failed the gate in the first round and are not applied, including communications (78.0%), isp, idc, fiber,
  mobile, cloud, internet, network (telecom and telekom are now handled org-only, see the update above); an org-only scope for the others might pass
  but needs its own review (owner decision). (2) Classification was from org names only, by one reviewer. (3) Automattic / Tumblr added (see the denylist-cleanup update). (4) The rules are not enforced anywhere yet: `check_contract.py` still
  understands only the exact list (RAW-010) and does not apply prefix, pattern or keyword rules. (5) Not yet run on the full file.
- Contract rule: companies row share outside 5-20% flagged (already planned); keyword-leakage check once `check_contract.py` calls `matches_keyword`.

## RAW-014 Expectations in D3/section 10 not reproduced on the spread sample
- Symptom: port 12304 is 0.22% (expected about 2%); infrastructure share 87.63% (expected about 86%); surviving 12.34% (expected about 10%).
  Timestamp range 09:54:53 to 11:05:46 (about 71 min), the architecture doc says about 61 min.
- Root cause (hypothesis): the 21-window probe (9,239 rows) was a small, clustered sample; the port-sweep burst is in only 53 of 1,000 blocks.
- Fix idea: update ARCHITECTURE.md section 10/15 expectations (owner or senior-data-engineer). Full-file run will give the true values.
- Contract rule: none; resolved-share range check stays 5% to 20%.
