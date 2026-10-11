FAIL

# QA verdict: M2 code review (branch `feat/qa/m2-review`, reviewer `qa-engineer`, steps 1 to 8)

Reason for FAIL: step 3 (adversarial testing) has 9 failing case rows with 3 root causes, one of them a non-deterministic result (R1). Steps 2 and 4 have no FAIL. Step 1 was green (163 unittest tests, 217 matcher cases, 20 hook cases). LLM behaviour does not exist, so there is no LLM verdict.

Condition that applies to any later PASS: NOT VERIFIED: the guardrail hook blocks searches that contain the environment-file string; owner decides (options: allow a Grep-tool search for the string, or narrow the hook). The check "no script reads the environment file" was not done.

## Summary by step

| Step | Result | File |
|---|---|---|
| 1 test suites | PASS (done by the previous run) | `outputs/qa/1_test_suites.md` |
| 2 mechanical rules | PASS with findings (no API code exists anywhere; no inline prompts; no LLM in `pipeline/`; 530 functions and classes, all with a one-line docstring; naming ok; no brand names in `pipeline/`; stages can write to any `--output`) | `2_mechanical_rules.md` |
| 3 adversarial | FAIL: 26 case rows, 17 PASS, 9 FAIL (3 root causes) | `3_adversarial.md` |
| 4 determinism | PASS: stages 1 to 4 reproduce the stored files exactly (97,758 / 5,790 / 5,790 / 5,790 rows, ordered hashes equal); stage 1 also identical on a shuffled input | `4_determinism.md` |
| 5 test adequacy | 24 of 31 mutants killed (77.4%); 7 survivors | `5_test_adequacy.md` |
| 6 hooks | 24 of 45 crafted events behave as expected; 21 do not (13 slips, 5 false positives, 3 covered by deny rules or unverified) | `6_hook_review.md` |
| 7 LLM readiness | nothing to test; list of missing items and 15 acceptance tests | `7_llm_readiness.md` |

## Findings

| # | Severity | File:line | Evidence | Suggested fix | Owner |
|---|---|---|---|---|---|
| 1 | Medium | `pipeline/1_clean.py:211` | Dedupe tie-break hashes only `org, isp, product, version, shodan_module, cert_subject_o, tags`. Two rows with the same key and timestamp that differ only in vulns, hostnames, domains, cert dates, etc. give different output depending on input order (case E08: 2 distinct outputs over 6 shuffles; `max_cvss` 9.8 vs 2.0). Not triggered on the real sample (shuffled input gives the same hash) but latent on the full run. | Add every kept column (or a hash of the whole raw row) to the ORDER BY. Add a unit test with a non-hashed difference. | data-engineer |
| 2 | Medium | `pipeline/1_clean.py:253`; `pipeline/2_companies.py:264`; `pipeline/3_signals.py:258`; `.claude/skills/scoring-calibration/scripts/score_distribution.py:23` | Zero-row batches crash every stage after the output is written, exit code 1: empty input (ZeroDivisionError), all-noise, all-infrastructure or all-null-org input (stage 2 `sum()` is NULL, assertion `sum(host_count) None != member rows 0`), empty companies (stage 3 assertion), empty signals (TypeError formatting NULL mean). Cases E01 to E05. | `coalesce(sum(...), 0)`, guard divisions, print "n/a"; add a zero-row test per stage. | data-engineer (stage code), data-analyst or whoever owns the skill script |
| 3 | Medium | `pipeline/2_companies.py:315`, `3_signals.py:331`, `4_score.py:548` | Stage reports are always written to `outputs/dq/<stage>_stage_[full_]<today>.md`, not tied to `--output`. A trial run with a scratch output overwrites the same-day committed report (I avoided it by running copies). | Add `--report` (or skip saving when `--output` is overridden). | data-engineer |
| 4 | Medium | `tests` for `4_score.py` band rule | Mutant M01 (`contact_score > X` instead of `>=` in `band_sql`) survives all 101 tests. Reproduced: 5 accounts at score 8, `--contact 8 --review 1 --review-n 1`: original 5 review, mutant 4 skip and 1 review. | Add a test with a would-be contact exactly at X and N below the would-be count. | data-engineer (test author), reviewed by QA |
| 5 | Medium | `scripts/test_1_clean.py` (cert dates) | Mutants M22 and M23 (1990 to 1991, 2100 to 2099) survive. The test uses years 4096, 0001 and 1970 only. My case E13 shows the code is right today. | Pin 1989-12-31, 1990-01-01, 2100-12-31, 2101-01-01. | data-engineer |
| 6 | Low | `scripts/test_3_signals.py`, `scripts/test_1_clean.py`, `scripts/test_4_score.py` | Tests compute expected values from the same constants (`STAGE.RISKY_PORTS`, `STAGE.VULN_COUNT_CAP`), so mutants M11, M12 (risky ports 2375, 6379) and M24 (cap 50 to 51) survive; M07 (`WHY_MAX_WORDS` 41) survives. | Pin literal spec values (ports list from section 3.2, cap 50, 40 words, a 41-word why). | data-engineer |
| 7 | Low | `pipeline/1_clean.py` report (print of 5 random rows) | A non-ASCII org (CJK) under the default Windows pipe encoding (cp1252) raises `UnicodeEncodeError` after the parquet is written (case E06b). | Reconfigure stdout to UTF-8 with replace, or print with `ascii()`. | data-engineer |
| 8 | Low | `pipeline/1_clean.py:222-224`, `2_companies.py:112`, `3_signals.py:172`, `4_score.py:298` | No stage refuses `--output` under `data/raw/` or the source dataset folder; `scripts/build_spread_sample.py:17-25` does. | Reuse `check_out_path` in all stages. | data-engineer |
| 9 | Low | `pipeline/4_score.py:304-305` | Threshold validation is a bare `assert` (removed by `python -O`, traceback instead of an argparse error). The negative `--review-n` refusal has no test. | `parser.error(...)` and a test. | data-engineer |
| 10 | Low | `scripts/test_4_score.py` | The suite prints a markdown report table to stdout during the run (step 1). | Redirect stdout inside the test. | data-engineer |
| 11 | High (reasoned, not executed) | `.claude/settings.json` PreToolUse matcher; `.claude/hooks/protect_files.py:34-36` | The matcher omits Grep and Glob and the hook reads only `file_path` and `notebook_path`; the deny rules cover Read, Edit and Write only. A Grep-tool search aimed at the secrets file would not be hooked. I did not run it. | Add `Grep\|Glob` to the matcher, check `path` and `glob`, add deny rules. | owner (settings and hooks are protected) |
| 12 | Medium | `.claude/hooks/protect_files.py:9,22,28` | Case-sensitive checks on a case-insensitive file system (`.ENV`, `DATA/RAW` slip); `..` not resolved in `in_raw_data` (Write to `data\silver\..\raw\x`); `D:/Cyber_DataSet/` unprotected; `find -delete`, interpreters, links and `cd`-relative paths slip. | See `6_hook_review.md` 6.3 items 2 to 4. | owner |
| 13 | Medium (false positive) | `.claude/hooks/protect_files.py:9-10,45-46` | The rule matches the secrets file name anywhere in the command text (grep pattern, commit message, echo, heredoc), and misses real reads that do not name it (`grep -rn KEY .`, `cat .en*`, quoting tricks). It blocked this review's step 2 report once. | Replace with the parsed-argument rule prototyped in `6_hook_review.md` 6.5 (0 mismatches on 42 cases). | owner |
| 14 | Low (false positive) | `.claude/hooks/branch_guard.py:11` | `PUSH_TARGET` blocks pushes of feature branches whose name contains the word dev, prod or main (`feat/qa/dev-tools`). `current_branch` returns "" in a repo with no commit, which disables the branch checks (cases H07, H18, H19 before the scratch repo had a commit). | Anchor to the refspec destination; use `git symbolic-ref --short HEAD`. | owner |
| 15 | Info | `pipeline/3_signals.py:266`; `3_signals.py:11-12`; stage helpers | The report repeats the cert-window rule instead of reusing the flag; stage 3 reads two layers (hosts and companies) by design; all stages load `.claude/skills/pipeline-stage-build/scripts/stage_report.py` by path. | Note only. | senior-data-engineer |
| 16 | Info | ARCHITECTURE.md line 1052 and 1141 versus case E14 | A company that is `host_signals_blind` can still carry `cert_expired_or_soon` (documented: cert counts all member hosts). | Confirm this is intended for the `why` of blind accounts. | senior-data-engineer |
| 17 | Info | `outputs/qa/7_llm_readiness.md` | `output_schema.json` has no field for the operator-versus-organisation answer that D10 and D11.2 make the first question. | Decide before the M3 prompt is written. | llm-engineer, senior-data-engineer |

