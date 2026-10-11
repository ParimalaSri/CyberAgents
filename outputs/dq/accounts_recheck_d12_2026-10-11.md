# accounts recheck after D12 (2026-10-11, 100K sample, data-quality-engineer)

Branch `feat/data-quality/d12-contracts`. Layer: `data/gold/accounts.parquet` (5,790 rows) against `signals.parquet` and `companies.parquet`. The stage was not edited. The recomputation is written from the D12 text, not from `pipeline/4_score.py`; one exception: how many ports a why names (at most two, port 22 left out of the non-SSH phrase) was read from the output and from the stage constants, because D12 does not state it. It proves the rules were applied, not that the constants are right (all provisional).

## Verdict: PASS

| runner | result |
|---|---|
| `check_contract.py` hosts.yml | 94/94 |
| companies.yml | 61/61 |
| signals.yml | 127/127 |
| accounts.yml | 90/90 (was 87; the skip-clause rule became two, plus one "never together" rule, plus one exposure-phrase rule) |
| `check_hosts_extra.py` | RESULT: PASS |
| `check_companies_extra.py` | 5/5 |
| `check_signals_extra.py` | 10/10 |
| `check_accounts_extra.py` | 7/7 |
| data-quality tests (`unittest discover`) | 62 tests, OK |
| stage suites (`scripts.test_1_clean ... test_4_score`) | 101 tests, OK |

Old contract against the new output (copy of `accounts.yml` at a7131f2): 84/87, the 3 failures the author predicted, reproduced: review cut recompute 14, skip implies rank 7, skip clause 537.

## Independent recomputation: author versus mine (all from signals.parquet)

Every row below matched (0 mismatches over 42 quantities; the full table is in `accounts_extra_d12_2026-10-11.md`). The ones asked for:

| quantity | author | mine | match |
|---|---|---|---|
| bands contact / review / skip / exclude | 0 / 200 / 5,589 / 1 | 0 / 200 / 5,589 / 1 | yes |
| would-be contacts | 51 | 51 | yes |
| cut score, tie, kept, to skip, above the cut | 30, 142, 7, 135, 193 | 30, 142, 7, 135, 193 | yes |
| kept flagged at the cut | 0 | 0 | yes |
| names of the 7 kept | Alta Gracia Project Holding Ltd, Provider Ktechnology, Brainoza OU, SugarHosts, Seiko Electric Co.,Ltd., Free Way Tecnologia, Owl Limited | identical | yes |
| the 7 that left review (D11 order recompute) | GCI Network Solutions, NTT PC Communications, Ziply Fiber, CSLOXINFO-IDC, Zen Internet, The Infrastructure Group, Zillion Network | same 7, with the legal suffixes the author trimmed (GCI Network Solutions Limited, NTT PC Communications, Inc., The Infrastructure Group B.V., Zen Internet Ltd, Zillion Network Inc) | yes (names only differ by suffix) |
| review operator-shaped rows, now / D11 order | 35 / 42 | 35 / 42 | yes |
| skip rows with the new clause | 537 (303 KEV, 234 CVSS; 455 at or above the floor, 82 below) | 537 (303, 234; 455, 82) | yes |
| skip rows with the plain clause | 586 | 586 | yes |
| accounts with the new exposure phrase | 40 (senior: 45) | 40 in the file, 40 recomputed | yes (see the 40 versus 45 note) |
| longest why, all rows / skip rows | 40 / 33 | 40 (file), 40 (my phrase-and-clause recount) / 33 | yes |
| top-25 order versus the D11 order | not reported by the author | 7 of 25 positions differ: Integen and HPE swap (13, 14); TimeWeb, Digital Core, OPTAGE, xTom rotate (16 to 19); Beget LLC enters at 25, Dattatec Corp leaves | n/a |
| fit, urgency, contact, band_uncapped, cap_reasons, band, top_signals (with fallback) | n/a | 0 disagreements on 5,790 accounts | yes |
| why word recount (phrases and clauses) equals the stored why | n/a | 5,790 of 5,790 | yes |

### 40 versus 45 (reported, not decided)

- 48 accounts have `exposed_and_outdated` among their top two signals.
- D11 run: 3 were already cut to one signal by the 40-word fallback (Aruba S.p.A. - Cloud Services Farm2, Strato Rechenzentrum Berlin, Virtuo Networks France SAS), so 45 showed the old phrase. This is the senior's 45.
- D12 run: the new phrase is 10 words longer, so 5 more cross 40 words (Wowrack.com, Integen Inc, Leaseweb Deutschland GmbH, Beijing Jingdong 360 Degree E-commerce Co., Ltd., Mega Cable S.A. de C.V.). 8 keep one signal; 48 - 8 = 40 show the phrase.
- All 8 are would-be contacts (D10 clause, 13 words). The author's "8 review rows pushed over 40" counts the 3 earlier ones too.
- Fallback correctness: applied on exactly the 8 rows whose two-signal why recounts to more than 40 words (45 to 53 words), on no other row, and the kept signal is the first one. Under my recount a skip row never gets near the limit (longest 33).

