---
name: email-writing
description: Write sales emails beyond the first touch - subject lines, a 3 to 4 step follow-up sequence, breakup emails, and replies to responses - in a calm, fact-grounded style, and lint them. Use when asked for follow-ups, a sequence, subject line options, a reply to a prospect, or to improve a draft email.
argument-hint: <account_id> [--kind first|followup|breakup|reply] [--sequence]
version: 1.0.0
---

# email-writing

Arguments: `$ARGUMENTS`

Scope: general email craft. The first-touch draft for a scored account is owned by
`outreach-draft` (same tone, same banned phrases); use this skill for everything around it.

## When to use
- Follow-ups, a full sequence, a breakup email, subject line options.
- Drafting a reply to a prospect's response, or tightening a draft the user wrote.
- NOT for choosing who to email (`account-scoring`).

## Inputs
- Account row and its signals (`.claude/skills/account-scoring/scripts/explain_account.py <id>`)
- The previous email(s) in the thread, if any
- `context/business.md` for what we sell and tone

## Steps
1. Pick the kind. For a sequence, follow `references/sequence_framework.md` (day, angle, word limit).
2. For subjects, write three candidates using `references/subject_lines.md`, then choose one.
3. For replies, match the situation in `references/reply_handling.md`.
4. Use only facts in the account data. Each email names the signals it uses.
5. Lint each email: `python .claude/skills/email-writing/scripts/lint_email.py email.json --kind followup`
   (`email.json` holds `{"subject": "...", "body": "..."}`). Fix FAIL items.
6. If LLM generation is used, call it through `llm/client.py` with a versioned prompt
   in `prompts/email_writing/vN.md`; never inline prompt text or call the API elsewhere.

## Outputs
For each email: `{"subject", "body", "signals_used", "kind", "day"}`. A sequence returns the
list in order. Drafts are suggestions; a human sends them.

## Rules
- Calm, specific, short. One call to action. No breach claims, no pressure, no invented facts.
- Opt-outs end the sequence. Hostile or legal replies are flagged `needs_human`.
- No exclamation marks, no all-caps words, at most one link.

## Worked example
> `/email-writing acct_00123 --sequence`

Returns four touches (day 0, 3, 7, 14): the observation, a second fact, an offer to share the
list, and a polite breakup; each passes `lint_email.py`. (Placeholder facts.)

## Files
- `scripts/lint_email.py` length, subject style, CTA count, banned phrases (shared list)
- `references/sequence_framework.md` cadence and angles
- `references/subject_lines.md` patterns to use and avoid
- `references/reply_handling.md` response playbook
