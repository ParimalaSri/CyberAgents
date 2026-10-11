# Step 2: mechanical rules (CLAUDE.md section 8)

Branch `feat/qa/m2-review`. Evidence is file:line from the working tree. The check "no script reads the environment file" was NOT done (see end).

| # | Rule | Result | Evidence |
|---|---|---|---|
| 1 | API calls only in `llm/client.py` | PASS (vacuous) | `llm/` is an empty folder; `prompts/account_scoring/` is empty; `evals/results/` is empty. Case-insensitive grep over all `*.py` (whole repo incl. `.claude/`, `scripts/`, `pipeline/`) for `anthropic`, `openai`, `api.anthropic`, `requests`, `httpx`, `urllib`, `urlopen`, `socket`: 0 matches. Same grep over json/toml/txt/yml (outside `data/`): 0 matches. No LLM or network code exists anywhere. |
| 2 | No inline prompt text in code | PASS | grep for `You are`, `system prompt`, `messages =`, `model =`, `claude-`, `haiku`, `sonnet` over `pipeline/ scripts/ .claude/` `*.py`: 0 matches. |
| 3 | No LLM calls in `pipeline/` | PASS | Imports in the four stages are only argparse, contextlib, datetime, duckdb, importlib.util, io, ipaddress, pathlib, re, sys. |
| 4 | One script per stage, reads previous layer | PASS with note | `1_clean.py` reads the raw JSONL (sample path, or `--full` source). `2_companies.py:11` reads `silver/hosts.parquet`. `4_score.py:13` reads only `gold/signals.parquet`. NOTE `3_signals.py:11-12` reads TWO layers (silver hosts + silver companies, companies is the spine). This is by design in D9.4 but is the only stage that reads a non-adjacent layer. Info. |
| 5 | Shared helpers loaded by file path | Info | `1_clean.py:62-63` loads `scripts/denylist_match.py`; stages load `.claude/skills/pipeline-stage-build/scripts/stage_report.py` (`1_clean.py:16,276`, `2_companies.py:16,274`, `3_signals.py:18,284`, `4_score.py:17,488`). Pipeline code depends on a file under `.claude/skills/`; if that folder moves the stages break. |
| 6 | Docstrings: every function/class has ONE line | PASS | AST check (`ast.get_docstring`, nested defs included) over all 41 `.py` files (excl. caches, data): 530 functions/classes, 0 missing, 0 multi-line. |
| 7 | Naming | PASS (1 note) | Files all `[a-z0-9_]+.py`; stages `1_clean.py` .. `4_score.py`. Classes PascalCase; functions snake_case; no lowercase module-level assignments (constants all UPPER_SNAKE). Only flagged name: `setUpClass` at `.claude/skills/data-quality-check/scripts/test_check_contract.py:238`, the unittest API override name, acceptable. |
| 8 | No hard-coded company names in `pipeline/` | PASS | grep (amazon, aws, google, microsoft, azure, cloudflare, akamai, digitalocean, ovh, hetzner, comcast, verizon, alibaba, tencent, huawei, fastly, oracle, linode, vultr, AT&T): only 2 hits, `3_signals.py:37,39`, generic regex words (`telecom`, `hosting`, `cloud`), not company names. Names live in `context/denylist*.txt`. |

## Write-sink audit (can anything write to `data/raw/` or `D:/Cyber_DataSet/`?)

| File:line | Sink | Target | Can reach raw? |
|---|---|---|---|
| `pipeline/1_clean.py:222-224` | `mkdir` + `COPY out TO` | `--output` (default `data/silver/hosts.parquet` or `hosts_full.parquet`) | YES if user passes `--output` under `data/raw/` or `D:/Cyber_DataSet/`; NO guard. Defaults safe. |
| `pipeline/2_companies.py:112-113` | `COPY companies TO` | `--output` | Unguarded. |
| `pipeline/2_companies.py:147-148` | `write_text` (report) | `outputs/dq/companies_stage_[full_]<today>.md`, not overridable | No raw. See F-A. |
| `pipeline/3_signals.py:172-173` | `COPY signals TO` | `--output` | Unguarded. |
| `pipeline/3_signals.py:207-208` | `write_text` | `outputs/dq/signals_stage_...md` | No raw. See F-A. |
| `pipeline/4_score.py:298-299` | `COPY accounts TO` | `--output` | Unguarded. |
| `pipeline/4_score.py:334-335` | `write_text` | `outputs/dq/accounts_stage_...md` | No raw. See F-A. |
| `scripts/build_spread_sample.py:67-73` | `open(args.out,"wb")` | `--out` | NO: `check_out_path` (`:17-25`) refuses any resolved path with consecutive parts `data`/`raw` (case-insensitive; resolved, so `..`, mixed case, junctions handled) and any path under the parent folder of `--src`. It does not name `D:/Cyber_DataSet/` explicitly; protected only when `--src` lives there. The check runs before mkdir/open (`:64-67`). |
| `.claude/skills/data-profiling/scripts/profile_table.py:101-102` | `open(args.out,"w")` | `--out` | Unguarded. Skill script, outside stated scope. |
| `.claude/skills/cost-report/scripts/cost_report.py:100` | `write_text` | `--out` | Unguarded. |
| `.claude/skills/data-quality-check/scripts/check_contract.py:231-232` | `write_text` | `outputs/dq/` | No. |
| `.claude/skills/account-scoring/scripts/sample_review_band.py:29,40` | `open(...,"w")` | `--out`, default `evals/candidates.jsonl` | Guards the labels file (`:29`), not raw. |
| `.claude/skills/prompt-version/scripts/prompt_tool.py:47-50` | `open(target,"x")` | `prompts/<feature>/vN.md` | Exclusive create: cannot overwrite an old version. Good. |
| `.claude/hooks/log_changes.py:26-27` | append | `.claude/logs/changes.jsonl` | No. |
| `scripts/test_*.py`, `.claude/skills/.../test_*.py` | `tempfile` dirs | temp only | No. Only `shutil.rmtree(tmp)` of its own `mkdtemp` (`test_check_contract.py:48-49`). |
| raw readers | `1_clean.py:287`, `build_spread_sample.py:69`, `check_hosts_extra.py:112` | read-only modes | No writes. |

No code calls `unlink`, `os.remove` or `rmtree` in `pipeline/` or non-test `scripts/`.

## Findings from step 2

- F-A (Medium): stages 2-4 always write their stage report to `outputs/dq/<stage>_stage_[full_]<today>.md` (`2_companies.py:315`, `3_signals.py:331`, `4_score.py:548`); the path is not an option and not tied to `--output`. A test or experimental run with a scratch `--output` silently overwrites the same-day committed report with different numbers. (I avoided this in step 4 by running copies of the stages under a scratch root.) Fix: add a `--report` option, or skip saving when `--output` is overridden. Owner: data-engineer.
- F-B (Low): no stage refuses an `--output` under `data/raw/` or the source dataset folder, while `build_spread_sample.py` does. Hooks only catch shell-text patterns, not Python arguments. Fix: reuse `check_out_path` in each stage. Owner: data-engineer.
- F-C (Low/Info): `check_out_path` protects the dataset folder only relative to `--src`; `D:/Cyber_DataSet/` is not named.
- F-D (Info): skill scripts with `--out` (profile_table, cost_report) can overwrite any path. Out of M2 scope.

## NOT VERIFIED
"No script reads the environment file": NOT VERIFIED: the guardrail hook blocks searches that contain the environment-file string; owner decides (options: allow a Grep-tool search for the string, or narrow the hook).
