# The team (subagents)

The main Claude session is the orchestrator ("head of data"). It reads `CLAUDE.md`, picks the next task, and delegates to one agent at a time. Subagents cannot talk to each other. They hand work over through FILES (contracts, reports, PRs), and the main session routes between them. Each agent's full definition is in `.claude/agents/<name>.md`.

| Agent | Job | Level |
|---|---|---|
| `data-integrator` | Ingest raw data, profile it, document the schema | Junior |
| `data-engineer` | Build pipeline stages (clean, companies, signals, score) | Junior |
| `llm-engineer` | Prompts, `llm/client.py`, tracing, prompt versions, cost wrapper | Junior |
| `app-developer` | Streamlit UI (uses `frontend-design` skill) | Junior |
| `data-analyst` | Scoring calibration, band and segment analysis | Mid |
| `data-quality-engineer` | Owns data contracts, runs data checks, owns `docs/ISSUES.md` | Mid |
| `qa-engineer` | Unit tests, eval harness, regression runs. Tests code and LLM behaviour | Mid |
| `security-reviewer` | Scans PRs for secrets, committed data, unsafe prompts, PII. Read-only | Reviewer |
| `sales-team` | Simulated end user: usability feedback, outreach drafts. Not ground truth | Read-mostly |
| `release-engineer` | Prepares the dev to prod promotion checklist | Senior-controlled |
| `senior-data-engineer` | Reviews PRs, owns architecture and cost docs, recommends approve or changes | Senior |
| `tech-writer` | Docs, README, reflection draft | Junior |

Core set to build first: `data-engineer`, `llm-engineer`, `data-quality-engineer`, `qa-engineer`, `senior-data-engineer`, `sales-team`. Add the others only when a PR needs them.

## Ownership rules
- **Data correctness** belongs to `data-quality-engineer`. **Code and LLM behaviour** belongs to `qa-engineer`. **Design and merge recommendation** belongs to `senior-data-engineer`.
- The author of a change never validates it. Reviewers never fix what they review. They return PASS or FAIL with evidence.
- Reviewer agents are read-only on pipeline code. `data-quality-engineer` may write only to `context/contracts/`, `outputs/dq/`, `docs/ISSUES.md`, and its own check scripts.
- `sales-team` output is never used as eval ground truth.
- Do not run agents in parallel on dependent stages. Parallel is fine only for independent work (profiling column groups, docs while evals run).

## Skills
Each lives in `.claude/skills/<name>/SKILL.md`. Required: `data-profiling`, `pipeline-stage-build`, `data-quality-check`, `scoring-calibration`, `account-scoring`, `outreach-draft`. Later: `data-contract`, `eval-run`, `prompt-version`, `cost-report`, `entity-resolution`, `signal-engineering`, `architecture-review`. Skills may contain `references/` and `scripts/`. Only `SKILL.md` is mandatory.
