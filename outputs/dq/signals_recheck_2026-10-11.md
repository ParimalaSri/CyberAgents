# Signals recheck after D11.1 (2026-10-11)

Verdict: **PASS** on the 100K sample (5,790 companies). Not the full file. Branch feat/data-quality/d11-contracts, validated by data-quality-engineer (not the author).

## What changed in the checks
- `context/contracts/signals.yml`: the T2 check now holds the D11.1 regex `(^| )(cloud[a-z0-9]*|host[a-z0-9]*|datacent[a-z0-9]*|rechenzentrum|fiber|fibre|isp|colo|vps|dedicated)( |$)|[a-z0-9]+(telecom|host|hosting|servers?)( |$)` (the `net` suffix branch is gone). T1 unchanged (D9.5).
- `check_signals_extra.py`: T2 recompute in Python uses the same regex; the D9.4 count table now expects operator_shape_t2 309, operator_name_shape 1,248, T2 only 202 (were 1,438 and 392).
- `test_check_signals_extra.py`: a synthetic `bellnet` company; two new mutations (a plain `...net` name flagged by T2; a T2-only name no longer flagged, each with the union kept consistent); regex unit test now asserts bellnet, public subnet, planet, magnet and "g2net sul provedor" are NOT flagged and sibirtelecom, strato rechenzentrum, rackhost are.

## Results on data/gold/signals.parquet
- Contract: 127/127 PASS (the author expected 1 failure against the old regex; it is fixed by the contract change, not by the data).
- Extra checks: 10/10 PASS. Independent recompute of all 26 signal columns from hosts and companies: 0 disagreements; T1, T2 and union: 0 disagreements; join recount 0; carried columns 0; denylist 0 hits; blind rule 180 = 180.
- Mutation tests: 36 mutations in the suite (2 new), each must be caught by the contract or the extra checker or both as listed; test_check_signals_extra 11 tests OK.

## Counts (author vs mine)
| figure | author (stage report) | mine (recompute) |
|---|---|---|
| operator_shape_t1 | 1,046 | 1,046 |
| operator_shape_t2 | 309 | 309 |
| T2 only | 202 | 202 |
| operator_name_shape (union) | 1,248 | 1,248 |
| kev_exposed | 462 | 462 |
| max_cvss_band 3 / 2 / 1 | 460 / 209 / 70 | 460 / 209 / 70 |
| cert_expired_or_soon | 373 | 373 |
| eol_stack | 352 | 352 |
| legacy_tls | 209 | 209 |
| risky_service_exposed (SSH only 158) | 226 | 226 |
| risky_non_ssh_exposed | 68 | 68 |
| exposed_and_outdated | 48 | 48 |
| sensitive_stack | 55 | 55 |
| host_signals_blind | 180 | 180 |
| in_territory (placeholder US) | 1,346 | 1,346 |
| any urgency / strong urgency | 1,294 / 662 | 1,294 / 662 |
| footprint_band 1 / 2 / 3 | 1,215 / 318 / 27 | 1,215 / 318 / 27 |

Every other signal is identical to the earlier run (the 27-figure coverage comparison against the D9.4 table, with the T2 figures updated, shows no difference).

## Warnings (not failures)
- phi(operator_shape_t1, operator_name_shape) = 0.896: expected, the union is mostly T1.
- phi(max_cvss >= 7, max_cvss_band = 3) = 0.813: expected, band 3 is a subset of 7+.

## Limits
Sample only. The recompute uses D9.4, D9.5 and D11.1 text, so it shows the rules were applied, not that the signal list is right (not owner-approved). `in_territory` is a placeholder (US) and is not used for points after D11.5.

Also rerun, unchanged stages: hosts contract 94/94 PASS, companies contract 61/61 PASS.
