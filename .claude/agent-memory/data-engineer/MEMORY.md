# data-engineer memory (CyberIntel)

Curate this file: keep it under 150 lines, newest lessons first inside each section. No data, secrets or trace content here.

## How to work (process, learned the hard way)
- Read CLAUDE.md, then ONLY the decision record you need: grep `### D<n>` in `docs/ARCHITECTURE.md` (it is about 1,300 lines; never read it whole, earlier agents stalled doing that). Long tasks stall at about 10 minutes: work in small steps, commit after each step, use one narrow scratch table instead of rescanning the 1 GB sample.
- Branch `feat/data-engineer/<task>` cut from the CURRENT tip (the history is one linear stack). Explicit `git add <paths>`. Commit trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Never push or merge. `.claude/agents/senior-data-engineer.md` often shows as modified: it is the owner's edit, leave it.
- You never validate your own stage. End with "ready for data-quality-check <layer>". The data-quality-engineer and qa-engineer return PASS/FAIL.
- If a hook blocks you, stop and tell the owner. Never reword or fragment text to get past it (the hook blocks any command text that mentions the environment-file name, even in a grep pattern: it is a known false positive, the owner decides).
- Windows: no pandas (blocked by policy), DuckDB and plain Python only. Python heredocs mangle backslashes: use the Write/Edit tools for code with backslashes or regexes. Console is cp1252: stages call `path_guard.use_utf8_output()`. CRLF warnings from git are harmless.
- Never touch `D:/Cyber_DataSet/` or `data/raw/`. Dev sample is `data/sample/spread_100k.jsonl`; never run `--full` unless the owner says so.

## Stage rules (CLAUDE.md and `.claude/rules/pipeline.md`)
- One script per stage, reads the previous layer, writes its own. Constants at the top. Deterministic SQL/Python, NO LLM. One-line docstring on every function. Stage modules start with a digit: load them with importlib in tests.
- Every stage prints the stage report (rows, null rates, 5 random rows, difference vs previous layer, every difference explained) and writes `outputs/dq/<stage>_stage_<date>.md`. `--report` is a separate option; a non-default `--output` writes its report next to the output so a trial run never overwrites the committed report.
- Validate BEFORE writing (readable error, `sys.exit(message)`, exit 1, nothing left behind). No post-write asserts, no bare asserts for validation (`python -O` strips them). Zero-row inputs must finish with exit 0 and a valid empty output.
- All output paths go through `scripts/path_guard.py` (ALLOWLIST: plain relative or `X:/` paths only; refuses UNC, `\\?\`, device forms, colons beyond the drive, trailing dot/space/NBSP/zero-width; compares resolved paths and file identity with `data/raw` and the dataset folder). No env var or flag may switch it off. Guard tests use scratch folders with the constants patched, NEVER the real folders.

## Problems already solved (do not reintroduce)
- Dedupe in `1_clean.py`: tie-break must be TOTAL over every kept column (a hash over all of them). Two rows with the same key and timestamp that differ only in `vulns` gave order-dependent output (PIPE-008). Test: 6 shuffles, 1 output, one test per hashed column.
- `--full` must not default to the sample output: it writes `hosts_full.parquet` / `companies_full.parquet` / `signals_full.parquet`.
- `cardinality()` works on MAPs only; arrays use `len()`. DuckDB JSON read options for the raw file: `sample_size=20000, maximum_object_size=33554432, ignore_errors=true`; select columns by name (the column set differs between samples, RAW-011).
- Name rules run once per DISTINCT org then join back (scales to 8M rows). `sha256()` exists in the installed DuckDB (`company_id = substr(sha256(name_norm),1,16)`).
- Percent/rounding: stage 4 uses integer arithmetic, half up (Python `round` is banker's rounding and differs).
- cert_o rows: an infrastructure row with a usable cert organisation becomes `cert_o` (D4 rule 3, D6.4); cert O values are rejected if ANY denylist rule matches (keywords included, DQ-001).

## Decisions you must follow (details in `docs/ARCHITECTURE.md` section 15)
- D4 identity order: noise, then non-infrastructure org, then cert_o, then infrastructure_unresolved, then null_org. D5: the isp text never excludes. D8: grouping is exact `name_norm` equality only, no fuzzy matching. D6: noise pattern `(^|-)rat$|^njrat$|^blackshades$`, `cert_date_invalid`, `dup_count`, vuln count capped at 50 and informational only.
- D9/D10/D11/D12 (stage 4): `contact_score = round(urgency*(FLOOR+(1-FLOOR)*fit/100))` with FLOOR 0.5; fit penalty uses the union flag `operator_name_shape`; every would-be contact is held in `review` with cap reason `operator_unverified` (no row is `contact` until the M3 adjudicator exists); review = would-be contacts plus best accounts up to `REVIEW_N` (provisional 200) with floor 20; total sort order: `contact_score` desc, `urgency_score` desc, `operator_name_shape` false first, `kev_host_count` desc, `host_count` desc, `account_id`; territory points 0 until the owner supplies the list. All constants live in one block marked PROVISIONAL: never present them as decisions.
- `why` text: at most 40 words, plain English, no column names, never states a banner-inferred vulnerability as fact, exact strings are pinned in D11/D12 and by tests.

## Known open items
- Full-file run of stages 1 to 4 has never been done (time/memory unmeasured). Contract constants (100,000 raw rows, 5,790 counts) must change for the full run.
- Stage 1 has no consistency checks of its own (only reports its row arithmetic).
