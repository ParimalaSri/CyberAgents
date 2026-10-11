# accounts layer review (2026-10-11), data-quality-engineer

**Verdict: PASS on the SAMPLE (5,790 accounts).** Not a PASS for prod: the full file has not been run, and every constant is PROVISIONAL (not calibrated, not owner-approved; the signal list is not owner-approved). Runner report: `outputs/dq/accounts_2026-10-11.md` (contract 78/78, extra 6/6). Contract: `context/contracts/accounts.yml`. Extra check and tests: `.claude/skills/data-quality-check/scripts/check_accounts_extra.py`, `test_check_accounts_extra.py`.

The recompute was written from D9.6, D9.7, D9.9 and D10 with its own constants (it does not import or read the stage SQL). Agreement with the stage proves the rules were applied as written, not that the constants are right.

## 1. Always-check list

| check | result |
|---|---|
| companies <= hosts | held by `companies.yml` (not re-run here); accounts == signals == companies == 5,790 |
| accounts rows == signals rows == companies rows, ids unique, id sets equal both ways | PASS (5,790 each, 0 duplicates, 0 only-in on either side) |
| no hyperscaler, CDN or ISP names (shared denylist on `company_name`) | PASS (0 hits, contract and extra) |
| scores within 0 to 100, integers | PASS (fit max 85, urgency max 100, contact max 68, min 0) |
| every account has a band, a band_uncapped, a final_band and a non-empty `why` | PASS |
| `why` at most 40 words, no `=` or `_`, no breach words | PASS (0 violations) |
| band `contact` for no row while `decision` is null | PASS (0 accounts in contact) |

## 2. Independent recomputation: author versus mine

Every account recomputed from `signals.parquet` (fit, urgency, contact, band_uncapped, cap_reasons, band, top_signals): 0 disagreements on all 5,790. One-signal `top_signals` on a would-be contact (second signal dropped for the 40-word limit, tolerated): 1 account (Strato Rechenzentrum, Berlin).

| quantity | author | mine | match |
|---|---|---|---|
| rows | 5,790 | 5,790 | yes |
| contact / review / skip / exclude | 0 / 664 / 5,125 / 1 | 0 / 664 / 5,125 / 1 | yes |
| would-be contacts (band_uncapped = contact) | 107 | 107 | yes |
| cap set operator_unverified alone | 70 | 70 | yes |
| operator_unverified,singleton | 20 | 20 | yes |
| operator_name_shape,operator_unverified | 12 | 12 | yes |
| low_confidence,operator_unverified,singleton | 3 | 3 | yes |
| low_confidence,operator_unverified | 1 | 1 | yes |
| operator_name_shape,operator_unverified,singleton | 1 | 1 | yes |
| review reached by threshold alone | 557 | 557 | yes |
| accounts with urgency above 0 | 1,324 (22.87%) | 1,324 | yes |
| accounts with fit above 0 | 2,271 in the hand-off; 2,187 (37.77%) in the stage report | 2,187 now; 2,271 under the pre-D10 T1-only penalty | 2,271 is the pre-D10 figure, 2,187 is current (no stage error) |
| accounts that lost fit under the union penalty | 167 | 167 | yes |
| accounts whose contact_score changed under the union | 49 | 49 | yes |
| max contact_score before D10 (T1-only penalty) | 75 | 75 | yes |
| max contact_score now | not stated (top row 68 in the stage report) | 68 | new figure: 68 |

Quantiles (linear): fit p5 to p50 0, p75 15, p90 35, p95 50, p99 65, max 85. urgency p5 to p75 0, p90 40, p95 60, p99 65, max 100. contact p5 to p75 0, p90 23, p95 30, p99 42, max 68. These equal the stage report.

Others measured: review band singletons 325, operator-shaped (T1 or T2) 187, low confidence 21 (all equal to the stage report); threshold-only review accounts that are operator-shaped 174 of 557.

Would-be contacts 107 versus D9.8's 108: see DQ-011 (reproduced as the pre-SSH-split SSH-only points of 10, a hypothesis).

## 3. Mutation tests (`test_check_accounts_extra.py`, 47 injected faults, synthetic 17-account layer with hand-computed expected values)

The clean layer passes both detectors (0 failed checks). All 47 faults are caught by the named detector (11 tests, all 56 tests in the directory pass: `python -m unittest discover -s .claude/skills/data-quality-check/scripts -p "test_*.py"`). "C" = contract fails, "E" = extra fails.

| fault | C | E |
|---|---|---|
| duplicated account row (fan-out); missing account; account_id differs from company_id | yes | yes |
| fit_score 101; urgency_score 101 | yes | yes |
| contact_score above urgency; contact below FLOOR times urgency | yes | yes |
| would-be contact left in contact (cap_reasons removed; cap_reasons kept) | yes | yes |
| capped account with cap_reasons null; without operator_unverified; singleton reason dropped | yes | yes |
| operator_unverified on a skip account; on a threshold-only review account | yes | yes |
| excluded account not excluded; non-excluded account excluded; boundary 2 noise hosts at share 0.5 not excluded | yes | yes |
| empty why; null why; why over 40 words | yes | yes |
| why missing the D10 clause; clause on a non-contact | yes | yes |
| why names a signal the company lacks, top_signals also changed | yes | yes |
| why names a signal the company lacks, top_signals unchanged | no | yes (contract cannot read the text against signals) |
| wrong CVSS number; wrong host count; wrong country in why; cap clause does not match cap_reasons; "Exposure is limited." dropped | no | yes |
| why states a breach; shows a formula; shows a column name | yes | yes |
| final_band differs from band; decision set at stage 4 | yes | yes |
| denylisted name (accounts and signals both changed) | yes | yes |
| cap_reasons not alphabetical; outside the allowed set | yes | yes |
| fit_score wrong but consistent with contact_score (T1-only penalty form) | no | yes |
| contact_score rounded down instead of half up | no | yes |
| band_uncapped inconsistent with contact_score | yes | yes |
| top_signals wrong order | no | yes |
| top_signals missing on an account with urgency; urgency-0 account with signal text | yes | yes |
| contact_score typed BIGINT; extra raw column; carried host_count differs from signals | yes | no (contract-only rules) |
| file not sorted by contact_score | no | yes |

