---
description: Build or rerun ONE pipeline stage on the sample, then check its layer against its contract
argument-hint: <1_clean|2_companies|3_signals|4_score> [--full]
---

Run pipeline stage `$ARGUMENTS`.

1. Load the `pipeline-stage-build` skill and follow it for this stage. Show the plan first.
2. Run the stage on the 100K sample unless `--full` was given (and only use `--full` if the
   sample output for this stage was already checked).
3. Then load the `data-quality-check` skill for the layer this stage produced and report
   PASS or FAIL with evidence.
4. Do not mark the stage done if the check fails. Show the error and root cause before fixing.
