FAIL

# QA rerun verdict: M2 stages 1 to 4 after the fixes (branch `feat/qa/m2-rerun`, from `feat/data-engineer/qa-fixes` at c64550e; reviewer `qa-engineer`)

Supersedes `outputs/qa/0_verdict.md` (left intact). Stage copies were re-synced from the committed repo code before every rerun.

## Why FAIL (narrow)
The rule was PASS only if R2, R3 and R4 have no FAIL. R3 (all 28 old and 20 new cases) and R4 (identical to the stored files) are clean. R2 has one FAIL, a Low finding: the new path guard does not protect the source dataset folder when the path is written as `\?\D:\Cyber_DataSet\...` or as the loopback UNC `\localhost\D$\Cyber_DataSet\...` (new finding N1). Separately, the repo test suites currently FAIL on one test because of a stray file my own mutation run left in `D:/Cyber_DataSet/` (see N2); this is an environment problem, not a code defect, and it clears when the owner deletes the file. If the owner treats N1 as accepted, everything else supports a PASS.

Conditions that apply to any PASS:
1. NOT VERIFIED: "no script reads the environment file": the guardrail hook blocks searches containing the file name; owner decides.
2. Hook findings 11 to 14 are routed to the owner (settings and hooks are protected); not re-tested, hooks were not changed by the fix commits.
3. The full dataset was not run.

## Findings 1 to 10: status

| # | Was | Status | Evidence |
|---|---|---|---|
| 1 | Dedupe tie-break narrow (non-deterministic on ties) | FIXED | E08 now 1 distinct output over 6 shuffles (was 2); N16 1 of 1 in both variants; M32 (narrow hash) killed; real sample identical |
| 2 | Zero-row batches crash | FIXED | E01 to E05, E01b to E01d PASS; N13, N13b PASS; P18 to P21 killed; the skill script `score_distribution.py` prints "0 rows" and exits 0 |
| 3 | Stage report always in `outputs/dq` | FIXED | N01, N02, N02b, N03 PASS; P07 to P09 killed |
| 4 | Band edge `>=` untested (M01) | FIXED | M01 killed; N11 edge grid PASS |
| 5 | Cert year edges untested (M22, M23) | FIXED | M22, M23, P27, P28 killed; E13 PASS |
| 6 | Tests reuse constants (M07, M11, M12, M24) | FIXED | all four killed |
| 7 | UnicodeEncodeError under cp1252 | FIXED | E06b PASS; P11, P29 killed |
| 8 | No refusal of `--output` under raw or dataset | FIXED with a residual (N1) | N05 to N09 refused in 4 of 4 stages; guard break attempts: 22 of 26 pass, `\?\` and UNC forms of the dataset folder not refused |
| 9 | Bare `assert` for thresholds | FIXED | `parser.error`, rc 2 (E19, E20, E21, N10, N12); P13, P14 killed |
| 10 | Test prints report table | PARTLY FIXED | `test_3_signals` and `test_4_score` are quiet; `test_2_companies` still prints a 126-line report with 54 table rows (Low) |

## New findings

| # | Severity | Where | Evidence and reproduction | Suggested fix |
|---|---|---|---|---|
| N1 | Low | `scripts/path_guard.py:15-18,24-28` | `forbidden_reason("\\?\D:\Cyber_DataSet\x")` and `forbidden_reason("\\localhost\D$\Cyber_DataSet\x")` return None (allowed); a `\?\` path is writable (proved on a scratch file). The data/raw side is covered by the any-parts clause, the dataset side has no equivalent. Also `data/raw::$DATA` form allowed (Info). | Strip `\?\` and `\host\share` prefixes before comparing, or also refuse any path with a part equal to `cyber_dataset`. Add the two forms to `test_path_guard`. |
| N2 | Medium (environment, caused by me) | `D:/Cyber_DataSet/qa_guard_test.parquet` | Created by my mutant P04 run (guard disabled; test target aimed at the real folder); not deleted by me. Makes `test_output_under_raw_or_dataset_folder_refused` fail in all four stage suites until the owner removes the file. Root cause for the design: tests write real targets under protected folders if the guard regresses. | Owner deletes the file. Tests should use an overridable dataset constant pointing to a temp folder. |
| N3 | Low | `pipeline/3_signals.py` (assertion after the write) | Zero-row companies with non-empty hosts: stage 3 exits 1 with a raw `AssertionError` traceback and the parquet is already on disk (N13c; E23). Loud failure is right; the leftover file is not. | Check before writing, or delete the output on failure; print a clean message. |
| N4 | Low (test gaps) | `scripts/test_1_clean.py`, `scripts/test_path_guard.py`, stage tests | 13 surviving new mutants: tie-break hash tested with one differing field (P22 to P26), no symlink or non-repo `data/raw` case (P02, P03), no `--report` under raw case (P12, P30, P16), `percent()` values unasserted (P17). | Loop the dedupe test over each hashed column; add those cases. |
| N5 | Info | `scripts/path_guard.py:7` | Dataset folder hard-coded as `D:/Cyber_DataSet/`; on another machine the guard protects only `data/raw`. | Read from config or `--src`. |

## Results by step

| Step | Result | File |
|---|---|---|
| R1 suites | 142 stage tests OK (25 + 19 + 28 + 64 + 6), 217 matcher cases, 20 of 20 hook cases, 62 dq tests OK; slowest suite 36.7 s | `rerun_1_2_suites_and_rules.md` |
| R2 mechanical | PASS on API, prompts, LLM, one script per stage, docstrings (612 of 612), naming, brands; FAIL on 2 of 26 guard break cases (N1) | same file |
| R3 adversarial | 28 old rows: 27 PASS, 1 intended failure (E23); the 9 old FAIL rows all PASS; E12 harness quirk confirmed; 20 new rows all PASS | `rerun_3_adversarial.md` |
| R4 determinism | PASS: stages 1 to 4 identical to stored (97,758 / 5,790 / 5,790 / 5,790), shuffled stage 1 identical | `rerun_4_determinism.md` |
| R5 mutation | 49 of 62 killed (79.0%): original plus M32 32 of 32; new 17 of 30 | `rerun_5_mutation.md` |

## What I did NOT verify
- The environment-file search (NOT VERIFIED; owner decides).
- Hooks and settings (findings 11 to 14): no rerun.
- The full dataset (`D:/Cyber_DataSet/`, stage 1 `--full`): memory, runtime and the latent tie case at scale.
- Whether `data/raw::$DATA` can create files; whether DuckDB itself accepts `\?\` or UNC output paths (I proved a plain Python write only).
- Junction behaviour was tested with one junction in scratch; symlinks (need privileges) not tested.
- No LLM code exists: no LLM behaviour verdict, no evals.
- Weights, bands and denylist accuracy (provisional); only that the code implements them.

## Recommendation to the senior reviewer
The ten findings are fixed except finding 10 for stage 2 (cosmetic). Determinism and the 48 adversarial rows are clean. Before approval: owner deletes the stray file (N2); data-engineer closes N1 (two path forms, a few lines) and adds the cheap tests in N4; then rerun R1 and the guard cases (about 5 minutes). I would approve after that.
