# Backlog

Source of truth for what is done and what is next. Milestones are copied from `docs/ARCHITECTURE.md` section 13.
Dependent milestones (M1 to M4) run one at a time. Update the status column when a quality gate returns PASS.

Status key: `done`, `in progress`, `next`, `blocked`, `not started`.

| M | milestone | owner agent | skills | quality gate (PASS/FAIL by) | status |
|---|---|---|---|---|---|
| M0 | Context, profile, decisions, scaffolding | `data-integrator`, `senior-data-engineer`, owner | `data-profiling`, `architecture-review` | owner approval of D1-D4 | in progress |
| M1 | Bronze to silver (`1_clean`, `2_companies`) | `data-engineer` | `pipeline-stage-build`, `entity-resolution`, `data-contract` | `data-quality-engineer` PASS on `hosts`, `companies` (sample) | not started |
| M2 | Gold signals and scores (`3_signals`, `4_score`) | `data-engineer`, `data-analyst` (to create) | `signal-engineering`, `scoring-calibration`, `account-scoring`, `data-contract` | `data-quality-engineer` PASS; owner approves signals and thresholds | not started |
| M3 | LLM layer (`llm/client.py`, adjudication, drafting) | `llm-engineer` | `account-scoring`, `prompt-version`, `outreach-draft`, `email-writing` | `qa-engineer` PASS; security clean | not started |
| M4 | Evals and cost | `qa-engineer`, owner (labels), `senior-data-engineer` | `eval-run`, `cost-report`, `prompt-version` | `qa-engineer` PASS; owner signs labels | not started |
| M5 | App and hosting | `app-developer` (to create), `sales-team` | `frontend-design` | smoke test PASS; security clean | not started |
| M6 | Docs, release, reflection | `tech-writer` (to create), `release-engineer` (to create) | `how-i-build-log`, `pr-review` | dev-to-prod gate; human merges | not started |

## M0 detail

Done:
- 100K head-of-file sample profiled (`outputs/profile_sample_100k.md`), raw schema drafted (`context/schema.md`), issues RAW-001..009 logged.
- Decisions D1-D4 recorded in `docs/ARCHITECTURE.md` and **approved by the owner**.
- Medallion architecture and planning docs written.
- 17 skills, 7 agents, hooks and permissions built and pushed to `main`.
- Owner decisions approved: spread sample in gitignored `data/sample/`; sample from the decompressed `.json` (after a match check against the `.zst`); serving extract on `prod` under `outputs/` (security-reviewed); dev LLM ceiling small with k = 2; redacted trace sample committed under `outputs/`; `final_band` column and noise-company rule settled at M2; `security-reviewer` agent created.

Open:
- [ ] `business.md` and `icp.md`: drafts written, **owner fills the `[OWNER]` blanks**.
- [ ] Denylist fixes: prefix families, cloud/CDN-tag rule, fix `ace`, move CIDR/pattern entries out, cert-default list (`data-integrator`).
- [ ] Spread sample builder in `scripts/`, sample in `data/sample/`, re-profile (expect about 86% denylisted, port 12304 about 2%) (`data-integrator`).
- [ ] Confirm the `.zst` and `.json` have identical content.
- [ ] PR template and CODEOWNERS in `.github/`.
- [ ] Merge the architecture and context branches into `dev` (human).

## Known blockers and risks
- Recall is capped: about 10% of rows can become companies; vulnerable estates sit mostly on denylisted hosts.
- No time signal in the data (about one hour of scanning).
- Brief's snapshot (2026-10-08) differs from the local file (2026-09-14).
- Pandas is blocked by a Windows policy on the dev machine (Streamlit tables may fail locally).
- Hosted app data path: small extract on `prod` (decided), needs a security review.
