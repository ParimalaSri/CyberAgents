---
name: pipeline-stage-build
description: Build or fix ONE pipeline stage (1_clean, 2_companies, 3_signals, 4_score) as a single script that reads the previous layer and writes its own, with the mandatory stage report. Use when asked to build, rewrite, or rerun a pipeline stage.
argument-hint: <stage-number-or-name> [--full]
version: 1.0.0
---

# pipeline-stage-build

Arguments: `$ARGUMENTS`

## When to use
- Creating `pipeline/N_name.py`, or changing its logic.
- A stage's output is wrong: rerun THAT stage only, never the whole pipeline.
- NOT for validating a layer (use `data-quality-check`) or tuning score weights
  (use `scoring-calibration`).

## Inputs
- Previous layer's file (see data flow in CLAUDE.md section 3)
- `context/schema.md`, `context/icp.md`, and the layer's contract in `context/contracts/`
- Stage number or name

## Steps
1. Plan first (plan mode): state input, output columns, grain, and the rules to apply. Show it.
2. Copy `references/stage_template.py` to `pipeline/N_name.py` and fill in `transform`.
3. Work through `references/stage_checklist.md`.
4. Run on the sample: `python pipeline/N_name.py`. The template prints the stage report
   (row count, null rates, 5 random rows, difference vs previous layer).
5. Read the output critically. Explain any row count difference. Fix root causes, not symptoms.
6. Hand over to `data-quality-check` for the layer. Only after PASS, offer a `--full` run.
7. Commit on a feature branch (`feat/data-engineer/<task>`).

## Outputs
- `pipeline/N_name.py`
- The layer's parquet file under `data/silver/` or `data/gold/` (gitignored)
- Stage report in the console, plus new entries in `docs/ISSUES.md` for any bug found

## Rules
- One script per stage. Deterministic code only (SQL/DuckDB/Python). No LLM calls here.
- Precision over recall when grouping rows into companies; report the unresolved share.
- A run without errors is not proof of correctness; verify the output.
- The author does not sign off their own stage.

## Worked example
> `/pipeline-stage-build 2_companies`

Plan: input `data/silver/hosts.parquet`, output `data/silver/companies.parquet`, grain one row
per company, normalise org names, drop denylisted orgs, report % of hosts unresolved. After the
sample run: 100,000 hosts -> 9,412 companies, 21% of hosts unresolved (reported, not hidden). Numbers illustrative.

## Files
- `scripts/stage_report.py` mandatory report (also callable alone on any parquet)
- `references/stage_template.py` stage skeleton
- `references/stage_checklist.md` pre/post checklist and common traps
