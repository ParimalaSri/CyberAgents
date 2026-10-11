# Step 5: test adequacy and mutation testing

## Method
31 mutations, each one text replacement in a COPY of one stage file (scratchpad `mroot\pipeline\`; the repo files and `data/` were not touched). Each mutant was run against its own stage test module (`python -m unittest -f scripts.test_<stage>`); a mutant that survived was then run against all four stage test modules. Runner: scratchpad `mut.py`. Every replacement matched exactly once (two first attempts matched 2-3 places and were re-anchored). The tests load the stage by file path relative to their own location, so the copies are what the tests exercised.

## Results

| ID | Stage | Mutation | Result | Test that caught it |
|---|---|---|---|---|
| M01 | 4_score | band rule: `contact_score >= X` becomes `> X` (band_sql) | SURVIVED (all 4 modules) | none |
| M02 | 4_score | review cut `rank <= N` becomes `< N` | KILLED | `test_excluded_accounts_never_take_a_slot` |
| M03 | 4_score | tie order: `host_count DESC` becomes ASC | KILLED | `test_cut_report_prints_score_and_tie_size` |
| M04 | 4_score | rounding `+5000` becomes `+4999` | KILLED | `test_thresholds_edges` |
| M05 | 4_score | CVSS band-3 points 40 becomes 35 | KILLED | `test_caps_only_contact_to_review_never_to_skip` |
| M06 | 4_score | exclude share `>=` becomes `>` (band rule) | KILLED | `test_exclude_rule_edges` |
| M07 | 4_score | `WHY_MAX_WORDS` 40 becomes 41 | SURVIVED | none |
| M08 | 4_score | drop the D10 "unverified" clause | KILLED | `test_cap_clauses_and_skip_texts` |
| M09 | 4_score | operator penalty 30 becomes 25 | KILLED | `test_operator_penalty_union` |
| M10 | 4_score | cap clause priority: singleton before operator | KILLED | `test_cap_clauses_and_skip_texts` |
| M11 | 3_signals | risky port 2375 (Docker) becomes 2376 | SURVIVED | none (test iterates `STAGE.RISKY_PORTS`) |
| M12 | 3_signals | risky port 6379 (Redis) becomes 6380 | SURVIVED | none (same reason) |
| M13 | 3_signals | cert soon window 30 becomes 31 days | KILLED | `test_cert_condition_branches` |
| M14 | 3_signals | cert soon `<=` becomes `<` (30-day edge) | KILLED | `test_cert_condition_branches` |
| M31 | 3_signals | cert soon lower edge `>` becomes `>=` | KILLED | `test_cert_condition_branches` |
| M15 | 3_signals | `CVSS_HIGH` 7.0 becomes 7.1 | KILLED | `test_cert_condition_branches` (name is misleading; it asserts the 7.0 edge) |
| M16 | 3_signals | footprint edge 20 becomes 21 | KILLED | `test_footprint_edges` |
| M17 | 3_signals | CDN exemption applies to org hosts instead of cert_o | KILLED | `test_cdn_rule_on_cert_o_host` |
| M18 | 3_signals | T2 operator regex without `colo` | KILLED | `test_operator_regexes_positive` |
| M19 | 3_signals | sensitive tags without `medical` | KILLED | `test_eol_and_sensitive_tags` |
| M20 | 1_clean | dedupe keeps the OLDEST timestamp | KILLED | `test_dedupe_keeps_latest_timestamp` |
| M21 | 1_clean | dedupe: drop the hash tie-break | KILLED | `test_dedupe_tie_is_deterministic` |
| M22 | 1_clean | `CERT_YEAR_MIN` 1990 becomes 1991 | SURVIVED | none |
| M23 | 1_clean | `CERT_YEAR_MAX` 2100 becomes 2099 | SURVIVED | none |
| M24 | 1_clean | `VULN_COUNT_CAP` 50 becomes 51 | SURVIVED | none (tests assert `== STAGE.VULN_COUNT_CAP`) |
| M25 | 1_clean | noise tags without `tor` | KILLED | `test_noise_precedence` |
| M26 | 1_clean | infra tags without `cdn` | KILLED | `test_infra_reason_values_and_precedence` |
| M27 | 2_companies | `company_id` hash length 16 becomes 15 | KILLED | `test_company_id_is_stable_sha256_prefix` |
| M28 | 2_companies | display name: least frequent spelling | KILLED | `test_display_name_most_frequent_then_not_upper_then_bytes` |
| M29 | 2_companies | country tie: largest code | KILLED | `test_country_majority_tie_and_nulls` |
| M30 | 2_companies | noise share denominator + 1 | KILLED | `test_noise_attribution_by_org_norm` |

Kill rate: 24 of 31 = 77.4% By stage: 4_score 8 of 10, 3_signals 8 of 10, 1_clean 4 of 7, 2_companies 4 of 4. 7 survived: M01, M07, M11, M12, M22, M23, M24.

## Survivors and what they mean
- M01 (genuine behavioural gap, Medium): an account whose `contact_score` equals X exactly stays in `review` only through the first `WHEN`; with `>` it falls to the top-N rule and can go to `skip` when its rank is beyond N. Demonstrated outside the test suite: on 5 accounts of score 8 with `--contact 8 --review 1 --review-n 1`, the original gives 5 review; the mutant gives 1 review, 4 skip. The tests `test_would_be_contacts_are_never_dropped` and `test_thresholds_edges` do not combine "score exactly at X" with "N smaller than the would-be count". Add that case.
- M07 (Low): a why of exactly 41 words is not tested; the generated why in the combinatorial test never reaches 41. Pin the limit with a synthetic row whose two-signal why is 41 words and must fall back to one signal.
- M11, M12, M24 (Low/Medium, test design): the tests take the expected values from the same constants they test (`STAGE.RISKY_PORTS`, `STAGE.VULN_COUNT_CAP`), so a wrong edit of the constant cannot fail them. Pin the literal values from the spec (section 3.2: 22, 3389, 445, 3306, 6379, 27017, 9200, 5900, 23, 2375; cap 50) in the tests.
- M22, M23 (Medium): the RAW-007 boundaries are not tested; the test uses years 4096, 0001 and 1970. My adversarial case E13 shows the code is right today (1990-01-01 and 2100-12-31 kept; 1989 and 2101 nulled), but a drift in the constant would not be noticed. Add edge dates 1989-12-31, 1990-01-01, 2100-12-31, 2101-01-01.

## Specified behaviours with NO test (by stage, from D4, D5, D6, D8, D9, D10, D11, D12)
Stage 1 (`1_clean.py`)
1. Zero-row input; zero-division in the report (E01).
2. Dedupe tie-break only for columns outside the hash (D6.5 relies on "distinct timestamps"; see step 3 R1, E08).
3. Cert date year edges 1990 and 2100 (D6.3, RAW-007); count cap 50 as a literal (D6.2).
4. Non-ASCII org text printed to a cp1252 stdout (E06b).
5. Guard against writing `--output` under `data/raw/` (no such guard exists; step 2 F-B).
Stage 2 (`2_companies.py`)
6. A batch with zero member rows (all noise, all infrastructure, all null org) (E03, E04, E05): crashes in the report assertion.
7. D8.3 "output ordered by `company_id`" and ZSTD parquet: no test mutates the order.
8. D8.7 report sections are checked only as "runs and reconciles"; individual section content (resolved share range 5 to 20) is checked by the DQ scripts, not by unit tests.
9. Display-name rule `raw_text = upper(raw_text)` for scripts without case (CJK, Arabic): every such name counts as "all upper" (a harmless tie-break quirk, Info).
Stage 3 (`3_signals.py`)
10. Zero companies / zero hosts (E01c).
11. `cert_issue` when the host `timestamp` is NULL (both comparisons become NULL, so only `cert_expired` can fire); D9.4 does not say.
12. D9.4 coverage comparison (`D9_COVERAGE`) only prints; no unit test pins any coverage number (by design, they are sample numbers).
13. The report duplicates the cert-window rule at `3_signals.py:266` instead of reusing the flag column (a second copy of the rule that tests would not keep in step; Info).
Stage 4 (`4_score.py`)
14. Score exactly at X with N smaller than the would-be count (M01).
15. Why at exactly 41 words (M07).
16. Empty signals input (E01d).
17. A negative `--review-n` is refused by a plain `assert`; no unit test pins it (E19 is mine). The refusal of `--review` at or above `--contact` IS tested (`test_4_score.py:236`). Both are `assert` statements, which `python -O` removes.
18. D12 tie order `kev_host_count` null-as-0 is tested (`test_tie_order_kev_hosts_then_host_count_then_id`); every other D9.6, D10, D11, D12 item I checked has at least one test (exclude edges, caps alone and together, floor, N larger or smaller, tie-break at the cut, skip clause by kept signal, exposure phrase, KEV and CVSS phrases, territory 0, `final_band`, output columns, determinism, `--full` defaults).

## Assessment
Boundary and ordering rules in stage 4 and the cert and CVSS edges in stage 3 are well pinned (24 of 31). The weak spots are: constants asserted against themselves, year edges, empty-input behaviour in all stages, and one band-edge combination. The existing suite does not prove stage robustness; step 3 found 9 failing edge cases that no test covers.
