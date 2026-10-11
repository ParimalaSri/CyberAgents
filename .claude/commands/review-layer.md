---
description: Independent data-quality review of one layer (hosts, companies, signals, accounts)
argument-hint: <hosts|companies|signals|accounts> [--full]
---

Review layer `$ARGUMENTS`.

1. Load the `data-quality-check` skill and run it for this layer against
   `context/contracts/<layer>.yml`, saving the report to `outputs/dq/`.
2. Return PASS or FAIL with evidence. Do not edit pipeline code. If this is not the layer's
   author reviewing their own work, say so; if it is, flag that an independent review is needed.
3. Log any bug found in `docs/ISSUES.md` (symptom, root cause, fix, contract rule).
