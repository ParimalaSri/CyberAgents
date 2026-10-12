# Step 7: LLM readiness (informational)

Plain statement: LLM behaviour does not exist yet, so none of it was tested. `llm/` is an empty folder, `prompts/account_scoring/` is empty, `evals/` contains only an empty `results/`, `traces/` is empty (and gitignored). The only LLM-related files that exist are skill helpers and references: `.claude/skills/eval-run/scripts/score_predictions.py` (metrics), `.claude/skills/prompt-version/scripts/prompt_tool.py` (list, new, diff), `.claude/skills/account-scoring/references/output_schema.json` and `why_style_guide.md`, `.claude/skills/cost-report/scripts/cost_report.py`, and the validators `outreach-draft/scripts/validate_draft.py` and `email-writing/scripts/lint_email.py`. BACKLOG.md marks M3 and M4 "not started".

## 7.1 What is missing before M3 and M4 can be tested

| Item | State | Needed for |
|---|---|---|
| `llm/client.py` | absent | the only API gateway (CLAUDE.md section 8); every acceptance test below |
| `llm/adjudicate.py` | absent | review-band verdicts |
| Prompt `prompts/account_scoring/v1.md` | absent (folder empty) | adjudication; must carry front matter (version, feature, parent, date, change) and the operator-or-organisation question first (D10, D11.2), the "version-matched, never vulnerable" wording (D11.3, RAW-006) and the hint-not-verdict handling of the operator clause (D12.4) |
| Prompt for drafting (`prompts/outreach/`) | absent | outreach |
| Trace writer and schema | specified in ARCHITECTURE.md 5.3 (11 required fields), not implemented; `traces/` empty | trace tests, cost report |
| Proposed extra trace fields (`run_id`, `attempt`, `status`, `feature`, `env`) | not agreed | separating retry cost from first-call cost; the ceiling test needs `run_id` |
| Cost ceiling | specified (5.2: check before each call, worst-case cost); no ceiling value set; BACKLOG lists "set dev and prod LLM ceilings" as an open owner item | ceiling-abort test; D11.2 bound `N <= ceiling / cost per call` |
| Price table | not present; `cost-report` fills it from current published pricing | cost assertions |
| Eval set `evals/labeled.jsonl` | absent; `evals/candidates.jsonl` absent; the review band now exists (step 4 reproduced it) so candidates can be drawn with `sample_review_band.py` | the owner must label 20 to 30 accounts; at least 8 operator and 8 organisation cases (D10); strata by `identity_source`, singleton, operator flag |
| `evals/run_eval.py` | absent (my writable path); `score_predictions.py` exists for the metric part | `python evals/run_eval.py --prompt v2 --baseline v1`; needs the client to produce predictions |
| Rules-only baseline | undefined threshold; D12 makes the review band a top-N list, so the baseline must be defined before looking at labels (single `contact_score` cut within the review band) | "does the LLM beat rules" |
| JSON schema | exists: `decision` in contact or skip, `confidence` 0 to 1, `why` at most 300 characters, no extra properties | validation test. Gap: the schema has no field for the operator-versus-organisation answer that D10 and D11.2 say the prompt asks first, so that question cannot be evaluated separately (Low) |
| API key handling | key read from the environment (ARCHITECTURE.md 5.1); not checked (the environment-file search was not done, see verdict) | leakage test |

Eval caveats to state in every future report: n = 20 to 30, so one flipped example moves precision or recall by 3 to 5 points; one labeller; the review band changes with N and the thresholds (re-draw after any recalibration); `sales-team` output is never ground truth.

## 7.2 Acceptance tests I will run on `llm/client.py` when it exists
All with a fake transport that replaces the HTTP layer (no real API call, no key) unless stated; tests live in `tests/` only if the owner approves that folder, otherwise as a scratch runner with results in `outputs/qa/`.

1. Single gateway: grep every `.py` and notebook for `anthropic`, `openai`, `api.anthropic`, `requests`, `httpx`, `urllib`; hits only in `llm/client.py`. (Step 2 baseline: zero hits today.)
2. No inline prompts: no multi-sentence instruction text, no `You are`, in `llm/*.py`, `pipeline/`, `app/`; the client builds requests only from `prompts/<feature>/vN.md` and variables.
3. JSON validation: valid response is accepted; each of these is rejected: not JSON, JSON with extra key, `decision` outside the enum, `confidence` 1.2, `why` of 301 characters, empty `why`, JSON wrapped in prose or a code fence (document the rule).
4. Retry once: first response invalid, second valid, call count is exactly 2 and the second request contains the validation error; first and second invalid gives `decision = needs_human` and exactly 2 calls (never 3); `final_band` stays `review`; the trace has two rows with `attempt` 1 and 2 and `status` `invalid_json`.
5. API error and timeout: bounded retries with backoff, counted against the ceiling, then `needs_human` with an error-status trace row; no infinite loop (assert a maximum call count).
6. Ceiling abort: with ceiling C and a fake price, the run aborts BEFORE the call whose worst-case cost would exceed C (checked with a ceiling of 0, exactly one call and one less than one call); earlier results and traces are kept; the exit is non-zero with a clear message; a retry counts toward the ceiling; the ceiling cannot be disabled by an environment variable or an argument of 0 or a negative number.
7. Trace fields: every call writes one JSON line to `traces/<env>.jsonl` with all 11 required fields and types (`timestamp` UTC ISO 8601, `request`, `response` raw before validation, `model` exact ID, `prompt_version`, `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, `decision`, `account_id`); `cost_usd` equals tokens times the price table; append-only (two runs do not truncate); `dev` writes `traces/dev.jsonl` and `prod` writes `traces/prod.jsonl`, never the other; the file is created if the folder does not exist.
8. No key leakage: run with a sentinel key value; assert the sentinel appears in no trace row, no log line, no exception message, no stdout and no `outputs/`; request headers are not stored in `request`.
9. Prompt files: `prompts/account_scoring/v1.md`, `v2.md` have the front matter, `parent` points to an existing file, no version is skipped or edited (compare to git history with `git log --follow` showing add-only), `prompt_version` in the trace equals the file's `version`; a request for a missing version fails loudly.
10. Cache and idempotence (the cache key of D9.6 item 6): rerunning adjudication with the same `account_id`, `prompt_version` and input hash makes zero API calls (fake transport counts them); changing the prompt version or any input signal triggers a call.
11. Scope: only `band = review` rows are sent; `exclude`, `skip` and `contact` rows never; the count of calls equals the number of review rows at most `REVIEW_N`; rules never promote an excluded or capped account except through the review path, and the `why` then names the cap (D9.6 item 6).
12. Model choice: Haiku-class model for adjudication, Sonnet-class for drafting, read from a config constant, not hard-coded in callers.
13. Content checks on outputs: the `why` never says "is vulnerable", "has been exploited" or a breach claim (D11.3); every signal it cites exists in the input account row; the clause on operator names is treated as a hint (the M3 prompt text is reviewed for this, D12.4).
14. Eval harness (my own `evals/run_eval.py`): reads labels, never writes them (assert file hash before and after); metrics equal `score_predictions.py` on a hand-computed toy example; confusion matrix, counts beside percentages, `needs_human` reported as coverage; flipped examples listed; saves a new file in `evals/results/` without overwriting; includes rules-only, all-skip and all-contact baselines; says plainly if the LLM does not beat rules-only; cost taken from the trace.
15. Real-call smoke test (only with the owner's approval and a tiny ceiling): 3 accounts, one trace row each, cost under the ceiling.

Status: not run (nothing to run).