## Mutation kill rate
24 of 31 killed (77.4%): `4_score` 8 of 10, `3_signals` 8 of 10, `1_clean` 4 of 7, `2_companies` 4 of 4. Survivors: M01 (band edge `>=` to `>`), M07 (why limit 41), M11 and M12 (risky ports 2375, 6379), M22 and M23 (cert year edges), M24 (vuln cap 51). Details and the list of behaviours with no test: `outputs/qa/5_test_adequacy.md`.

## Determinism
Stages 1 to 4 rerun on the real sample into scratch files are identical to the stored files in `data/silver` and `data/gold`, row for row and by ordered hash; stage 1 on a line-shuffled copy of the sample is identical too.

## What I did NOT verify
- The full dataset (`D:/Cyber_DataSet/`, about 7.6M to 8.9M rows): no stage was run on it; stage 1 `--full`, memory and runtime are untested, and finding 1 (latent non-determinism) could be exposed there.
- Names-only denylist validation: the denylist accuracy (D5, D6.7, D7) rests on a single reviewer's name reading; I tested the code that applies it, not whether the names are infrastructure.
- No LLM code exists: no client, no prompt, no trace, no ceiling, no eval set, no harness. Nothing about LLM behaviour was tested; only readiness was reviewed (`7_llm_readiness.md`).
- The environment-file search ("no script reads the environment file"): NOT VERIFIED, as stated above.
- Hook finding 11 (Grep tool not hooked) is reasoned from the configuration, not run.
- Whether the permission matcher's `git push --force:*` prefix also catches `--force-with-lease` and flags placed after the refspec.
- Scoring weights and bands are provisional (D9.7, D11); I tested that the code implements them, not that they are right.

## Recommendation to the senior reviewer
Do not approve a PR into `dev` on the strength of this check yet. The M2 stages are deterministic and idempotent on the real sample and the stage tests are good on band, cap, tie and wording rules. Before approval: fix finding 1 (tie-break), finding 2 (zero-row batches) and finding 3 (report path), and add the tests for findings 4 to 6. Findings 7 to 10 can follow. Route findings 11 to 14 to the owner (settings and hooks are protected); finding 11 is the most important of them. Once these are in, I will rerun steps 2 to 5 (about 15 minutes) and the verdict can be PASS, with the environment-file item still listed as NOT VERIFIED until the owner decides how it may be checked.
