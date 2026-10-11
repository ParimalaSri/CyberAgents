---
name: architecture-review
description: Review the design and a PR against the project's architecture rules - rules-first vs LLM split, all LLM calls through llm/client.py, prompts as files, cost ceiling, tracing, one script per stage - and recommend approve or request changes. Use when asked to review architecture, check a PR for design problems, or write docs/ARCHITECTURE.md.
argument-hint: [pr-number | path | "docs"]
version: 1.0.0
---

# architecture-review

Arguments: `$ARGUMENTS`

## When to use
- The `senior-data-engineer` reviewing a PR; before dev to prod; writing or updating `docs/ARCHITECTURE.md`.
- NOT for data correctness (`data-quality-check`) or LLM output quality (`eval-run`).

## Inputs
- The diff (`git diff dev...HEAD`) or the named files; `CLAUDE.md`; `docs/ARCHITECTURE.md`

## Steps
1. Mechanical checks (grep the diff, do not trust memory):
   - API calls only in `llm/client.py` (no `import anthropic` elsewhere)
   - No prompt text inline in code; prompts are `prompts/<feature>/vN.md`, old versions untouched
   - Pipeline stages are deterministic: no LLM imports in `pipeline/`
   - One script per stage; reads previous layer, writes its own
   - Cost ceiling enforced in `llm/client.py`; every call traced with the required fields
   - No `.env`, `data/`, `traces/` in the diff; nothing writes to `data/raw/`
2. Design checks:
   - Rule-vs-LLM split: is every LLM use justified (ambiguous review band, or text generation)? Could a rule do it?
   - Cheapest model that passes evals; cost math shown, not asserted
   - Every account has a salesperson-readable `why`
   - Failure behaviour: invalid JSON -> retry once -> `needs_human`; ceiling hit -> abort
   - Dev vs prod separation (sample vs full, trace files per environment)
3. Docs check: is each design decision and trade-off written in `docs/ARCHITECTURE.md`
   (what was chosen, what was rejected, why)? Add missing entries as short decision records:
   `Context | Decision | Alternatives considered | Consequences`.
4. Return a recommendation: APPROVE or CHANGES REQUESTED, with a numbered list of findings,
   each tied to a file and a rule. Recommend only; a human merges.

## Outputs
A review comment (PASS/FAIL per area with evidence) and, when asked, updated
`docs/ARCHITECTURE.md` sections: data flow, rule-vs-LLM split, cost model, trade-offs, known weaknesses.

## Rules
- Reviewers do not fix what they review; the author fixes. Reviews cite evidence (file:line).
- Never approve your own change. Never merge.
- Be specific about weaknesses; the docs should state what you would flag to a teammate.

## Worked example
> `/architecture-review 12`

Finding 1 (FAIL): `pipeline/3_signals.py:41` imports `llm.client`, but stages must be
deterministic. Finding 2 (FAIL): prompt text is inline at `llm/adjudicate.py:18`; move to
`prompts/account_scoring/v2.md`. Recommendation: CHANGES REQUESTED. (Illustrative.)
