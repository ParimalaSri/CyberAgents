---
name: data-quality-check
description: Validate a data layer (hosts, companies, signals, accounts) against its contract in context/contracts/ and return PASS or FAIL with evidence. Use after any pipeline stage runs, before a PR touching data, and before dev to prod promotion.
argument-hint: <layer> [--full]
version: 1.0.0
---

# data-quality-check

Arguments: `$ARGUMENTS`

## When to use
- After a stage runs (the author never validates their own work).
- When a PR touches `pipeline/` or data; before promoting dev to prod (run on the FULL data).
- NOT for exploring unfamiliar data (use `data-profiling`).

## Inputs
- Layer name, mapped to `context/contracts/<layer>.yml`
- The layer's parquet file (path comes from the contract; `--path` overrides)
- Contract format: `references/contract_example.yml`

## Steps
1. If no contract exists yet, draft one from `references/contract_example.yml` and the layer's
   schema, then ask the user to approve it. Contracts are written before checks are trusted.
2. Run `python .claude/skills/data-quality-check/scripts/check_contract.py context/contracts/<layer>.yml --report`.
   The denylist check applies the same rules as the pipeline through `scripts/denylist_match.py`
   (exact, prefix, pattern, keyword; accent-folded; org text only, never isp). Use
   `denylist: {column, rules: shared}`; the old `{column, file}` form is exact-only. Other checks:
   `infra_reason` (values must be in the matcher's `INFRA_REASONS`) and `shares` (shares sum to 100%,
   resolved share inside a range).
3. Add the judgement checks from `references/checks_catalogue.md` (random rows, top/bottom 20,
   row count differences) and record what was seen.
4. Return a verdict: PASS or FAIL, with evidence for every failure.
5. For each bug found, add an entry to `docs/ISSUES.md`: symptom, root cause, fix, and the
   contract rule that now catches it. If no rule catches it, add one to the contract.

## Outputs
- `outputs/dq/<layer>_<date>.md` (written by `--report`)
- Updated `docs/ISSUES.md` and, if needed, `context/contracts/<layer>.yml`
- Script exit code: 0 = all pass, 1 = at least one failure

## Rules
- Reviewers return PASS/FAIL with evidence; they do not fix pipeline code.
- Allowed writes: `context/contracts/`, `outputs/dq/`, `docs/ISSUES.md`, own check scripts.
- A PASS on the sample does not authorise prod; run on the full dataset before dev to prod.

## Worked example
> `/data-quality-check companies`

```
**FAIL**: 7/8 checks passed
| FAIL | denylist leakage in 'company_name' | 897 distinct names match; e.g. 'Contabo GmbH' x1 [exact: contabo] |
```
Verdict FAIL. Root cause candidate: the stage applies only the exact list, not prefix, keyword and pattern rules.
Entry added to `docs/ISSUES.md`; control returns to the author (`pipeline-stage-build`).
(Numbers illustrative.)

## Files
- `scripts/check_contract.py` contract runner (DuckDB + pyyaml; imports the shared denylist matcher)
- `scripts/test_check_contract.py` tests for the runner
- `references/contract_example.yml` contract format
- `references/checks_catalogue.md` which checks each layer needs
