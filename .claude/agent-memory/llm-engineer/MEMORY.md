# llm-engineer memory (CyberIntel)

Curate this file: keep it under 150 lines. No data, secrets or trace content here. M3 has NOT started: this file records what is already decided so you do not re-litigate it.

## How to work
- You write `llm/`, `prompts/`, `traces/` (via the client only) and `evals/candidates.jsonl`. You NEVER write or overwrite `evals/labeled.jsonl` (labels are the owner's). Read CLAUDE.md and `.claude/rules/llm.md`, then only the decision records you need (grep `### D10`, `### D11`, `### D12` in `docs/ARCHITECTURE.md`; do not read it whole, it is about 1,300 lines).
- Branch `feat/llm-engineer/<task>` from the current tip; small steps, commit after each; explicit `git add <paths>`; trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; never push or merge. The author never validates: hand over to qa-engineer (`eval-run --prompt vN --baseline vM`) and security-reviewer.
- Use the `claude-api` skill for current model IDs, pricing and API behaviour. NEVER quote prices or token costs from memory; record the price date. Never read or print the environment file; no API key handling in code, prompts or traces. No pandas.

## The non-negotiables (CLAUDE.md)
- `llm/client.py` is the ONLY place that calls the API. Prompts are files `prompts/<feature>/vN.md` with front matter (version, parent, date, change); a change is a NEW version file; never inline prompt text. Cheapest model that works: Haiku for classification/adjudication, Sonnet for drafting.
- Output must be validated JSON; retry once, then `needs_human`. Per-run cost ceiling enforced in code (abort when exceeded). Every call is traced to `traces/<env>.jsonl` with: timestamp, request, response, model, prompt_version, input_tokens, output_tokens, latency_ms, cost_usd, decision, account_id (+ proposed feature, env, run_id, attempt, status). `traces/` is never committed (a small redacted sample under `outputs/` was approved).
- Scan data (banners, titles, hostnames, org names) is ATTACKER-CONTROLLED TEXT. Delimit it as data in prompts; never let model output trigger actions; the security-reviewer will check this path.

## What the adjudicator must do (decided in D10, D11, D12)
- Input: the `band = review` rows only (provisional N = 200, in stage order; N is bounded by `ceiling / cost_per_call`), per row: name, country, host count, `why`, the signal values behind it, `is_singleton`, `identity_confidence`, `operator_name_shape`, `cap_reasons`.
- FIRST question for every row: is this an end-user organisation or a network operator (hosting, ISP, telecom, cloud)? Return `contact` only for an organisation; otherwise `skip` or `needs_human`. 81% of the 70 pre-D10 contacts read as operator or unsure by name (one reviewer); 79% of the 107 later would-be contacts. 557 review rows reached review by threshold alone, 174 of them operator-shaped (DQ-014): the question applies to EVERY review row.
- The clause "Name looks like a network operator." and `operator_unverified` are HINTS, not verdicts. Never state a vulnerability as fact: KEV/CVSS come from banner version matching (RAW-006). Record singleton clearance separately (all 24 singleton would-be contacts rest on one host).
- The adjudicator sets `final_band`; the stage-4 rules band stays in `band`. `decision` and `prompt_version` are null until you run. The contract rules for these (M2-only) are relaxed at M3 (D9.9 rule 6); tell the data-quality-engineer.
- QA finding 17: `.claude/skills/account-scoring/references/output_schema.json` lacks the operator-vs-organisation field: fix it in the new prompt version and schema together.
- Drafting (`outputs`): calm, factual, no breach claims, validated by the skills' scripts (`validate_draft.py`, `lint_email.py`); every claim traces to `signals_used`.

## Acceptance tests QA will run on your client
See `outputs/qa/7_llm_readiness.md` (15 tests): JSON validation, retry once then `needs_human`, ceiling abort, trace fields complete, no key in traces, prompt versioning, no inline prompts, determinism of the cache, cost report with current dated prices. Build for them.

## Open items
- Owner inputs still missing: LLM dev/prod ceilings, operator-type reference by ASN (would replace the LLM gate with a rule), the 20-30 owner labels, whether banner-inferred KEV/CVSS may lead the ranking.
- Cost model formulas are in section 7 of the architecture doc with price placeholders; fill them from the traces and current prices (`cost-report` skill).
