# Backlog

Source of truth for what is done and what is next. Milestones are copied from `docs/ARCHITECTURE.md` section 13.
Dependent milestones (M1 to M4) run one at a time. Update the status column when a quality gate returns PASS.

Status key: `done`, `in progress`, `next`, `blocked`, `not started`.

| M | milestone | owner agent | skills | quality gate (PASS/FAIL by) | status |
|---|---|---|---|---|---|
| M0 | Context, profile, decisions, scaffolding | `data-integrator`, `senior-data-engineer`, owner | `data-profiling`, `architecture-review` | owner approval of D1-D4 | done except owner blanks in `business.md` / `icp.md` |
| M1 | Bronze to silver (`1_clean`, `2_companies`) | `data-engineer` | `pipeline-stage-build`, `entity-resolution`, `data-contract` | `data-quality-engineer` PASS on `hosts`, `companies` (sample) | done on the sample (2026-10-11): hosts 94/94, companies 61/61 at 6e2f136; senior engineer APPROVE; qa and security reviews still open |
| M2 | Gold signals and scores (`3_signals`, `4_score`) | `data-engineer`, `data-analyst` (to create) | `signal-engineering`, `scoring-calibration`, `account-scoring`, `data-contract` | `data-quality-engineer` PASS; owner approves signals and thresholds | in progress: D9 specification written (681a02b); build not started |
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
- D5 to D9 decided by `senior-data-engineer` under the owner's delegation (D9 = gold layer specification).
- Owner decisions approved: spread sample in gitignored `data/sample/`; sample from the decompressed `.json` (after a match check against the `.zst`); serving extract on `prod` under `outputs/` (security-reviewed); dev LLM ceiling small with k = 2; redacted trace sample committed under `outputs/`; `final_band` column and noise-company rule settled at M2; `security-reviewer` agent created.

Also done since:
- Spread sample (`data/sample/spread_100k.jsonl`) and re-profile; denylist split into exact, prefix, pattern, keyword (org-scoped), cert-default files with accent folding; D5 (isp text never excludes) decided by `senior-data-engineer` under the owner's delegation; contract checker applies the shared matcher (RAW-010 closed); PR template, CODEOWNERS, `security-reviewer` agent.

Open:
- [ ] Owner: fill the `[OWNER]` blanks in `context/business.md` and `context/icp.md` (product, price band, buyer titles, rep capacity, territories, competitors, industries, size, countries, named accounts, 3 to 5 example accounts, enrichment or not).
- [ ] Owner: approve or edit the D9.4 signal list and the provisional values (D9.7); decide the four band questions in D9 (operators, singleton cap, short list, territory); set dev and prod LLM ceilings; confirm D9.1 to D9.3.
- [ ] qa-engineer PASS and security-reviewer run on the branch stack (required before a PR to `dev`).
- [ ] Merge the stacked branches into `dev` (human). The stack is long; the diff against `dev` is about 125 files.
- [ ] data-engineer: `pipeline/1_clean.py --full` default output path would overwrite the sample `hosts.parquet` (D9.10 step 2).
- [ ] data-quality-engineer: close DQ-006/007/008 per D9; correct DQ-006 (`data room` is org plus org, not cross-source).
- [ ] data-analyst agent file (created in this branch); calibration at M2 after stage 4 exists.
- [ ] Whole-file match of the `.zst` and `.json` (only the first 512 MiB compared).
- [ ] Before `prod`: full-file run of stages 1 and 2 and full-file DQ PASS (contract paths and counts replaced), fresh top-50 operator read, evals not regressed, cost within ceiling.

## Known blockers and risks
- Recall is capped: about 13.6% of rows resolve to a company (sample); vulnerable estates sit mostly on denylisted hosts. 77.65% of companies have no urgency signal, so the `contact` band will be small.
- The `contact` band may be operator-heavy; the D7.2a trigger is expected to trip at calibration. The `skip` band mostly means unknown, not safe.
- Everything is validated on the 100K sample by name-only review (one reviewer); the full file has not been run.
- No time signal in the data (about one hour of scanning).
- Brief's snapshot (2026-10-08) differs from the local file (2026-09-14).
- Pandas is blocked by a Windows policy on the dev machine (Streamlit tables may fail locally).
- Hosted app data path: small extract on `prod` (decided), needs a security review.
