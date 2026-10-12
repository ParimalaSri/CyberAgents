# Final2 G4: determinism and idempotence on the real sample (committed code 10e75fa)

Method: stages 1 to 4 run from the working tree (pipeline files identical to commit 10e75fa; `git status` showed only the unrelated agent file and my own `outputs/qa` files) with `--output` into the scratchpad (`scratchpad/g4/run1/`). Nothing was written under `data/`, `outputs/dq/` or the dataset folder; the stage reports landed next to the scratch outputs. Compared with the stored `data/silver` and `data/gold` files three ways: `EXCEPT ALL` both directions, positional compare of row text, and an ORDERED hash `md5(string_agg(CAST(row AS VARCHAR), chr(10) ORDER BY CAST(row AS VARCHAR)))` (explicit ORDER BY over the full row text). Script: `scratchpad/g4/g4.py`.

| Stage | Rows new / stored | In new, not stored | In stored, not new | Positional mismatches | Ordered md5 (new = stored) | Result |
|---|---|---|---|---|---|---|
| 1 hosts | 97,758 / 97,758 | 0 | 0 | 0 | `8dbd47c2a1521049fabf8a429228a12f` | IDENTICAL |
| 2 companies | 5,790 / 5,790 | 0 | 0 | 0 | `39e6656ea0613811d3585570a835ec24` | IDENTICAL |
| 3 signals | 5,790 / 5,790 | 0 | 0 | 0 | `5b6df167911d0ceb8a226fab0b495786` | IDENTICAL |
| 4 accounts | 5,790 / 5,790 | 0 | 0 | 0 | `dea217763e9d54f0fbd65df7ee336e31` | IDENTICAL |
| 1 hosts from a line-shuffled copy (100,000 lines, seed 20261012) | 97,758 / 97,758 | 0 | 0 | 0 | `8dbd47c2a1521049fabf8a429228a12f` | IDENTICAL |

Runtime and stdout lines (stage reports, by design): stage 1 10.2 s / 56 lines, stage 2 0.7 s / 160, stage 3 0.6 s / 121, stage 4 4.5 s / 223. The hashes are identical to the previous final run (05eeb10), so the new pre-write checks and the allowlist did not change any output.

## Legit and refused `--output` through each stage's CLI
- Legit: all four stages wrote their scratch `--output` (scratchpad) and the report beside it (above).
- Refused (run on a SANDBOX copy of the committed code where both protected-folder constants point into the scratchpad, verified before the run; the copy was `scratchpad/g4/cli`): for each of stages 1 to 4, `--output` = `data/raw/x.parquet`, `<fake dataset folder>/x.parquet`, `//localhost/C$/x.parquet`, `data/raw:evil` gave exit code 1 and the refusal text (16 of 16 refused; no file created in the sandbox raw or fake dataset folders). The stage CLIs were NOT aimed at the real folders.

Result: PASS. Not proved: determinism at 10x scale (full file not run).
