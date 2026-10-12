# Final F4: determinism and idempotence on the real sample (committed code 05eeb10)

Method: stages 1 to 4 run from the working tree (pipeline files identical to commit 05eeb10; `git status` showed only the unrelated agent file and my own outputs) with `--output` into the scratchpad (`scratchpad/f4/run1/`). Nothing was written under `data/`, `outputs/dq/` or the dataset folder; with a scratch `--output` the stage report lands next to the output (checked: `accounts_stage_report.md`, `companies_stage_report.md`, `signals_stage_report.md` are in the scratch folder). Comparison with the stored `data/silver` and `data/gold` files, three ways: (1) `EXCEPT ALL` in both directions, (2) positional compare of row text (row_number over the file order), (3) an ORDERED hash: `md5(string_agg(CAST(row AS VARCHAR), chr(10) ORDER BY CAST(row AS VARCHAR)))`, an explicit ORDER BY over the full row text (not the data-engineer's unordered string_agg). Script: `scratchpad/f4/f4.py`.

| Stage | Rows new / stored | In new, not stored | In stored, not new | Positional mismatches | Ordered md5 (new = stored) | Result |
|---|---|---|---|---|---|---|
| 1 hosts | 97,758 / 97,758 | 0 | 0 | 0 | `8dbd47c2a1521049fabf8a429228a12f` | IDENTICAL |
| 2 companies | 5,790 / 5,790 | 0 | 0 | 0 | `39e6656ea0613811d3585570a835ec24` | IDENTICAL |
| 3 signals | 5,790 / 5,790 | 0 | 0 | 0 | `5b6df167911d0ceb8a226fab0b495786` | IDENTICAL |
| 4 accounts | 5,790 / 5,790 | 0 | 0 | 0 | `dea217763e9d54f0fbd65df7ee336e31` | IDENTICAL |
| 1 hosts from a line-shuffled copy of the sample (100,000 lines, seed 20261012) | 97,758 / 97,758 | 0 | 0 | 0 | `8dbd47c2a1521049fabf8a429228a12f` | IDENTICAL |

Runtime and noise (stdout lines): stage 1 15.5 s, 56 lines; stage 2 0.8 s, 160 lines; stage 3 0.7 s, 121 lines; stage 4 4.0 s, 223 lines (these are the stage reports, by design; the noise requirement applies to the test suites, see F1).

Result: PASS. The stored layers are reproducible byte-for-byte in content and in row order from the committed code, and stage 1 is independent of the input line order (the dedupe tie-break fix holds on the real sample, which is where it matters). This does not prove determinism at 10x scale (full file not run).
