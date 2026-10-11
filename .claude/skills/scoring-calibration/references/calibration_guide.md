# Calibration guide

Goal: choose signal weights and band thresholds from THIS dataset's score distribution, then
document the reasoning in `docs/ARCHITECTURE.md`. Do not copy numbers from another project.

## Method
1. **Look at the distribution** (`scripts/score_distribution.py`). Is it spread, bunched near
   zero, or bimodal? Bunched scores mean the signals are too sparse or the weights too small.
2. **Set the contact band by capacity, not by taste.** How many accounts can a sales team work
   per week? The contact band should be about that size (for example the top 2 to 5%).
3. **Set the review band by LLM budget.** Review accounts cost money to adjudicate:
   `review_count x avg_tokens x price`. Pick a width whose cost fits the run ceiling.
4. **Check the edges by hand.** Read 10 accounts just above and just below each threshold.
   The boundary should feel like a real judgement call, not an obvious miss.
5. **Test sensitivity.** Move each threshold by +/-5 points: how many accounts change band?
   A threshold where thousands flip is unstable; prefer a flatter region.
6. **Check with labels.** When `evals/labeled.jsonl` exists, compute precision of the contact
   band against the user's labels. Do not tune on the same examples you report.
7. **Segment check.** Compare band shares across segments (size, industry, country). A band
   that is empty for one segment usually means a signal is biased.

## What to record in `docs/ARCHITECTURE.md`
- Signal list with weights and why each weight was chosen
- Distribution summary (quantiles) and the chosen thresholds
- Band sizes at the thresholds and the capacity/budget reasoning
- Sensitivity results (how many accounts move at +/-5)
- Known weaknesses (biased signals, thin segments)

## Warning signs
- Everything is in `review`: thresholds too tight, or signals too weak to separate accounts.
- Top 20 dominated by one signal: that weight is too large.
- Urgency and fit highly correlated: they may be measuring the same thing.
