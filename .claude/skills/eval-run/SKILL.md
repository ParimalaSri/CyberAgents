---
name: eval-run
description: Run the hand-labelled eval set against a prompt version, report precision/recall/F1 and flipped examples versus the previous version, and state the weaknesses. Use after creating or changing any prompt, or when asked how good the LLM feature is.
argument-hint: --prompt vN --baseline vM
version: 1.0.0
---

# eval-run

Arguments: `$ARGUMENTS`

## When to use
- A new prompt version exists, or the user asks "did v2 beat v1?".
- Before promoting dev to prod ("evals not regressed" is a gate).
- NOT for labelling (labels are the user's) and not for data correctness.

## Inputs
- `evals/labeled.jsonl` (20 to 30 accounts, labelled BY THE USER; never edit or overwrite)
- `--prompt vN` (candidate) and `--baseline vM` (previous)
- Design notes: `references/eval_design.md`

## Steps
1. Run the harness: `python evals/run_eval.py --prompt vN --baseline vM`. It calls the model
   through `llm/client.py` (traced, cost-capped) and writes predictions to
   `evals/results/<prompt>.jsonl` plus a results JSON.
2. Score and compare (also works on saved predictions):
   `python .claude/skills/eval-run/scripts/score_predictions.py --pred evals/results/vN.jsonl --baseline evals/results/vM.jsonl`
3. Report precision, recall, F1, the confusion matrix, which examples fixed or regressed, and
   the run cost from `traces/<env>.jsonl`.
4. Add the rules-only baseline when possible. State plainly if the LLM does not beat it.
5. Write the weaknesses: failing examples, common cause, small-n caveat, what to try next.
6. Save the summary to `evals/results/` (not over a previous result).

## Outputs
Console comparison, saved results in `evals/results/`, and a short weaknesses note.

## Rules
- Claude suggests labels with reasoning; only the user sets `label`. Never overwrite labels.
- Never tune a prompt on examples and report the same examples as the score; keep a hold-out.
- Report counts next to percentages. No hedging a bad result into a good one.

## Worked example
> `/eval-run --prompt v2 --baseline v1`

```
candidate: precision=0.80 recall=0.67 f1=0.73 (n=25)
baseline : precision=0.71 recall=0.63 f1=0.67 (n=25)
flips vs baseline: fixed=3 regressed=1
```
(Illustrative.) Weakness noted: regression on a large quiet company; n=25 means one flip is 4 points.

## Files
- `scripts/score_predictions.py` metrics, confusion matrix, flips (works on any two JSONL files)
- `references/eval_design.md` set design, metrics, honesty checklist
