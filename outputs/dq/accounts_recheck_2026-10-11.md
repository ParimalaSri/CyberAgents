# Accounts recheck after D11.2 to D11.5 (2026-10-11)

Verdict: **PASS** on the 100K sample (5,790 accounts). Not the full file. Validated by data-quality-engineer (not the author); branch feat/data-quality/d11-contracts. Constants are PROVISIONAL (FLOOR 0.5, X 40, Y 20 floor, REVIEW_N 200, territory 0 points); the recompute is written from D11 text, so it shows the rules were applied, not that the constants are right.

## Checks
- Contract `context/contracts/accounts.yml`: 87/87 PASS (the author expected 3 failures of 78 on 464 rows each; the three rules were rewritten, see DQ-016).
- `check_accounts_extra.py`: 7/7 PASS (fan-out, full recompute of scores, bands, caps and top_signals, the review cut, why on every account, sort order, denylist, stage rules). One-signal fallback (second signal dropped for the 40-word limit) on 3 would-be contacts, tolerated.
- Rules rewritten: bands move only contact to review (cap) or review to skip (cut); every would-be contact is in review; cap_reasons null exactly when band_uncapped is not contact; review = would-be contacts plus the best non-excluded accounts by (contact_score, urgency_score, host_count desc, account_id) with contact_score >= 20, until 200 (SQL recompute in the contract); skip implies score below 20 or beyond the cut; skip clause, operator clause, old-wording ban, KEV and CVSS phrase rules, no in_territory top signal.

## Recomputation, author versus mine
| quantity | author | mine |
|---|---|---|
| accounts | 5,790 | 5,790 |
| contact / review / skip / exclude | 0 / 200 / 5,589 / 1 | 0 / 200 / 5,589 / 1 |
| would-be contacts | 51 | 51 |
| cut score; tie at the cut; kept; to skip | 30; 142; 7; 135 | 30; 142; 7; 135 |
| accounts above the cut score | 193 | 193 |
| cap sets: operator_unverified; +operator_name_shape; +operator_name_shape+singleton | 46; 4; 1 | 46; 4; 1 |
| review reached by top-N alone | 149 | 149 |
| operator-shaped review (via cap clause; via D11.3) | 42 (5; 37) | 42 (5; 37) |
| skip with urgency above 0 | 1,123 | 1,123 |
| below floor: total; non-SSH admin or database; CVSS 7+; overlap; union | 659; 42; 32; 0; 74 | 659; 42; 32; 0; 74 |
| at or above floor beyond the cut | 464 | 464 (9 non-SSH, 441 CVSS 7+, union 450) |
| longest why (words) | 37 | 37 |
| max fit_score | 65 | 65 |
| urgency above 0; fit above 0 | 1,324; 1,190 | 1,324; 1,190 |
| accounts whose fit fell under the T1-or-T2 penalty; contact changed | 66; 29 | 66; 29 |

No mismatch. Also: review singletons 22, low confidence 8 (author 22, 8).

## Mutation tests (synthetic 18-account layer, N = 8 in a copy of the contract; scratch only)
65 mutations; each must fail the contract, the extra checker, or both as listed; the contract failure is pinned to the intended rule where a needle is given. All caught. Cut-specific: wrong N (one too many, one too few / excluded account taking a slot), would-be contact dropped, order violation (skip above weakest review), tie broken by account_id wrongly, tie broken by host_count wrongly, floor ignored, band moved up, missing operator clause (top-N row and would-be contact), operator clause on a non-operator row, old skip, KEV, CVSS wording, territory wording, in_territory as top signal, pre-D11 territory fit. Clean layer passes both detectors. Full suite `test_*.py`: 59 tests OK. Stage suites (1_clean, 2_companies, 3_signals, 4_score): 93 tests OK. Hosts contract 94/94 and companies contract 61/61 PASS.

## Hand review (names only, one reviewer, not ground truth)
- Top 25 by contact_score: 13 operators (Strato Rechenzentrum, Leaseweb Deutschland, Aruba Cloud Services Farm2, Wowrack, Telia Eesti, Volcano Engine, OPTAGE, xTom, TimeWeb, TT DOTCOM, LIWEST Kabelmedien, Cellcom Fixed Line, Dattatec), 7 unsure (SOLLUTIUM EU, Fastmos, ANX Holding, Integen, Federal Online Group, Digital Core Technology, Eonix), 5 organisations (Beijing Jingdong 360, NCR, Hewlett Packard Enterprise, U.S. Marshals Service, Thai Office of Info.Tech. Admin.). 20 of 25 operator or unsure; the name flag marks 2 (Strato, Aruba). All 25 are review with operator_unverified; none is contact. The author read 14 / 6 / 5 (Eonix differs).
- Five top-N-only review why (Ebexo, ReliableSite.Net, Lifecell, Yorkshire Tech, ChinaTelecom Group Beijing): readable, within 40 words, no breach or formula wording; ChinaTelecom carries the operator clause, the others do not (no flagged word).
- Five skip why with a KEV host or CVSS 7+ (Virtuozzo, Optimus Technologies, quantx360, MUNDIVOX DO BRASIL, HAWKFIELD): "Below the review cut-off." after a KEV or CVSS sentence is true but can read as a dismissal; 303 skip accounts carry a KEV host and 441 CVSS 7+; the cut is a count cap and 135 accounts tie at 30 (DQ-017, DQ-018). Reported, not decided.
- The 42 operator-shaped review rows: all carry "Name looks like a network operator."; most are plain operator names; "Sprint Data Center Customer" and "Private Customer - AT&T Internet Services" say "customer" yet get the clause; "Imagine Communications Group" may be an organisation (DQ-019).
- "on outdated software" (unchanged by D11): 45 accounts (36 review, 9 skip). 16 rest on an end-of-life tag; 29 rest only on a version-matched CVSS of 7.0 or more with no EOL tag. It reads as fact, not "version-matched", for those 29 (DQ-019). Not decided.

## Not verified
Full file; names-only single-reviewer reads; constants (provisional, no ground truth); no adjudicator exists; signal list not owner-approved.
