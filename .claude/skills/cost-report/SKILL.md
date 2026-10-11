---
name: cost-report
description: Summarise LLM spend from the trace log and project production cost as tokens x volume x frequency per model, with a recommended per-run cost ceiling. Use when asked about cost or budget, before a full-dataset run, or when writing the cost model for the architecture doc.
argument-hint: [--accounts N] [--runs-per-month N] [--price-in X --price-out Y]
version: 1.0.0
---

# cost-report

Arguments: `$ARGUMENTS`

## When to use
- Before running adjudication or drafting on the full dataset.
- After each prompt version; before dev to prod; when writing `docs/ARCHITECTURE.md`.
- NOT for choosing thresholds (`scoring-calibration` decides how big the review band is).

## Inputs
- `traces/<env>.jsonl` with `model, prompt_version, input_tokens, output_tokens, latency_ms, cost_usd, decision, account_id`
- Expected volume: accounts per run (review-band size) and runs per month
- Current prices in USD per million tokens for each model. Look these up from Anthropic's
  published pricing; never quote from memory, and record the date.

## Steps
1. Run `python .claude/skills/cost-report/scripts/cost_report.py --traces traces/dev.jsonl`
   for actuals by model and prompt version (calls, avg tokens, cost, p50/p95 latency).
2. Add the projection:
   `... --accounts 5000 --runs-per-month 4 --price-in <in> --price-out <out> --out outputs/cost_report_<date>.md`
3. Fill `references/cost_model_template.md` for `docs/ARCHITECTURE.md`: model per task, the
   formula with real numbers, the levers used, and the ceiling.
4. Confirm the ceiling is actually enforced in `llm/client.py` (abort when exceeded). If not,
   file it as a blocker for `llm-engineer`.

## Outputs
`outputs/cost_report_<date>.md` and a cost-model section for `docs/ARCHITECTURE.md`.

## Rules
- Show the arithmetic. Totals without the formula do not count.
- Use cheap models for classification and stronger ones for writing; justify each choice with eval results.
- State assumptions (token counts, volume, price date) explicitly.

## Worked example
> `/cost-report --accounts 5000 --runs-per-month 4 --price-in 1.0 --price-out 5.0`

```
- per call = (900 in x $1.0/MTok + 120 out x $5.0/MTok) / 1e6 = $0.00150
- per run  = 5,000 accounts x $0.00150 = $7.50
- ceiling  = 2.0x per run = $15.00
```
(Illustrative prices and tokens: replace with current prices and trace averages.)

## Files
- `scripts/cost_report.py` actuals and projection from a trace JSONL
- `references/cost_model_template.md` structure for the architecture doc
