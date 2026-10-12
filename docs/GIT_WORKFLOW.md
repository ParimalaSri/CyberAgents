# Git workflow and access

```
prod   protected. Hosted app deploys from here. Merge only via PR from dev.
dev    protected. Integration and testing. Merge only via PR from feature branches.
feat/<role>/<task>   where work happens, always branched from dev.
```
- NEVER commit, push, merge or rebase on `dev` or `prod`. Work on a feature branch.
- Open PRs with `gh pr create --base dev` using the PR template.
- Required checks on a PR into `dev`: data-quality-engineer PASS (when pipeline or data is touched), qa-engineer PASS (when code or prompts are touched), security-reviewer clean, senior-data-engineer recommendation.
- Before dev to prod: data-quality-engineer PASS on the FULL dataset (not the sample), evals not regressed, cost within ceiling, docs updated.
- **AI agents open PRs and comment on them. A human merges**, especially into `prod`. Agents never merge their own or another agent's PR.
- No hotfixes straight to `prod`. Fixes go through `dev`.
- Environments: dev uses the 100K sample and a small cost ceiling; prod uses the full scored extract. Traces go to `traces/dev.jsonl` or `traces/prod.jsonl`.

| Role group | Feature branch | PR to dev | Merge | Edit .env |
|---|---|---|---|---|
| Junior and mid agents | yes (own branch) | yes | no | no |
| Reviewer agents (security, sales) | no | no | no | no |
| release-engineer | no | prepares dev to prod PR | no | no |
| senior-data-engineer | yes | yes | recommends only | no |
| Human owner (me) | yes | yes | yes | yes |
