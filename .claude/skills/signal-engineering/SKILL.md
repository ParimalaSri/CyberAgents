---
name: signal-engineering
description: Design, define and test fit and urgency signals (buying signals) derived from the raw columns, beyond simple filters, and document each with its rationale. Use when asked to create or improve signals, decide what makes a company need cybersecurity help, or before building 3_signals.
argument-hint: [fit|urgency] [signal idea]
version: 1.0.0
---

# signal-engineering

Arguments: `$ARGUMENTS`

## When to use
- Turning profiled columns into signals for `pipeline/3_signals.py`.
- A signal looks useless, redundant, or biased; the user asks "what hidden signals are in this data?".
- NOT for weights/thresholds (`scoring-calibration`) or company grouping (`entity-resolution`).

## Inputs
- `context/schema.md`, the `data-profiling` report, `context/icp.md`, `context/business.md`
- `data/silver/companies.parquet` (and hosts) to compute against
- Optional labelled accounts to measure lift

## Steps
1. Research first: how B2B security teams prospect (ICP fit, exposure and risk indicators,
   recency/trigger events). Let real use cases drive the list; cite what you used.
2. Propose 8 to 12 candidate signals, each in the form below, split into FIT (is this our buyer)
   and URGENCY (do they need help now). Show them to the user; do not build until approved.
   `name | fit or urgency | definition in plain English | source columns | why it matters to a buyer | failure mode`
3. Prefer signals that combine columns or add time ("exposed admin service AND outdated
   version", "new exposure in last 30 days") over a single-column filter.
4. After approval, compute them in `3_signals` (deterministic SQL) and check:
   `python .claude/skills/signal-engineering/scripts/signal_stats.py data/gold/signals.parquet [--labels evals/labeled.jsonl]`
   It shows coverage, redundant pairs (|corr| >= 0.8) and, with labels, mean among contact vs rest.
5. Drop or merge signals that are near-empty, redundant, or have no lift. Record why.
6. Document the approved set (name, definition, columns, rationale, known bias) in
   `context/schema.md` or `docs/PLANNING.md`, so scoring weights can reference them.

## Outputs
- Approved signal list with definitions and rationale
- Signal columns in `data/gold/signals.parquet` (via `3_signals`), with diagnostics from the script

## Rules
- Every signal is explainable to a salesperson in one sentence and feeds the `why` text.
- Deterministic code computes signals; no LLM here.
- Be explicit about bias: a signal that only large companies can trigger is a size proxy.
- The user approves the signal list before it is built.

## Worked example
> `/signal-engineering urgency`

Proposes `exposed_admin_service` (an administration interface reachable from the internet),
`outdated_remote_access` (remote access software behind current versions) and
`new_exposure_30d` (a service first seen recently). Script shows `exposed_admin_service` is
non-zero for 4% of companies and correlates 0.86 with `outdated_remote_access`, so the two are merged.
(Illustrative: real columns decide the list.)

## Files
- `scripts/signal_stats.py` coverage, redundancy and lift diagnostics (optional helper)
