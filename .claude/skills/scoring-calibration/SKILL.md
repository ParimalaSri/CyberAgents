---
name: scoring-calibration
description: Calibrate signal weights and contact/review/skip thresholds against the real score distribution, with band sizes, capacity and LLM-budget reasoning, and sensitivity checks. Use after signals are built, or when bands look wrong (too many or too few accounts in contact or review).
argument-hint: [accounts-file] [--contact X --review Y]
version: 1.0.0
---

# scoring-calibration

Arguments: `$ARGUMENTS`

## When to use
- Signals are approved and `4_score` has produced a first `accounts.parquet`.
- Bands look off, or weights changed and the distribution must be rechecked.
- NOT for fixing a data bug (use `data-quality-check` / `pipeline-stage-build`).

## Inputs
- `data/gold/accounts.parquet` (needs `fit_score`, `urgency_score`, `contact_score`)
- `context/icp.md`; `evals/labeled.jsonl` when available
- Sales capacity (accounts per week) and the per-run LLM cost ceiling, asked from the user

## Steps
1. Run `python .claude/skills/scoring-calibration/scripts/score_distribution.py data/gold/accounts.parquet --score contact_score`.
   Repeat for `fit_score` and `urgency_score`.
2. Follow `references/calibration_guide.md`: capacity for contact, budget for review, edges by hand.
3. Propose thresholds with
   `--contact X --review Y` previews and a +/-5 sensitivity table. Show the user.
4. Wait for approval, then update `pipeline/4_score.py` constants and rerun that stage only.
5. Record weights, thresholds, band sizes and reasoning in `docs/ARCHITECTURE.md`, and fill
   CLAUDE.md section 12 after the user approves.

## Outputs
- Distribution report (console) and a proposed threshold table
- Updated `docs/ARCHITECTURE.md` scoring section (after approval)

## Rules
- Weights and thresholds come from this dataset, with written reasons. Never copy another project's.
- Propose; the user decides. Do not edit CLAUDE.md section 12 unprompted.
- Do not tune on the labelled eval examples and then report them as the score.

## Worked example
> `/scoring-calibration data/gold/accounts.parquet --contact 70 --review 45`

```
bands at contact >= 70, review >= 45:
  contact       412    2.1%
  review      3,980   20.3%
  skip       15,208   77.6%
```
Review is 20%: at 900 tokens each on Haiku that is a cost the run ceiling must cover, so
propose raising `review` to 52 and re-previewing. (Numbers illustrative.)

## Files
- `scripts/score_distribution.py` quantiles, histogram, band preview
- `references/calibration_guide.md` method and what to document
