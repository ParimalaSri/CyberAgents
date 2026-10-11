---
name: pr-review
description: Prepare and review a pull request into dev - work out which required checks apply from the changed files, flag forbidden files, draft the PR description, and write PASS/FAIL review comments with evidence. Use when opening a PR, asking what checks a change needs, or reviewing someone else's PR.
argument-hint: [open | review <pr-number>] [--base dev]
version: 1.0.0
---

# pr-review

Arguments: `$ARGUMENTS`

## When to use
- Opening a PR from a `feat/<role>/<task>` branch, or reviewing one. Also dev to prod preparation (`release-engineer`).
- NOT for merging: AI agents open PRs and comment; a human merges.

## Steps (open)
1. Confirm you are on a feature branch (not `main`, `dev`, `prod`) and the work is committed.
2. List changed files: `git diff --name-only dev...HEAD`. Block on forbidden paths:
   `.env`, `data/`, `traces/`, `.claude/logs/`.
3. Decide the required checks from the files:
   - touches `pipeline/`, `data/` contracts, `context/contracts/` -> `data-quality-check` PASS
   - touches code, `prompts/`, `llm/`, `evals/` -> qa-engineer PASS (`eval-run` if prompts changed)
   - always -> security-reviewer clean (secrets, committed data, unsafe prompts, PII)
   - always -> senior-data-engineer recommendation (`architecture-review`)
4. Draft the description: What changed and why; layers/prompts touched; checks run and results
   (with links to `outputs/dq/` reports and eval results); cost impact; known weaknesses.
5. Open it: `gh pr create --base dev --title "<short>" --body "<description>"`.

## Steps (review)
1. Read the diff and the PR description. Run the checks that apply; the author never validates their own change.
2. Comment one verdict per area: `PASS` or `FAIL` with evidence (file:line, counts, example rows).
3. Reviewers do not fix; the author does. Recommend approve or changes; do not merge.

## Dev to prod gate (human merges)
Full-dataset DQ PASS (not the sample), evals not regressed, cost within the ceiling, docs updated.
No hotfixes straight to `prod`: fixes go through `dev`.

## Outputs
A PR description, a checklist of required checks with status, and review comments.

## Rules
- Attribution lines per the repository's commit/PR conventions.
- Never merge, force-push, or push to `main`/`dev`/`prod` directly (hooks block it).
- Keep PRs small and single-purpose.

## Worked example
> `/pr-review open`

Changed: `pipeline/2_companies.py`, `context/contracts/companies.yml`. Required: DQ PASS,
QA PASS, security clean, senior recommendation. Description lists the unresolved share and the
row count change (100,000 hosts -> N companies) with the DQ report link. (Illustrative.)
