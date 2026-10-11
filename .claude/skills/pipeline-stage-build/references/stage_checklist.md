# Stage build checklist

Each stage is ONE script in `pipeline/` named `N_name.py` (`1_clean.py`, `2_companies.py`,
`3_signals.py`, `4_score.py`). It reads the previous layer's file and writes its own.

## Before writing code
- [ ] The input layer has a contract in `context/contracts/` and passed `data-quality-check`.
- [ ] The output columns are written down (name, type, meaning) before the SQL is.
- [ ] The grain is stated in one line ("one row per company"). Joins must not change the grain.

## While writing
- [ ] Deterministic SQL/DuckDB only. No LLM calls in pipeline stages.
- [ ] Every function has a one-line docstring (enforced by hook).
- [ ] Constants (paths, thresholds, denylists) at the top of the file, not buried in SQL.
- [ ] Dev default is the 100K sample; `--full` is explicit.
- [ ] Never write into `data/raw/`.

## After running
- [ ] Stage report printed (`scripts/stage_report.py`): rows, null rates, 5 random rows.
- [ ] Row count compared to the previous layer and any difference explained.
- [ ] Join fan-out checked: if a join was used, output rows must equal the expected grain.
- [ ] Look at the 5 random rows with your own eyes. Do they make sense to a salesperson?
- [ ] Bugs found go to `docs/ISSUES.md` (symptom, root cause, fix, contract rule).
- [ ] Hand to `data-quality-check`. The author does not validate their own stage.

## Common traps for this project
- Cloud, CDN and ISP names becoming "companies" (denylist leakage).
- Name variants splitting one company into several (case, punctuation, "Inc"/"Ltd").
- Joins on non-unique keys multiplying rows.
- Aggregating before filtering, hiding the sample bias.