## Mutation tests (synthetic layer of 21 accounts, N = 8; every mutation made on a scratch copy only)

All caught, by the detector named and by the intended rule (contract rule name or extra check name pinned):

| mutation | caught by |
|---|---|
| old tie order (host_count before the operator flag) | contract rank rule; extra review cut |
| flagged first (operator flag descending) | contract rank rule; extra review cut |
| kev_host_count ignored | contract rank rule; extra review cut |
| a flagged account kept at the cut over an unflagged one | contract rank rule; extra review cut |
| file sorted in the D11 order | extra file order |
| wrong skip clause on a KEV skip row; on a CVSS skip row | contract "Ranked below this run's review list" rule; extra why |
| the D12.2 clause on a skip row without KEV or CVSS | contract "Below the review cut-off" rule; extra why |
| both skip clauses together; the D12.2 clause on a review row | contract "never appear together" rule; extra why |
| old "Exposure is limited." wording | contract; extra |
| old exposure phrase "on outdated software"; phrase cut short | contract exposure-phrase rule; extra why |
| why over 40 words | contract; extra |
| fallback not applied (two signals, 49 words) | contract 40-word rule; extra recompute |
| fallback applied where not needed | extra recompute |
| second signal still named after the fallback | extra |
| earlier mutations (fan-out, caps, bands, top-N size, floor, order, clauses, types) | unchanged, all still caught (62 tests) |

The clean synthetic layer passes both detectors. It includes a tie at the cut with 3 unflagged and 1 flagged account that need all four keys (flag, kev_host_count, host_count) to separate.

## Hand review (names only, one reviewer; not ground truth)

- Top 25 by contact_score (operator count): 2 of 25 carry the flag (Strato Rechenzentrum, Aruba Cloud). By my read of the names at least 12 more look like hosting providers or ISPs (Leaseweb Deutschland, Wowrack.com, Telia Eesti, Beijing Volcano Engine, TimeWeb, OPTAGE, xTom, TT DOTCOM, LIWEST Kabelmedien, Cellcom, Beget, Fastmos). This matches D11.1 (about 75% of operators carry no flag) and is why every one of the 25 is review, not contact. Real end-user looking names: NCR Corporation, HPE, US Marshals Service, the Thai education office, SOLLUTIUM.
- The 7 kept at the cut: none flagged; 5 are singletons; SugarHosts, Provider Ktechnology and Free Way Tecnologia look like hosting or ISP names; Seiko Electric looks like an end user; Alta Gracia, Brainoza, Owl Limited unclear. Each why is true ("N host(s) running software ... known-exploited list; N host(s) on end-of-life software."). D12 predicted a modest gain only; it is.
- 5 skip rows with the new clause (ELLINIKA DIKTIA KALODION, JSC Datacenter, Silicon House, Portunity GmbH, High Speed Web/Genesis 2 Networks): "Ranked below this run's review list; a rank, not a judgement of risk." reads neutral and true after a KEV sentence and after a CVSS sentence (these rank 23 to 30 against a cut at 30 with a count cap). It is also true for the row at contact_score 5 (CVSS 6.1), where the cause is a low score, not the count cap. Two reading notes: "this run" is internal wording; the sentence has 13 words, D12.2 says 12.
- 5 review rows with the new phrase (Metrabyte, KujtesaNET Cable, Beijing Volcano Engine, Register.com, Apoteket AB): true and hedged. When the CVSS sentence comes first it says the same thing twice ("worst ... CVSS 9.8; ... on software that is end-of-life or whose version matches a CVSS 7+ vulnerability"), and a lone SSH 22 is called an "admin or database service". Long but readable.
- One fallback case (Beijing Jingdong 360 Degree E-commerce: "2 hosts running software whose version matches the CISA known-exploited list. Not yet checked ..."): true and readable, but the why no longer mentions the exposed admin or database service (ports 22 and 27017) that adds 30 of its 90 urgency points. All 8 fallback rows are would-be contacts and 6 sit in the top 25 (DQ-022).

## Issues logged (docs/ISSUES.md)

DQ-017, DQ-018, DQ-019 updated as decided and applied (D12); DQ-020 carried (D12.5); new: DQ-021 (contract lag, 3 rules), DQ-022 (fallback and the 40 versus 45 note).

## Not verified

The full file (only the 100K sample; dev to prod needs a PASS on the full data); names-only review by one reviewer; the recomputation uses D12 text, so it proves the rules were applied, not that the constants (X 40, Y 20, N 200, FLOOR 0.5, points) are right, and they are provisional; no adjudicator exists yet (decision null on every row); the signal list is not owner-approved; the port-naming rule (two ports, no 22 in the non-SSH phrase) was learned from the output.
