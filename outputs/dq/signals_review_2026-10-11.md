# Signals layer review (data-quality-engineer, 2026-10-11)

Verdict: **PASS** on the 100K sample (`data/gold/signals.parquet`, 5,790 rows, 36 columns; commit under review 7b12c2e on `feat/m2/signal-stats-fix`).
Not a verdict on the full file, and not an approval of the signal list (owner approval pending, D9.4 is PROVISIONAL).

Runner: `context/contracts/signals.yml`, 127/127 checks passed (`outputs/dq/signals_2026-10-11.md`). Extra checks: 10/10 passed
(`.claude/skills/data-quality-check/scripts/check_signals_extra.py`, whose output is reproduced in section 1).

## 1. Extra checks (independent recomputation from hosts.parquet + companies.parquet)

| result | check | evidence |
|---|---|---|
| PASS | signals rows == companies rows, company_id unique, id sets equal both ways | signals 5,790, companies 5,790, duplicate ids 0, only in signals 0, only in companies 0 |
| PASS | independent recompute of all 26 signal columns: 0 disagreements | 5,790 companies; missing 0, extra 0, duplicate 0; column disagreements none |
| PASS | regexes recomputed in Python (T1, T2, union) | 0, 0, 0 disagreements |
| PASS | max_cvss_band edges recomputed | 0 band disagreements, 0 max_cvss disagreements |
| PASS | the 10 carried columns equal companies on every row | no differences |
| PASS | join recount from hosts equals host_count and distinct_host_ips | 0 rows differ |
| PASS | host_signals_blind = companies whose every member host is cdn-tagged | stage 180, mine 180, only stage 0, only mine 0, blind but not cert_o 0 |
| PASS | denylist leakage in company_name and name_norm (shared rules) | 0 hits over 5,790 companies |
| PASS | no boolean signal is constant | none |
| PASS | company-level coverage equals the D9.4 table | 26 figures compared; differences none |

Warnings (not failures): `operator_shape_t1` with `operator_name_shape` |phi| 0.817 (nested by construction: the union contains T1);
`max_cvss >= 7` with `max_cvss_band = 3` |phi| 0.813 (the same score, two cut points; D9.6 already takes the larger single contribution, never a sum).
No boolean is outside 1% to 50% without being on the documented list.

Edge conventions verified (the recompute implements D9.4 exactly): cert row condition = raw `cert_expired` true, OR `cert_expires` strictly after the host's own
`timestamp` and at most 30 days after it (lower edge exclusive, upper edge inclusive); a null date falls back to the boolean. The real data contains 0 member rows
exactly on either edge, so the edges are proven by the synthetic unit and mutation tests only, not by the sample. `max_cvss` exactly 0.0 occurs on 0 member rows
(D9.4 would give band 1, "below 7.0", not 0; the question never arises on the sample).

## 2. Recomputation table (author = stage report 2026-10-11, mine = `check_signals_extra.py`, D9 = ARCHITECTURE D9.4 table)

| number | D9 | author (stage report) | mine |
|---|---|---|---|
| signals rows = companies rows | 5,790 | 5,790 | 5,790 |
| member host rows | 13,315 | 13,315 | 13,315 |
| counted member rows | 13,067 | 13,067 | 13,067 |
| non-counted (CDN-tagged cert_o) rows | 248 | 248 | 248 |
| companies with at least one non-counted host | 192 | 192 | 192 |
| host_signals_blind | 180 | 180 | 180 |
| kev_exposed | 462 | 462 | 462 |
| max_cvss_band 3 / 2 / 1 | 460 / 209 / 70 | 460 / 209 / 70 | 460 / 209 / 70 |
| any CVSS | 739 | 739 | 739 |
| cert_expired_or_soon | 373 | 373 | 373 |
| member rows by cert branch: boolean / window only | 286 / 150 | 286 / 150 | 286 / 150 |
| eol_stack | 352 | 352 | 352 |
| legacy_tls | 209 | 209 | 209 |
| risky_service_exposed | 226 | 226 | 226 |
| of which SSH only | 158 | 158 | 158 |
| risky_non_ssh_exposed | 68 | 68 | 68 |
| exposed_and_outdated | 48 | 48 | 48 |
| sensitive_stack | 55 | 55 | 55 |
| named_registrant | 5,387 | 5,387 | 5,387 |
| in_territory (placeholder US) | 1,346 | 1,346 | 1,346 |
| is_singleton | 4,169 | 4,169 | 4,169 |
| operator_shape_t1 | 1,046 | 1,046 | 1,046 |
| operator_shape_t2 raw | (not stated) | 738 | 738 |
| T2 only (T2 and not T1) | 392 | 392 | 392 |
| operator_name_shape (union) | 1,438 | 1,438 | 1,438 |
| any urgency signal | 1,294 | 1,294 | 1,294 |
| strong urgency | 662 | 662 | 662 |
| footprint_band 0 / 1 / 2 / 3 | 4,230 / 1,215 / 318 / 27 | 4,230 / 1,215 / 318 / 27 | 4,230 / 1,215 / 318 / 27 |

The stage report's open question (is the D9.4 "150 expiring" exclusive of the "286 expired"?) is answered: yes, 150 member rows meet the condition only through the
30-day window with the boolean false, so 286 + 150 = 436 member rows meet it, spread over 373 companies. Redundant pairs are by construction (section 1 warnings).
All matches are exact; this shows the D9.4 and D9.5 text was applied, not that the signals are right (same text, same shared matcher on the denylist).

