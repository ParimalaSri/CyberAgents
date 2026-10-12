## What and why
<!-- One or two sentences. Link the milestone (M0-M6) in docs/BACKLOG.md. -->

## Layers / prompts touched
- [ ] bronze (`data/raw`, sample builder)  - [ ] silver  - [ ] gold  - [ ] `llm/`  - [ ] `prompts/`  - [ ] `evals/`  - [ ] `app/`  - [ ] docs only

## Required checks (state PASS / CLEAN / n/a with a link or evidence)
- [ ] `data-quality-engineer`: PASS (required if pipeline or data touched; report in `outputs/dq/`)
- [ ] `qa-engineer`: PASS (required if code or prompts touched; eval results in `evals/results/`)
- [ ] `security-reviewer`: CLEAN
- [ ] `senior-data-engineer`: recommendation (APPROVE / CHANGES REQUESTED)

## Evidence
- Row counts vs previous layer and any difference explained:
- Unresolved / infrastructure share (if grouping changed):
- Eval precision / recall vs previous prompt (if prompts changed):
- LLM cost of the test run and the cost ceiling:

## Checklist
- [ ] No `.env`, `data/`, `traces/` or `.claude/logs/` in the diff
- [ ] Nothing writes to `data/raw/`
- [ ] All LLM calls go through `llm/client.py`; no inline prompt text
- [ ] Every function has a one-line docstring
- [ ] `docs/ISSUES.md` updated for any bug found; contract rule added

## Known weaknesses
<!-- Be specific. What would you flag to a teammate? -->

> Agents open PRs and comment; a human merges. Never merge your own PR.
