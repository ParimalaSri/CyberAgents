---
name: data-contract
description: Draft or update the data contract (context/contracts/<layer>.yml) for a pipeline layer - columns, types, nullability, key, ranges, row-count rules, denylist - so data-quality-check can enforce it. Use when a new layer is created, a column changes, or a bug needs a new rule.
argument-hint: <hosts|companies|signals|accounts>
version: 1.0.0
---

# data-contract

Arguments: `$ARGUMENTS`

## When to use
- A layer has no contract yet; its columns or meaning changed; a bug was found and no rule catches it.
- NOT for running checks (`data-quality-check`) or exploring data (`data-profiling`).

## Inputs
- The layer's parquet file and its schema in `context/schema.md`
- The format in `.claude/skills/data-quality-check/references/contract_example.yml`
- Rules from CLAUDE.md "Data quality" (e.g. `companies <= hosts`, signals rows == companies rows,
  scores 0 to 100, every account has a band and a non-empty `why`)

## Steps
1. Read the schema and the profile of the layer. Decide the grain (one row per what?) and the key.
2. Write `context/contracts/<layer>.yml`: `layer`, `path`, `key`, `columns` (type, nullable, min/max),
   `row_rule` against the parent layer, `denylist` where company names appear, and `checks` for
   custom SQL (empty names, missing `why`, bad band values).
3. Take the ranges from MEANING, not from what the data happens to contain: a score is 0 to 100
   even if the sample's max is 87. Observed values can hide bugs.
4. Run `data-quality-check <layer>` once to validate the contract itself (does it parse, do the checks run).
5. For every bug in `docs/ISSUES.md`, make sure a contract rule now catches it; add one if not.
6. Show the contract to the user for approval; contracts change only with a reason in the PR.

## Outputs
`context/contracts/<layer>.yml`, plus ISSUES.md cross-references to rule names.

## Rules
- Writes only to `context/contracts/` (data-quality-engineer's allowed paths).
- Every rule is testable by a query. No vague rules.
- A contract is written before checks are trusted, and before a layer is promoted to prod.

## Worked example
> `/data-contract accounts`

Contract: key `account_id`; `fit_score`, `urgency_score`, `contact_score` DOUBLE in [0, 100];
`band` in contact/review/skip/exclude (custom check); `why` non-empty (custom check);
row count == companies row count. (Illustrative.)