## 3. Mutation tests

`test_check_signals_extra.py`: 11 tests, 34 injected faults on a synthetic layer (11 companies, 50 host rows with CDN, edge, udp and noise cases), each caught by the
detector(s) named. The 11 tests plus the earlier suites pass together (`python -m unittest discover -s .claude/skills/data-quality-check/scripts -p "test_*.py"`: 45 tests OK).
The clean synthetic layer passes both detectors (so the faults, not the harness, produce the failures).

| fault | caught by |
|---|---|
| duplicated company row (join fan-out) | contract, extra |
| missing company | contract, extra |
| kev_exposed flipped / flipped consistently with its count | contract and extra / extra only |
| cert_expired_or_soon flipped / flipped consistently | contract and extra / extra only |
| cert 30-day upper edge dropped; lower edge counted | extra only |
| CDN-tagged host counted for a cert_o company (CDN rule removed) | contract (counted-host sum against hosts), extra |
| legacy_tls false while count positive; `-SSLv3` treated as offered | contract and extra; extra only |
| max_cvss of 11 | contract, extra |
| band edges: 8.9 as 3, 9.0 as 2, 7.0 as 1, null with band 1 | contract, extra |
| is_singleton wrong | contract, extra |
| denylisted name_norm | contract, extra |
| carried company_name or host_count differs from companies | contract, extra |
| T1 flag flipped; union not equal to T1 or T2 | contract, extra |
| host-blind company with kev true, with max_cvss, or blind flag false | contract, extra |
| risky_ports unsorted; udp port 22 counted | contract and extra; extra only |
| exposed_and_outdated without a risky service; cleared on a same-host company | contract and extra; extra only |
| in_territory wrong; non-null with a null country | contract, extra |
| footprint_band edge wrong | contract, extra |
| risky_ports typed BIGINT[]; an extra raw column | contract only |

On the real file (copies in the scratchpad, nothing under `data/` modified): a duplicated row fails 5 contract checks and 2 extra checks; one flipped `kev_exposed` fails
1 contract check and the recompute; one `max_cvss_band` moved from 2 to 3 fails 1 contract check and 2 extra checks.

## 4. Hand review (names only, one reviewer, 100K sample)

Random 10 rows (seed 42): Ministerio del Interior de Chile (3 hosts), UNIDISH1, Tallinn University of Technology, SERPRONET LTDA (flagged operator-shaped), WideOpenWest,
Industrial Cyber Security Center of Excellence, MavianMax srl, Acadia University, CRIANN, Red del Instituto Cervantes: all 10 have `max_cvss` null, no urgency signal,
counted = host_count, and the host counts, band, footprint band and flags are consistent with their size. The sample shows no firing signal, which fits 77.65% of
companies having none; the rows therefore cannot test the signal columns, which the recompute and the next paragraph do.

Top 15 by number of firing urgency signals (kev, cert, eol, legacy tls, risky, exposed-and-outdated; ties by host_count then company_id; host org, ISP and a few domains read):
- Confident operators (hosting, cloud, telecom): 11 of 15: Strato Rechenzentrum, Aruba Cloud Services Farm2, CloudRadium, Interserver, UK Next Generation Cloud Server,
  Telia Eesti, TimeWeb, Beijing Volcano Engine, Leaseweb Canada, Leaseweb Deutschland, SERVERS TECH FZCO.
- Unsure: 2 (Digital Core Technology, Fastmos). Read as organisations: 2 (an education IT office, Beijing Jingdong 360 Degree E-commerce).
- `operator_name_shape` is true for 6 of the 15 and misses 5 of the 11 operators (Telia Eesti, TimeWeb, Volcano Engine, Leaseweb Canada, Leaseweb Deutschland).
  This is the D9.11 risk 1 and is logged as DQ-009. Urgency ranks operators first, as D9.5 predicted; it is not a stage 3 defect.

Host-blind companies (180): all 180 are `identity_source = cert_o`, `identity_confidence = low`; by an independent query on hosts, exactly 180 companies have no org host
and every member host tagged `cdn`; 48 of the 180 still fire `cert_expired_or_soon` (certificate signals use every member host, D9.4). A random 8 read as large real
brands that sit behind a CDN (Walt Disney, PNC, Honda Canada, Santos and others), so blind means "scan sees the CDN, not them", not "safe". 223 other cert_o companies are not blind.

## 5. Not verified

- Only the 100K sample. The full file (`hosts_full`, `companies_full`, `signals_full`) is not run; dev to prod still needs a PASS on the full data and a contract edit of the paths.
- The recompute reads the same D9.4 and D9.5 text and the shared denylist matcher as the stage: it proves the rules were applied, not that the signals are right.
- Names-only, single-reviewer hand review of 10 + 15 + 8 rows. The signal list, the territory list (`in_territory` is a US placeholder encoded in the contract) and the
  provisional values are not owner-approved. Cloud-tagged cert_o hosts are counted (D6.4 names only `cdn`); the effect of excluding them is not measured.
- The cert 30-day edges and a `max_cvss` of 0.0 have 0 rows in the real data; they are tested on synthetic rows only.
