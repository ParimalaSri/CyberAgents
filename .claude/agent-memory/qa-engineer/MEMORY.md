# qa-engineer memory (CyberIntel)

Curate this file: keep it under 150 lines. No data, secrets or trace content here.

## How to work
- You test code and LLM behaviour and return PASS or FAIL with evidence; you do NOT fix. Your ONLY writable path is `outputs/qa/` (prefix new rounds: `rerun_`, `final_`, `final2_`; never edit earlier files). Propose fixes as findings (severity, file:line, reproduction, owner).
- Read CLAUDE.md; grep `### D<n>` records instead of reading `docs/ARCHITECTURE.md` whole (about 1,300 lines). Small steps, write each result file as you go, commit at the end. Runs stall at about 10 minutes.
- Branch `feat/qa/<task>` from the current tip; explicit `git add outputs/qa`; trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; never push or merge; leave the owner's uncommitted `.claude/agents/senior-data-engineer.md` alone.
- No pandas. If a hook blocks a command, record BLOCKED, stop that step, continue; never rephrase to pass it. The hook blocks any command text that mentions the environment-file name, so the check "no script reads the environment file" is NOT VERIFIED until the owner decides (QA prototyped a narrower rule in `outputs/qa/6_hook_review.md` section 6.5).

## HARD SAFETY RULE (an incident happened)
- A QA mutation run once wrote `D:/Cyber_DataSet/qa_guard_test.parquet` into the protected dataset folder: the mutant disabled the guard while the code still pointed at the REAL folder. The owner still has to delete that file. NEVER run a mutant, harness or test that can write to `D:/Cyber_DataSet/` or the real `data/raw/`. Run mutants only on a SANDBOX COPY where BOTH protected constants are patched to scratch folders BEFORE any test runs; print the constants and assert they point inside the scratchpad for every mutant; otherwise record NOT RUN. Do not run `adv3.py`, `mut.py`, `mut3.py` unless rewritten to scratch targets. The main session snapshots the dataset folder before and after your run.
- Do not list, read, delete or modify anything in `D:/Cyber_DataSet/`.

## What the harnesses showed (history)
- Round 1 FAIL: dedupe tie-break non-deterministic when rows differed only in `vulns`/`hostnames` (case E08); zero-row inputs crashed after writing; stages overwrote the committed report; test gaps (band `>=` edge, cert year edges, literal pins) left 7 mutants alive. Fixed (PIPE-008..017).
- Round 2: guard did not refuse `\\?\` and UNC forms of the dataset folder; tests aimed real writes at protected folders (root cause of the stray file). Fixed by injectable constants and scratch-folder tests.
- Round 3 (final): guard enumerated spellings, 7 crafted strings slipped (GLOBALROOT, Volume{}, `\??\`, LAN-IP UNC, ipv6-literal UNC, `D:/folder:evil` streams); 13 mutants alive on untested pre-write consistency checks. The data-engineer replaced the guard with an ALLOWLIST and added one test per check (own sample 62/62 killed). YOUR PENDING WORK: rerun F2 (guard re-attack with 25 new cases) and F3 (mutation, sandbox only), then `final2_verdict.md`. Partial reports `final2_1_suites.md`, `final2_2_guard.md`, `final2_4_determinism.md` exist from a stopped run.
- Determinism: stages 1-4 on the real sample are identical on rerun (explicit ORDER BY over all columns in the hash; the data-engineer's earlier hash had none). Re-sync stage copies from the committed code before every rerun and say that you did.
- Mutation kill rates so far: 24/31 -> 32/32 on the originals; 49/62 overall on the second round; always classify survivors as safety-critical or equivalent.

## Hook review (informational, owner decides; findings 11-14)
- Grep/Glob are not in the PreToolUse matcher or deny rules (High). The secrets-file regex matches the name anywhere in a command (false positive) and misses real reads that do not name the file. Checks are case-sensitive and do not resolve `..`; the dataset folder has no hook protection; `branch_guard.py` blocks feature branch names containing `dev`/`prod`/`main` as a word; `--force-with-lease` coverage unverified.

## LLM readiness (M3/M4 not built)
- `llm/`, `prompts/`, `evals/` are empty. Acceptance tests to run on `llm/client.py` when it exists are listed in `outputs/qa/7_llm_readiness.md` (JSON validation, retry once then `needs_human`, ceiling abort, all trace fields, no key leakage into traces, prompt files versioned, no inline prompts). QA finding 17: `output_schema.json` has no field for the operator-vs-organisation answer that D10/D11.2 make the first question.
