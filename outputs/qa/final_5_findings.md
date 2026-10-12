# Final F5: findings status (code at commit 05eeb10)

## Previous findings 1 to 10 (from `0_verdict.md` and `rerun_verdict.md`)
| # | Finding | Status | Evidence in this run |
|---|---|---|---|
| 1 | Dedupe tie-break narrow | FIXED (stays fixed) | M21, M32, P22 to P26 all killed; stage 1 identical on the real sample and on a line-shuffled copy (F4) |
| 2 | Zero-row batches crash | FIXED | suites green; P18 to P21 killed in the last run, not re-selected now |
| 3 | Stage report always in `outputs/dq` | FIXED | P07 to P09, N30 killed; F4 reports landed next to the scratch outputs, `git status` clean |
| 4 | Band edge `>=` untested | FIXED | M01 killed |
| 5 | Cert year edges untested | FIXED | M22, M23 killed |
| 6 | Tests reuse constants | FIXED | M07, M11, M12, M24 killed |
| 7 | cp1252 UnicodeEncodeError | FIXED | tests `test_cjk_*_under_cp1252_pipe` green in all stage suites |
| 8 | No refusal of `--output` under raw or dataset | PARTLY FIXED (see N1 below) | refused in all four stages and the sample builder, in plain, `..`, case, `\\?\`, `\\?\UNC`, loopback UNC forms; 7 further spellings are allowed (F2) |
| 9 | Bare `assert` for thresholds | FIXED | stage 4 uses `parser.error`; P13/P14 killed in the last run |
| 10 | Test prints report table | FIXED | stage 2 suite now prints 5 lines (was 126) |

## N1 to N5 from the rerun
| # | Was | Status now | Evidence |
|---|---|---|---|
| N1 | `\\?\D:\Cyber_DataSet` and loopback UNC not refused | PARTLY FIXED, still open for other spellings | the two named forms are refused (N01, N02, N03, N05, N12 kill the code that does it). F2: 7 FAIL rows remain: `\??\D:\...`, `\\?\GLOBALROOT\Device\HarddiskVolume5\...`, `\\?\Volume{GUID}\...`, `\\<ipv6-literal>\D$\...`, `\\<own LAN IP>\D$\...`, and an alternate stream on the folder itself (`D:/Cyber_DataSet:evil`, `data/raw:evil`). Severity Low |
| N2 | Stray file makes tests fail | FIXED for the tests; the file itself is the owner's | 153 of 153 green with the file present (per the main session; I did not look); tests now use scratch stand-ins; broken-guard runs wrote nothing outside temp dirs |
| N3 | Stage 3 leaves the parquet on disk when it fails | FIXED for the tested case | `check_consistency` runs before `write_output` in stages 2 to 4; N25 to N27 (moved after the write) killed. Residual: see NF-3 |
| N4 | Test gaps (P02, P03, P12, P16, P17, P22 to P26, P30) | FIXED | all 13 killed |
| N5 | Dataset folder hard-coded to `D:/Cyber_DataSet/` | NOT FIXED (Info) | `path_guard.py` line 9; it is now injectable through the function parameters for tests, but production still has one fixed constant; on another machine only `data/raw` is protected |

## New findings
| # | Severity | Where | Evidence and reproduction | Suggested fix |
|---|---|---|---|---|
| NF-1 | Low | `scripts/path_guard.py` (alias family) | `forbidden_reason("\\\\?\\GLOBALROOT\\Device\\HarddiskVolume5\\Cyber_DataSet\\x.parquet")` returns None; so do `\\?\Volume{fcf459af-bb60-412a-960c-6979b1cc2127}\Cyber_DataSet\x.parquet`, `\??\D:\Cyber_DataSet\x`, `\\192.168.1.7\D$\Cyber_DataSet\x`, `\\0-0-0-0-0-0-0-1.ipv6-literal.net\D$\Cyber_DataSet\x`, `D:/Cyber_DataSet:evil`. On the scratch analog each wrote a file (or a stream) into the protected folder. `data/raw` side is covered except for `data/raw:evil`. | Accept only plain `X:\...` paths (refuse leading `\\`, `\??\`, any `:` after position 1) or compare file identity (`os.path.samefile` on the nearest existing ancestor). Add the six cases to `test_path_guard` using the scratch-analog pattern in `final_2_guard.md` |
| NF-2 | Medium (test gap) | stage tests | 13 surviving mutants (F3): checks without a test: stage 2 infra_reason set, companies > hosts, member-sum; stage 3 fan-out, host_count reconciliation; stage 4 NULL why, contact floor, score range, `final_band <> band`, decision/prompt_version NULL; guard own-host-name UNC form. The "nothing is written" promise is tested for only one failing input per stage | one parametrised test per check using the `damaged()`/crafted-input pattern, asserting message, exit code 1, no output file, no report |
| NF-3 | Low | `pipeline/2_companies.py:190-294`, `3_signals.py:281-314`, `4_score.py:518-530` | bare `assert` statements remain in `print_report` AFTER the write. If a pre-write check is missing or tests are deleted, the stage still fails with a traceback but the parquet is already on disk (the N3 behaviour). Not reproducible today with a tested input; reproducible by removing any pre-write check (mutants N14 to N16, N19, N23, N24 survive for this reason) | remove the post-write duplicates, or keep them but treat them as a second line after the tests above exist |
| NF-4 | Info | `path_guard.forbidden_reason` | `forbidden_reason("\\\\127.0.0.2\\C$\\...")` raises `OSError` from `realpath`; the stage would stop with a traceback (no write). Safe but ugly | catch `OSError` in `check_output_path` and refuse |
| NF-5 | Info (harness correction) | `outputs/qa/rerun_3_adversarial.md` row 18 of `pg_break.py` | The old expectation for `D:Cyber_DataSet/x` was wrong when the cwd is on D: and not `D:\`; `Path(...).resolve()` follows the per-drive cwd (measured: `D:\CyberAgents\Cyber_DataSet\x`, `D:\Cyber_DataSet\x` when the cwd is `D:\` or on C:), and the guard resolves the same way as the writer. Not a finding against the code | none |

## Findings 11 to 14 (owner's decisions; NOT re-tested; hooks and settings were not changed by 2e2a1ff to 05eeb10)
| # | Severity | What | Recommended action | Owner |
|---|---|---|---|---|
| 11 | High (reasoned, not executed) | PreToolUse matcher omits Grep and Glob; deny rules cover Read, Edit, Write only; a Grep-tool search aimed at the secrets file is not hooked | add `Grep\|Glob` to the matcher, check `path` and `glob`, add deny rules | owner |
| 12 | Medium | `protect_files.py`: case-sensitive checks, `..` not resolved, dataset folder unprotected, `find -delete`/interpreters/links/`cd`-relative slip | apply `6_hook_review.md` 6.3 items 2 to 4 (and reuse the guard's identity or plain-drive rule) | owner |
| 13 | Medium | secrets-file rule matches the name anywhere in command text (false positives, it blocked a step in this review again by design) and misses reads that do not name it | adopt the parsed-argument rule in `6_hook_review.md` 6.5 | owner |
| 14 | Low | `branch_guard.py` `PUSH_TARGET` blocks branches containing dev, prod or main; no-commit repo disables the checks | anchor to the refspec destination; use `git symbolic-ref --short HEAD` | owner |
