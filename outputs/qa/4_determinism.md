# Step 4: determinism and idempotence on the real sample

Method: byte-identical copies of the four stage scripts (checked with `cmp` against `pipeline/`) run from a scratch root, so the stage reports and outputs went only to the scratchpad. Inputs under `data/` were read only; no `data/` file was written. Comparison: row counts, column names and types, `EXCEPT ALL` in both directions, and a SHA-256 over the rows in stored order (script: scratchpad `det.py`).

| Stage | Input (read-only) | Scratch output vs stored output | Rows | Rows only in scratch / only in stored | Ordered row hash equal | Run time |
|---|---|---|---|---|---|---|
| 1 `1_clean.py` | `data/sample/spread_100k.jsonl` (1,019,584,854 bytes) | `data/silver/hosts.parquet` | 97,758 vs 97,758 | 0 / 0 | yes (`26fe9df918c2`) | 11.5 s |
| 1 again, input LINES SHUFFLED (seed 7) | same file, shuffled copy in scratch | `data/silver/hosts.parquet` | 97,758 vs 97,758 | 0 / 0 | yes (same hash) | 13.5 s |
| 2 `2_companies.py` | `data/silver/hosts.parquet` | `data/silver/companies.parquet` | 5,790 vs 5,790 | 0 / 0 | yes (`fd890827f2a1`) | 0.6 s |
| 3 `3_signals.py` | `hosts.parquet` + `companies.parquet` | `data/gold/signals.parquet` | 5,790 vs 5,790 | 0 / 0 | yes (`9fa3ee4eb25b`) | 0.4 s |
| 4 `4_score.py` (default thresholds 40/20/200) | `data/gold/signals.parquet` | `data/gold/accounts.parquet` | 5,790 vs 5,790 | 0 / 0 | yes (`d16611b87bdb`) | 2.4 s |

Column names and types are the same in all five comparisons.

Findings:
- All four stages are deterministic and idempotent on the real sample, and the stored files were produced by the current code (no stale layer).
- Stage 1 is also invariant to input line order on the real sample (shuffled copy gives the same hash). So the dedupe tie-break defect R1 found with synthetic input in step 3 (E08, `1_clean.py:211`) has NOT shown up on this sample: it needs two rows with the same key and timestamp that differ only outside the hashed columns. It remains a latent risk for the full run (the full source was not tested here).
- Stage 1 on the full compressed source was not run (not needed for this step and the source is outside the repo).
- Side effect noted again (F-A): running a stage with a scratch `--output` from the repo would have overwritten `outputs/dq/<stage>_stage_<today>.md`; avoided by the scratch root.

Verdict for step 4: PASS (no difference).
