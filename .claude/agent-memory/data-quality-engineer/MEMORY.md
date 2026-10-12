# data-quality-engineer memory (CyberIntel)

Curate this file: keep it under 150 lines. No data, secrets or trace content here.

## How to work
- You decide data correctness. You write ONLY `context/contracts/`, `outputs/dq/`, `docs/ISSUES.md` and your own check scripts under `.claude/skills/data-quality-check/scripts/` (with tests and `references/`). You never fix pipeline code: return PASS or FAIL with evidence.
- Read CLAUDE.md, then only the decision records you need (grep `### D<n>` in `docs/ARCHITECTURE.md`; it is about 1,300 lines, never read it whole). Small steps, commit after each layer. Earlier long runs stalled at about 10 minutes.
- Branch `feat/data-quality/<task>` from the current tip; explicit `git add <paths>`; trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; never push or merge; leave the owner's uncommitted `.claude/agents/senior-data-engineer.md` alone.
- Never touch `data/raw/` or `D:/Cyber_DataSet/`; never read the environment file; if a hook blocks you stop and tell the owner. No pandas. Run mutation tests on COPIES (scratchpad) or synthetic layers only, never on `data/` files.

## How the checks are built
- Contract format: `context/contracts/<layer>.yml`; runner `check_contract.py <contract> --report` writes `outputs/dq/<layer>_<date>.md`. Current results (sample): hosts 94/94, companies 61/61, signals 127/127, accounts 90/90, plus `check_<layer>_extra.py` (independent recomputation, mutation tests).
- Denylist check: use `denylist: {column, rules: shared}` (imports `scripts/denylist_match.py`: exact, prefix, pattern, keyword, accent-folded, org text only). The old `{column, file}` form is exact-only.
- Write the independent recompute from the DECISION TEXT (D4/D6/D8/D9-D12) with its own constants, not from the stage SQL. It proves rules were applied, not that the rules or constants are right: say so in every report.
- Take ranges from MEANING, not from what the data holds. Contract constants that mirror provisional values (FLOOR 0.5, thresholds 40/20, REVIEW_N 200, territory 0) must be marked PROVISIONAL.
- The generic runner matches types by prefix (`INTEGER[]` passes an `INTEGER` rule, DQ-010): use exact-type checks for arrays.
- Mutation tests: inject at least 8-10 faults per layer on a synthetic layer (and a few on scratch copies of the real file); each must be caught by the detector named for it. Faults that are consistent between a flag and its count are caught only by the recompute, not by the contract.

## Pitfalls seen (do not repeat)
- Contract lag: after a stage change the contract and extra checks go stale (DQ-015/016/021: T2 regex, threshold-based band rules, skip wording). Always rerun ALL four layers after any stage or rule change and read the stage report's "expected failures" list.
- The raw row count constant (100,000) must change for a full run; `row_rule` cannot read JSONL so it is a custom check.
- The review band is a count-capped top-N, not a score threshold: ties pile up at 3, 20, 25, 30 (DQ-017). Tie-break order is pinned (D12.1).
- `cap_reasons` order is alphabetical (DQ-012). `why` safety checks: at most 40 words, no `=` or `_`, no breach words, no "located in", no "Exposure is limited".
- Operators dominate the top of the ranking (DQ-009, 20 of the top 25 read as operator or unsure by name; the name flag catches about a quarter). Operators that reach review by threshold alone (DQ-014) must be read by the M3 adjudicator.

## Open items
- No full-file PASS exists (not authorised for prod). DQ-022: the 40-word fallback drops the exposure sentence on 8 would-be contacts (6 in the top 25): awaiting the senior engineer.
- DQ-018/019 wording notes were applied under D12; DQ-020 (territory 0 points) is carried until the owner supplies a territory list.
