# Rerun R1 and R2: test suites and mechanical rules

Branch `feat/qa/m2-rerun` (from `feat/data-engineer/qa-fixes` at c64550e). Before the run I re-synced the scratch stage copies (`root/`, `mroot/`: `pipeline/`, `scripts/`, `.claude/skills/`) from the repo working tree with `sync.sh`; the tree had no code changes (only the unrelated `.claude/agents/senior-data-engineer.md`), so the copies equal the committed code.

## R1 Test suites

| Suite | Tests | Result | Runtime |
|---|---|---|---|
| `scripts.test_1_clean` | 25 | OK | 5.3 s |
| `scripts.test_2_companies` | 19 | OK | 3.5 s |
| `scripts.test_3_signals` | 28 | OK | 8.2 s |
| `scripts.test_4_score` | 64 | OK | 13.7 s |
| `scripts.test_path_guard` | 6 | OK | 0.3 s |
| Stage suites total | 142 | OK | about 31 s |
| `scripts/test_denylist_match.py` | 217 cases | all pass | seconds |
| `.claude/hooks/test_protect_files.py` | 20 cases | 20/20 | seconds |
| data-quality-check suite (discover) | 62 | OK | 36.7 s (slowest) |

Previous run: 163 unittests (101 stage tests, 62 dq tests), 217, 20. Stage tests are now 142 (+41 vs 101). All counted tests pass.

