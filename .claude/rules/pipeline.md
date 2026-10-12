---
paths:
  - "pipeline/**"
  - "context/contracts/**"
  - "outputs/dq/**"
  - "docs/ISSUES.md"
---

# Architecture
- **Rules first.** Scoring, banding, filtering and entity grouping are deterministic code (SQL/DuckDB/Python). The LLM is not used here.
- Every account must have a `why` explanation a salesperson can read directly.
- Prefer precision over recall when grouping rows into companies. Report the unresolved percentage openly. Do not hide it.

# Data and pipeline
- Develop on a SAMPLE (100K rows) first. Run the full dataset only after the sample output has been checked.
- After EVERY stage print: row count, null rates for key columns, and 5 random sample rows. Compare row count to the previous layer and explain differences.
- A pipeline that runs without errors can still be wrong. Verify outputs.
- Each stage is ONE script. It reads the previous stage's file and writes its own. If a stage is wrong, rerun that stage only.

# Data quality
- Every layer has a contract in `context/contracts/<layer>.yml` (columns, types, key uniqueness, allowed ranges). `data-quality-check` runs against it.
- Always check: `companies <= hosts`; signals row count equals companies row count (join fan-out); no hyperscaler, CDN or ISP names as companies (denylist leakage); scores within 0 to 100; every account has a band and a non-empty `why`.
- Every bug found goes into `docs/ISSUES.md` with symptom, root cause, fix, and the contract rule that now catches it.
- Quality reports are saved to `outputs/dq/<layer>_<date>.md`.
