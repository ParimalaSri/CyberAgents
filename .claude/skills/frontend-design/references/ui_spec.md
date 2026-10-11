# UI spec: what a salesperson needs

Design for a rep with 10 minutes: they must see who to call first, why, and what to say.

## Views
1. **Ranked accounts** (home). Table sorted by `contact_score`, band badge, company, score,
   one-line `why`. Filters on the left: band (default contact + review), segment/size,
   country, minimum score, text search. Show the count: "412 accounts match".
2. **Account detail** (click a row). Header: company, band, scores. Then `why`, the signals
   that drove it with values, and the hosts behind them. Button: "Draft outreach" (uses
   `outreach-draft`, shows `signals_used` next to the text so each claim is checkable).
3. **How it works** (tab). Data flow, rule-vs-LLM split, eval results (precision/recall for
   the review band), cost to date and the cost ceiling. Graders read this; so do sceptical reps.
4. **Data quality** (tab, small). Unresolved share, row counts per layer, latest DQ verdict.

## Principles
- The answer first: the ranked list is visible without scrolling or clicking.
- Every number has a plain label; no raw column names in headers (use `column_config`).
- Show uncertainty honestly: `review`/`needs_human` accounts are labelled, not hidden.
- LLM text is marked as a draft; the human sends it.
- Fast: load parquet once (`st.cache_data`), query with DuckDB, never load the full dataset
  into a DataFrame unless it fits comfortably.
- Works with the hosted sample extract (prod uses the full scored extract, dev the sample).

## Done means
- `scripts/smoke_test_app.py` passes.
- Looked at in a browser: filters change results, the detail view opens, no console errors.
- No secrets or `.env` access in the app; API keys come from Streamlit secrets in hosting.
