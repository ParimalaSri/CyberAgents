---
name: data-profiling
description: Profile a raw or intermediate data file (row count, null rates, distinct values, top values, sample rows) and document its schema. Use when exploring a new dataset, filling context/schema.md or context/data_notes.md, or finding fit and urgency signal candidates.
argument-hint: <path-to-file> [--sample 100000]
version: 1.0.0
---

# data-profiling

Arguments: `$ARGUMENTS` (file path, optional flags)

## When to use
- First contact with a dataset, or when a stage output looks suspicious.
- Before designing signals, to decide which columns carry fit or urgency information.
- NOT for checking a layer against its contract (use `data-quality-check`).

## Inputs
- A parquet, csv or json/ndjson file (globs allowed). Read-only: never write into `data/raw/`.
- Optional `--sample N` (default recommendation: 100000 for the first pass).

## Steps
1. Run `python .claude/skills/data-profiling/scripts/profile_table.py <path> --sample 100000 --out outputs/profile_<name>.md`.
2. Read the report with `references/profiling_checklist.md` open. Answer each checklist question
   for this dataset.
3. Draft `context/schema.md` using `references/schema_template.md` (columns, meaning, role).
4. Propose, do not decide: candidate FIT columns, URGENCY columns, entity-grouping columns and
   denylist candidates. Present them to the user for approval.
5. Log data-quality surprises in `docs/ISSUES.md`.

## Outputs
- `outputs/profile_<name>.md` (generated, can be regenerated)
- Draft `context/schema.md`
- Proposed values for context/data_notes.md (shown to the user; the user approves before editing)

## Rules
- Sample first; run the full file only after the sample findings are written up.
- State null rates and unresolved shares plainly. Do not hide bad columns.
- Never print secrets or personal data found in the file; summarise instead.

## Worked example
> `/data-profiling data/raw/hosts.csv --sample 100000`

Produces a table of 40 columns with null rates, flags that `org` is 18% null and that its top
values are `Amazon.com, Inc.` and `Google LLC` (denylist candidates), and proposes `org`,
`domain` as entity columns. (Illustrative: the file and numbers are placeholders.)

## Files
- `scripts/profile_table.py` profile any table via DuckDB
- `references/profiling_checklist.md` what to look for
- `references/schema_template.md` format for `context/schema.md`