## 4. Hand review (one reviewer, names only)

**10 random accounts** (seeded): `schaal @it UG`, `Moy`, `Solace Corporation`, `Martin-Luther-Universitaet Halle-Wittenberg` read as organisations (4); `Pe3ny Net s.r.o.`, `Internet Union Spolka Akcyjna`, `OCHANOKO-NET`, `MANGO NETWORK` as operators (4); `INCOGNET LLC`, `K&K Kommunikationssysteme GmbH` unsure (2). 8 of the 10 are skip with "No exposure signal found in the scan (N hosts seen)."; 1 is review by threshold (`Pe3ny Net`: CVSS 9.8 plus 3 IPs, urgency 40, contact 23) and 1 is review with `operator_unverified` (Martin-Luther: 3 KEV hosts, 9 IPs, contact 42). Every statement matched signals.

**Top 25 by contact_score** (all in `review`, none in `contact`): 13 read as operators (Wowrack, Strato Rechenzentrum, Leaseweb Deutschland, Eonix, Aruba Cloud Services Farm2, Interserver, Register.com, Telia Eesti, Volcano Engine, ReliableSite.Net, Nocix, Webzilla, CloudRadium), 7 unsure (Brander Group, Aventice, High Family Technology, SOLLUTIUM EU, P.D.R Solutions FZC, PDR, Fastmos), 5 organisations (Beijing Jingdong 360, NCR, Hewlett Packard Enterprise, U.S. Marshals Service, Thai Office of Info.Tech. Admin. for Educational Development). Operator or unsure: 20 of 25 (80%). The name flag (T1 or T2) marks 4 of the 25 (Strato, Aruba, Interserver, CloudRadium; T1 alone 1), so it misses 9 of my 13 operators. The checker verified every statement in every `why` against `signals.parquet` (not only these 25); by hand I checked the 25 against the signals columns (KEV host counts, CVSS maxima, risky ports, footprint IPs, country): all agree. Strato's `why` keeps one signal because of the 40-word limit; the D10 clause is always kept.

**Bottom 20 by contact_score**: all contact_score 0, all skip, all "No exposure signal found in the scan (1 host seen)." (singletons with no signal).

**5 skip accounts with urgency 0**: `Exponential-E Ltd.` (fit 15), `The Viriyah Insurance Public Company Limited`, `Thomax Technology Pty Ltd`, `Tiscali AG`, `AIR ARABIA`: all read "No exposure signal found in the scan (N host(s) seen).", the wording D9.6 asks for; it says what the scan did not find, not that the company is safe. Skip accounts with urgency above 0 (659) read "...Exposure is limited." (DQ-013).

**The exclude account**: `SC Lithuanian Radio and TV Center`, 2 hosts, noise_host_count 3, share 0.6 (signals), band exclude, band_uncapped exclude, no cap_reasons, no top_signals, why "Mostly honeypot or attacker-infrastructure hosts (3 of 5)." (3 noise rows of 5 rows); scores fit 50, urgency 5, contact 4. It is the only account meeting the D9.3 rule on the file (5 companies have a noise host count of 2 or more; the other 4 have shares 0.017 to 0.154).

**Safety wording**: no `why` contains breach, compromised or hacked (0 of 5,790). "attacker-infrastructure" appears only in the exclude text. Two wording risks logged as DQ-013: "Exposure is limited." on 659 skip accounts (42 with an RDP/SMB/DB-type port open, 32 with CVSS of 7.0 or more) reads as reassurance; "known-exploited list" states an inferred (RAW-006) vulnerability as fact. Neither claims a breach.

## 5. Findings

| id | finding | verdict impact |
|---|---|---|
| DQ-011 | would-be contacts 108 (D9.8) vs 107; reproduced as SSH-only points of 10 in the earlier ad hoc run (hypothesis) | none |
| DQ-012 | `cap_reasons` order: D9.6 text vs alphabetical stage; contract follows the stage | none |
| DQ-013 | "Exposure is limited." on 659 skip accounts; KEV phrase states an inferred fact | wording, hand back to the data-engineer or senior |
| DQ-014 | 557 threshold-only review accounts, 174 operator-shaped, no operator clause; top 25 is 13 operators, 7 unsure | informational (D10 by design) |
| DQ-008 | status updated: the exclude threshold is now enforced | closed with a rule |

## 6. Not verified

- Not the full file: this is the 100K sample only; dev to prod needs a PASS on the full data (`accounts_full.parquet`), with the contract paths changed in that PR.
- The recompute uses the D9/D10 text, so it proves the rules were applied, not that the constants (points, FLOOR 0.5, X 40, Y 20, territory placeholder US) are right; all are PROVISIONAL and the signal list is not owner-approved. The three contract checks that hard-code FLOOR, X and Y must change with calibration.
- Hand reads are names only, one reviewer. The 13, 7 and 5 are my own count, not the author's 14, 6 and 5 (the groups differ for Register.com, Brander Group, Beijing Jingdong 360).
- Not verified: that a rerun of `4_score` on unchanged signals gives an identical file (D9.9 rule 7; needs the stage to write data); the order of cap clauses when several apply (the stage's precedence is observed, not specified); the adjudication columns at M3 (rules marked "M2 only" will change); `companies <= hosts` was not re-run (belongs to `companies.yml`).
