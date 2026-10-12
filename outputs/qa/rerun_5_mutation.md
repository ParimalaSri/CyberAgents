# Rerun R5: mutation testing

## Method and an incident I caused (read first)

Stage copies were re-synced from the committed code (c64550e) before running. Mutants are applied to a scratch copy, the unit suites run, the file is restored.

INCIDENT: my first run of the new path-guard mutants used a copy whose guard still pointed at the real source folder. Mutant P04 (dataset check disabled) let a test write `qa_guard_test.parquet` (4,166 bytes, 2026-10-11 23:23:06) into `D:/Cyber_DataSet/`. That folder must never be modified. I did NOT delete it (deleting there is also a modification and outside my permission); I found it, confirmed the only such file (`find -maxdepth 2 -iname "qa_*"`), and stopped touching that folder. Consequences:
- The file is a stray created by my run. The OWNER should delete `D:/Cyber_DataSet/qa_guard_test.parquet`.
- Until it is deleted, `test_output_under_raw_or_dataset_folder_refused` in all four stage suites FAILS on the real repo (the test asserts the target does not exist; verified with `python -m unittest scripts.test_1_clean.CliRobustnessTests.test_output_under_raw_or_dataset_folder_refused`). My R1 suite results (142 tests OK) were taken BEFORE this happened.
- Design weakness for the senior reviewer: the tests aim real writes at `D:/Cyber_DataSet/` and `data/raw/`. If a guard regression ever lets one through, the test itself writes into the protected folder (this is exactly what happened with my mutant) and then fails every later run. Suggest the tests point at a temp folder via a guard constant that can be overridden.
- The results of my first two runs of the new mutants were contaminated by this file and were discarded. The results below come from a sandboxed rerun: a pristine patched copy where the dataset folder constant (guard and tests) points to a scratch folder `scratchpad/fake_ds`. Baseline on that copy: 50 of 50 tests OK before mutating. Nothing in `D:/Cyber_DataSet/` changed during the sandboxed run (still exactly the one stray file).

## Original 31 mutants plus M32 (rerun)

32 of 32 KILLED (31 before: 24 killed, 7 survived). Each is killed by its own stage's suite. The 7 former survivors are now killed:

| Mutant | Change | Killed by |
|---|---|---|
| M01 | band `>=` to `>` | `test_would_be_contact_exactly_at_contact_threshold` |
| M07 | why limit 41 | `test_limit_constant_is_forty` |
| M11, M12 | risky ports 2375, 6379 | `test_risky_port_list_literal` |
| M22, M23 | cert year 1991, 2099 | `test_certificate_year_edges` (as an ERROR, not an assertion failure: the test errors when the edge date changes class; still a kill) |
| M24 | vuln cap 51 | `test_vuln_cap_literal_values` |
| M32 (new, narrow 7-column hash again) | dedupe | `test_dedupe_tie_total_for_same_hash_columns_different_other_fields` |

## 30 new mutants on the changed code

| # | File | Mutant | Result | Killed by or why it survives |
|---|---|---|---|---|
| P01 | path_guard | drop `.lower()` (case-sensitive) | KILLED | guard test (upper-case targets) |
| P02 | path_guard | `realpath` to `abspath` | SURVIVED | no test uses a symlink or junction |
| P03 | path_guard | drop the any-`data/raw`-parts clause | SURVIVED | no test for a `data/raw` outside the repo root, or in UNC or `\?\` form |
| P04 | path_guard | dataset check disabled | KILLED | guard test |
| P05 | path_guard | off-by-one in the parts window | SURVIVED | covered by the other clause for every tested path |
| P06 | path_guard | `is_under` compares one part fewer | KILLED | `test_4_score` threshold test errors |
| P07 | path_guard | `--report` ignored | KILLED | `test_report_goes_next_to_scratch_output` and others |
| P08 | path_guard | default-output test inverted | KILLED | `test_default_output_keeps_committed_report_path` |
| P09 | path_guard | scratch report written into cwd | KILLED | `test_report_goes_next_to_scratch_output` |
| P10 | path_guard | UTF-8 `errors="replace"` to `"strict"` | SURVIVED | near-equivalent: UTF-8 encodes everything except lone surrogates |
| P11 | path_guard | `reconfigure` removed | KILLED | `test_cjk_org_under_cp1252_pipe` |
| P12 | 3_signals | drop report-path guard | SURVIVED | no test passes `--report` under `data/raw` (my N09 shows the real code refuses it) |
| P13 | 4_score | `review >= contact` to `>` | KILLED | `test_contact_below_review` |
| P14 | 4_score | `review_n < 0` to `< -1` | KILLED | `test_negative_review_n` |
| P15 | 4_score | `review_n <= 0` refused in run_stage | KILLED | `test_no_account_in_contact_and_final_band_follows_band` |
| P16 | 4_score | drop the output-path guard | SURVIVED | redundant defence: the derived report path sits next to the output and is guarded too; it would only matter with an explicit safe `--report` and an output under raw (no test) |
| P17 | 1_clean | `percent()` floor division | SURVIVED | percent values are not asserted in any test |
| P18 | 1_clean | `percent()` zero guard removed | KILLED | `test_empty_input_file` |
| P19 | 2_companies | `max(total, 1)` to `max(total, 0)` | KILLED | `test_zero_row_batches_complete` |
| P20 | 2_companies | coalesce of the member sum removed | KILLED | `test_zero_member_reconciliation_arithmetic` |
| P21 | 3_signals | coalesce of the counted sum removed | KILLED | `test_zero_row_batches_complete` |
| P22 | 1_clean | dedupe hash drops `max_cvss` | SURVIVED | no test with two rows that differ only in that column |
| P23 | 1_clean | dedupe hash drops `hostnames` | SURVIVED | same |
| P24 | 1_clean | dedupe hash drops `cert_expires` | SURVIVED | same |
| P25 | 1_clean | dedupe hash drops `os` | SURVIVED | same |
| P26 | 1_clean | dedupe hash drops `vuln_count` | SURVIVED | same |
| P27 | 1_clean | cert year min 1989 | KILLED | `test_certificate_year_edges` |
| P28 | 1_clean | cert year max 2101 | KILLED | `test_certificate_year_edges` |
| P29 | 1_clean | stage 1 skips the UTF-8 switch | KILLED | `test_cjk_org_under_cp1252_pipe` |
| P30 | 2_companies | drop report-path guard | SURVIVED | same gap as P12 |

New mutants: 17 killed, 13 survived (56.7%). Of the 13: P10 is near-equivalent, P16 is a redundant layer, P05 is masked by another clause; the real gaps are P02/P03 (symlink and non-repo `data/raw` forms), P12/P30 (explicit `--report` under raw), P17 (percent values) and P22 to P26 (the tie-break hash is tested with one differing field, not with every column; a dedupe test that loops over each column would kill all five).

## Overall

| Set | Mutants | Killed | Survived | Kill rate |
|---|---|---|---|---|
| Original plus M32 | 32 | 32 | 0 | 100% |
| New (changed code) | 30 | 17 | 13 | 56.7% |
| All | 62 | 49 | 13 | 79.0% |

Previous run: 24 of 31 (77.4%). The old weak spots are fixed; the new fix code (guard and tie-break hash) has weaker tests than the rest.
