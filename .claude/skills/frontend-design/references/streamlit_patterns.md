# Streamlit patterns for this app

## Data access
```python
import duckdb, streamlit as st

@st.cache_data(show_spinner=False)
def query(sql, params=()):
    """Run a read-only DuckDB query on the gold parquet files and cache the result."""
    return duckdb.connect().execute(sql, list(params)).df()
```
Push filters into SQL (`WHERE band IN (...) AND contact_score >= ?`) and `LIMIT` the table to
a few hundred rows. Never `SELECT *` the whole file into memory.

## Layout
- `st.set_page_config(layout="wide", page_title="CyberIntel")` first.
- Filters in `st.sidebar`; results in the main area; views in `st.tabs([...])`.
- Detail view: `st.session_state["selected_account"]`, set from the table selection
  (`st.dataframe(..., on_select="rerun", selection_mode="single-row")`).

## Tables
Use `st.dataframe(df, column_config={...})` for readable headers, `ProgressColumn` for scores
(0 to 100), and a text column for `why`. Hide ids the rep does not need.

## State and cost
- Anything that calls the LLM sits behind a button; cache results in `st.session_state` and
  show the model, prompt version and cost of the call under the text.
- Keep the per-session LLM budget visible and enforced by `llm/client.py`, not by the UI.

## Style
- One accent colour for the contact band; neutral for the rest. Do not rely on colour alone:
  show the band name as text.
- Short labels, sentence case, no jargon (say "Exposed hosts", not `exp_host_cnt`).
- Empty states say what to do ("No accounts match. Lower the minimum score.").

## Hosting (Streamlit Community Cloud, deploys from `prod`)
- Entry point `app/streamlit_app.py`; dependencies in `requirements.txt`.
- Secrets via Streamlit secrets, never committed. The hosted app reads a small scored extract,
  not raw data.
