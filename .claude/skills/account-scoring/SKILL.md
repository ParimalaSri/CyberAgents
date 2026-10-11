---
name: account-scoring
description: Score and band accounts (contact / review / skip / exclude) with deterministic rules, then adjudicate the ambiguous review band with a cheap LLM and give every account a plain-English why. Use when asked to score, rank, band, re-score, explain an account, or prepare review-band examples for labelling.
argument-hint: [--sample] [--prompt vN] [--account-id ID]
version: 1.1.0
---

# account-scoring

Arguments: `$ARGUMENTS`

## When to use
- Rebuilding `data/gold/accounts.parquet` after signals or weights change.
- Explaining why one account landed in a band.
- Picking review-band accounts for the user to label (eval set).
- NOT for threshold tuning (`scoring-calibration`) or outreach (`outreach-draft`).

## Inputs
- `data/gold/signals.parquet` (schema in `context/schema.md`), `context/icp.md`
- Prompt `prompts/account_scoring/vN.md` (latest unless `--prompt`)
- Optional `--account-id`, `--sample` (dev on the 100K sample)

## Steps
1. **Rules first.** Run `python pipeline/4_score.py [--sample]`. Fit, urgency, contact score,
   band and rule-based `why` are deterministic. Check with `data-quality-check accounts`.
2. **LLM only for `review`.** Run `python llm/adjudicate.py --prompt vN [--sample]`. It calls the
   model through `llm/client.py` only (Haiku, per-run cost ceiling, trace to `traces/<env>.jsonl`).
3. Output must match `references/output_schema.json`. Invalid JSON: retry once, then
   `decision = needs_human`. Never guess.
4. `why` text follows `references/why_style_guide.md`.
5. To explain one account: `python .claude/skills/account-scoring/scripts/explain_account.py <id>`.
6. To prepare eval candidates:
   `python .claude/skills/account-scoring/scripts/sample_review_band.py data/gold/accounts.parquet --n 30`.
   This writes `evals/candidates.jsonl` with EMPTY labels. You may add `suggested_label` with
   reasoning; the user sets `label` and moves rows into `evals/labeled.jsonl` themselves.
7. After any prompt change, run the eval harness (`python evals/run_eval.py --prompt vN --baseline vM`).

## Outputs
`data/gold/accounts.parquet`: `account_id, company_name, fit_score, urgency_score, contact_score,
band, why, decision, prompt_version` (final column list is defined in `context/schema.md`).

LLM response (strict JSON): `{"decision": "contact|skip", "confidence": 0.0-1.0, "why": "..."}`

## Rules
- Rules score; the LLM judges only the ambiguous band. Do not send contact/skip accounts to the LLM.
- All model calls go through `llm/client.py`; prompts are files; new prompt = new version file.
- Never write labels. Never overwrite `evals/labeled.jsonl`.
- Abort if the run cost ceiling is reached.

## Worked example
> `/account-scoring --sample --prompt v2`

Rules band 100K sample hosts' companies: 3% contact, 20% review, 77% skip. Adjudication of the
review band: 14 -> contact, 41 -> skip, 2 -> needs_human. Example row:
`acct_00123 | review->contact | 0.78 | "14 internet-facing hosts on outdated OpenSSH, mid-size
fintech matching ICP segment 2."` (Numbers illustrative.)

## Files
- `scripts/explain_account.py` show one account's score row and signals
- `scripts/sample_review_band.py` draw label candidates (never labels them)
- `references/output_schema.json` LLM response contract
- `references/why_style_guide.md` how to write `why`
