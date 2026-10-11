# Eval design

## The set
- 20 to 30 accounts from the REVIEW band (that is where the LLM decides), labelled by the user.
- Cover the hard cases on purpose: borderline scores, thin data, big-but-quiet companies,
  small-but-exposed ones. Include some clear contact and clear skip as sanity anchors.
- One row per account: `account_id`, input signals, `label` (`contact` or `skip`), `label_notes`
  (why, in a sentence). Claude may add `suggested_label` with reasoning; the user sets `label`.

## Metrics
- Positive class = `contact`. Precision: of accounts the model sends to sales, how many are
  truly worth contacting. Recall: of the truly worth-contacting, how many did we catch.
- For sales, precision usually matters more (wasted calls cost trust); say which you optimise.
- Compare against two baselines: the previous prompt version and "rules only" (what the
  score alone would decide). If the LLM does not beat rules-only, say so.

## Honesty checklist
- Small n: 25 examples give wide error bars (one flip moves precision by ~4 points). Report counts.
- Overfit: do not edit a prompt to fix specific eval examples and then quote the same set.
  Keep 5 to 8 examples as a hold-out for the final prompt.
- Label noise: if the user hesitated on a label, record it in `label_notes`.
- Report weaknesses: which accounts fail, what they have in common, what you would do next.

## Output
Each run saves `evals/results/<timestamp>_<prompt>_vs_<baseline>.json` containing the metrics,
the per-example predictions, the prompt versions, model, and the run cost from the trace log.