- Slow: only the dq-check suite (36.7 s); nothing flaky seen (each suite run once; the stage suites also passed in the fix author's runs and mine).
- Real data: no test opens `data/silver`, `data/gold` or `D:/Cyber_DataSet` for reading. The new guard tests (`scripts/test_1_clean.py:356-363`, `test_2_companies.py:294-301`, `test_3_signals.py:414-419`) pass target paths under `data/raw/` and `D:/Cyber_DataSet/` and assert nothing is written; they do depend on the guard working (if the guard failed, a file `qa_guard_test.parquet` would land in `data/raw`). Residual risk, Info.
- Report tables on stdout: `scripts.test_2_companies` STILL prints a stage report to stdout (126 output lines, 54 table rows, starting "# Companies stage report"). `scripts.test_3_signals` and `scripts.test_4_score` are now quiet (5 lines: dots, Ran, OK). So the data-engineer's note is correct for stage 2 only and stale for stage 3. Low (finding 10 for stage 2 remains open).

## R2 Mechanical rules (file:line)

| # | Rule | Result | Evidence |
|---|---|---|---|
| 1 | API calls only in `llm/client.py` | PASS (vacuous) | `llm/` empty, `prompts/account_scoring/` empty, `evals/results/` empty. Grep (case-insensitive) over all `*.py` for anthropic, openai, requests, httpx, urllib, urlopen, socket, api.anthropic: 0 matches. |
| 2 | No inline prompts | PASS | Grep `pipeline/` for "You are", system prompt, messages =, model =, claude-, haiku, sonnet: 0. |
| 3 | No LLM in `pipeline/` | PASS | Imports of the four stages: argparse, contextlib, datetime, duckdb, importlib.util, io, ipaddress, pathlib, re, sys. |
| 4 | One script per stage | PASS | Four files `1_clean.py` to `4_score.py`; each loads the shared guard by path (`pipeline/1_clean.py:62-64`, `2_companies.py:38-40`, `3_signals.py:75-77`, `4_score.py:100-102`), no stage imports another. |
| 5 | Docstrings | PASS | AST check, 43 `.py` files, 612 functions and classes, 0 missing, 0 multi-line (previous: 530 over 41 files; new files `scripts/path_guard.py`, `scripts/test_path_guard.py`). |
| 6 | Naming | PASS (1 note) | Only `setUpClass` (unittest API) flagged, as before. |
| 7 | Brand names in `pipeline/` | PASS | Grep for 19 brand names: 0 matches. |
| 8 | Writes to raw or dataset folder | PASS for defaults and the listed forms, 2 bypass forms (see below) | Stage writes: `1_clean.py:234`, `2_companies.py:122,157`, `3_signals.py:182,217`, `4_score.py:308,346`. Each stage calls `guard.check_output_path(output_path)` before writing (`1_clean.py:338`, `2_companies.py:328-329`, `3_signals.py:344-345`, `4_score.py:567-568`); stages 2 to 4 also check the report path. `scripts/build_spread_sample.py` got 4 lines. No `unlink`, `rmtree` or `os.remove` in `pipeline/` or non-test `scripts/`. |

### Path guard break attempts (`scripts/path_guard.py`, 26 cases, run on Windows 11)

Harness: calls `forbidden_reason` directly (no write). Junctions to `data/raw` and `D:/Cyber_DataSet` were created inside the scratchpad only (link creation reads nothing).

| # | Input | Expected | Observed | Result |
|---|---|---|---|---|
| 01 | `data/raw/x.parquet` absolute | refuse | refused data/raw/ | PASS |
| 02 | `data/silver/../raw/x` | refuse | refused | PASS |
| 03 | `DATA/RAW/x` upper case | refuse | refused | PASS |
| 04 | relative `data/raw/x` (cwd = repo) | refuse | refused | PASS |
| 05 | `data/raw./x` trailing dot | refuse | refused (`realpath` strips the dot) | PASS |
| 06 | `data/raw /x` trailing space | refuse | refused (only by the any-`data/raw`-parts clause, `path_guard.py:24`) | PASS |
| 07 | `\\?\D:\CyberAgents\data\raw\x` | refuse | refused (same clause, because the base prefix differs) | PASS |
| 08 | UNC `\\localhost\D$\CyberAgents\data\raw\x` | refuse | refused (same clause) | PASS |
| 09 | junction to `data/raw` | refuse | refused (realpath resolves) | PASS |
| 10 | `D:/Cyber_DataSet/x` | refuse | refused dataset folder | PASS |
| 11 | `d:/CYBER_DATASET/a/../x` | refuse | refused | PASS |
| 12 | junction to the dataset folder | refuse | refused | PASS |
| 13 | UNC `\\localhost\D$\Cyber_DataSet\x` | refuse | NOT refused (returns None) | FAIL |
| 13b | `\\?\D:\Cyber_DataSet\x` | refuse | NOT refused (returns None); I proved that `\\?\<path>` is a writable form with a scratch file | FAIL |
| 14 | `D:/Cyber_DataSet./x` | refuse | refused | PASS |
| 15 | `data//raw/x` | refuse | refused | PASS |
| 16 | `data/raw::$DATA/x` (stream suffix) | refuse | NOT refused; I do not believe this form can create files in a directory (not tested), so I rate it Info | FAIL (Info) |
| 17 | `data/RAW~1/x` short name | n/a | allowed; "raw" has no 8.3 alias (3 characters), so no real route | n/a |
| 18 | drive-relative `D:Cyber_DataSet/x` | allow when cwd is the repo | resolved to `D:\CyberAgents\Cyber_DataSet\x`, allowed, which is correct | PASS |
| 19 | bare `D:/Cyber_DataSet` | refuse | refused | PASS |
| 20 | `data/raw2/x` (sibling name) | allow | allowed | PASS |
| 21 | `data/silver/hosts.parquet` | allow | allowed | PASS |
| 22 | `D:/Cyber_DataSet2/x` | allow | allowed | PASS |
| 23 | `C:/tmp/data/raw/x` (any `data/raw` anywhere) | refuse (policy) | refused (over-broad on purpose) | PASS |
| 24 | `D:/Cyber_DataSet /x` (space in the middle) | refuse | allowed; but Windows does NOT normalise it: a write to `scr /y.txt` failed with "No such file", so there is no route | n/a (not exploitable) |
| 25 | report path `data/raw/report.md` | refuse | refused | PASS |
| 26 | empty string | no crash | allowed, resolves to cwd | PASS |

Break result: the guard handles `..`, case, relative, doubled separators, trailing dot, junctions, and the raw folder in `\\?\` and UNC form. It FAILS to protect the source dataset folder when written as `\\?\D:\Cyber_DataSet\...` or as a loopback UNC `\\localhost\D$\Cyber_DataSet\...`, because `is_under` compares drive-prefix parts and the data/raw backstop clause (`path_guard.py:24`) has no equivalent for the dataset folder. New finding N1 (Low: needs deliberate use of an odd prefix; the defaults and normal typing are safe). Suggested fix: strip a `\\?\` or `\\host\share` prefix before comparing, or also refuse any path with a part equal to `cyber_dataset`.

Also noted, Info: `DATASET_DIR` is hard-coded as `D:/Cyber_DataSet/` (`path_guard.py:7`); another machine with a different folder is unprotected unless `--src` based.

## NOT VERIFIED
"No script reads the environment file": NOT VERIFIED, unchanged (the guardrail hook blocks searches containing the environment-file string; owner decides).
