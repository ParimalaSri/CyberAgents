---
name: outreach-draft
description: Draft a short, calm, fact-grounded outreach email or LinkedIn message for a scored account in the contact band, and validate it before returning. Use when asked to write outreach, a first-touch email, or talking points for a specific account.
argument-hint: <account_id> [--channel email|linkedin] [--persona security|it|exec]
version: 1.1.0
---

# outreach-draft

Arguments: `$ARGUMENTS`

## When to use
- The user wants outreach for a specific account, normally `band = contact`.
- NOT for scoring (use `account-scoring`). For accounts outside `contact`, confirm with the user first.

## Inputs
- Account row from `data/gold/accounts.parquet` (incl. `why`) and its signals
- `context/business.md` (what we sell, tone) and `context/icp.md`
- Prompt `prompts/outreach/vN.md` (latest unless the user names one)
- Optional channel (default email) and persona

## Steps
1. Load the account (`.claude/skills/account-scoring/scripts/explain_account.py <id>` prints it).
   Choose its top one or two signals. Use ONLY values present in the data.
2. Read `references/tone_guide.md`; look at `references/example_drafts.md`.
3. Generate through `llm/client.py` with the versioned prompt (Sonnet). Never call the API elsewhere.
4. Save the draft JSON and the account row to files, then validate:
   `python .claude/skills/outreach-draft/scripts/validate_draft.py draft.json --account account.json`
5. On FAIL, regenerate once with the problems listed. Still failing: mark `needs_human`.
6. Return the draft plus `signals_used`, so a human can verify every claim against the data.

## Outputs
```json
{"subject": "...", "body": "<=120 words (email) / <=60 (linkedin)", "signals_used": ["col=value"], "channel": "email"}
```
Logged to `traces/<env>.jsonl` with `account_id` and `prompt_version`.

## Rules
- No breach claims, no fear-mongering, no invented facts, one call to action.
- Every claim traces to a `signals_used` entry that exists in the account data.
- Prompt text lives in `prompts/outreach/vN.md`; changes create a new version.
- Draft text is a suggestion; a human sends it.

## Worked example
> `/outreach-draft acct_00123 --channel email --persona security`

Returns the "Quick note on your public-facing SSH hosts" draft from `references/example_drafts.md`
(placeholder facts), validation PASS, `signals_used: ["exposed_hosts=14", "outdated_ssh=true"]`.

## Files
- `scripts/validate_draft.py` schema, length, banned phrases, grounding check
- `references/tone_guide.md` structure and tone rules
- `references/example_drafts.md` good and bad examples
- `references/banned_phrases.txt` phrases that fail validation (edit to personalise)
