# Rerun R4: determinism and idempotence on the real sample

Stage copies re-synced from the repo (c64550e) first. Each stage was run from the copy into a scratch folder (`scratchpad/real/`), reading the real inputs read-only (`data/sample/spread_100k.jsonl`, stored silver and gold files); `data/` was not overwritten. Because outputs are not the default path, the stage reports went next to the scratch output (the new `--report` rule), so no committed report was touched.

| Stage | Rows scratch | Rows stored | Rows only in scratch / only in stored (EXCEPT ALL) | Same columns | Ordered SHA-256 equal | Hash (first 12) | Runtime |
|---|---|---|---|---|---|---|---|
| 1 clean (`spread_100k.jsonl`) | 97,758 | 97,758 | 0 / 0 | yes | yes | 26fe9df918c2 | 5.0 s |
| 2 companies | 5,790 | 5,790 | 0 / 0 | yes | yes | fd890827f2a1 | 0.5 s |
| 3 signals | 5,790 | 5,790 | 0 / 0 | yes | yes | 9fa3ee4eb25b | 0.4 s |
| 4 score | 5,790 | 5,790 | 0 / 0 | yes | yes | d16611b87bdb | 2.1 s |
| 1 clean, input lines shuffled (seed 7) | 97,758 | 97,758 | 0 / 0 | yes | yes | 26fe9df918c2 | 6.5 s |
| 1 clean, second plain run (idempotence) | 97,758 | 97,758 | 0 / 0 | yes | yes | 26fe9df918c2 | about 5 s |

Result: PASS. All stages reproduce the stored files exactly (identical hashes to the previous run's 97,758 / 5,790 / 5,790 / 5,790 rows), so the finding-1 tie-break change and the other fixes did not change the real-sample output. The sample has 1,098 hosts rows with `dup_count` above 1 (max 20), so the dedupe path is exercised and still order-independent on a shuffled input.

Not covered here: stored files were produced by the pre-fix code, so "identical" also shows the fixes leave the sample output unchanged; it does not exercise the latent full-dataset tie case (covered synthetically by E08 and N16).
