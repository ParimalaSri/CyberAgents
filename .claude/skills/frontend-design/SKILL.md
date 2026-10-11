---
name: frontend-design
description: Design and build the Streamlit sales-intelligence UI (ranked accounts, filters, account detail with why, outreach draft panel, how-it-works and data-quality tabs) with a salesperson-first layout, and smoke-test it. Use when asked to build or change app/streamlit_app.py, improve the UI, or prepare the hosted demo.
argument-hint: [view-or-change-to-make]
version: 1.0.0
---

# frontend-design

Arguments: `$ARGUMENTS`

## When to use
- Creating or changing `app/streamlit_app.py` (the `app-developer` role).
- Usability changes from `sales-team` feedback; preparing the hosted demo.
- NOT for scoring logic (that lives in the pipeline, never in the UI).

## Inputs
- `data/gold/accounts.parquet` (+ `signals.parquet` for the detail view); a small scored
  extract when hosted
- `references/ui_spec.md` (views and principles), `references/streamlit_patterns.md`
- `context/business.md`, `context/icp.md` for wording

## Steps
1. Plan first: list the views to build or change from `references/ui_spec.md`. Show the plan.
2. Implement in `app/streamlit_app.py` (split into modules under `app/` only if it grows).
   Follow `references/streamlit_patterns.md`: cached DuckDB queries, filters in SQL, `LIMIT` rows.
3. LLM actions (outreach draft) call the existing skill/`llm/client.py` path; the UI never
   calls the API itself, and shows `signals_used`, model, prompt version and cost.
4. Smoke test: `python .claude/skills/frontend-design/scripts/smoke_test_app.py app/streamlit_app.py`.
5. Run it (`streamlit run app/streamlit_app.py`) and check in a browser: filters, detail view,
   empty state, no errors. Say plainly if you could not check visually.
6. Ask for `sales-team` feedback; treat it as usability input, never as ground truth.

## Outputs
- `app/streamlit_app.py` (and helpers under `app/`)
- Smoke test PASS plus a short note on what was and was not checked in a browser

## Rules
- Answer first: the ranked list is visible immediately; every account shows its `why`.
- No business logic in the UI; no API calls outside `llm/client.py`; no `.env` access.
- Plain-English labels, band shown as text not colour only, honest empty states.
- Hosted app reads a small scored extract, never `data/raw/`.

## Worked example
> `/frontend-design ranked accounts view with band and score filters`

Adds a sidebar (band, minimum score, search), a table of the top 300 matching accounts with
score bars and `why`, and a count line. Smoke test: 1 title, 1 dataframe, 3 widgets, PASS.
(Illustrative.)

## Files
- `scripts/smoke_test_app.py` headless render check using Streamlit's AppTest
- `references/ui_spec.md` views, principles, definition of done
- `references/streamlit_patterns.md` data access, layout, tables, state, hosting
