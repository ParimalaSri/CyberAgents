# Final F3: mutation testing on a sandbox copy (code at commit 05eeb10)

## Safety method (read first)
- Nothing was mutated or run in the repo. `scratchpad/fm/build_sbx.py` extracts the COMMITTED code (`git archive HEAD pipeline scripts context .claude/skills`) into `scratchpad/fm/sbx`. In that copy: `RAW_DIR` is `<sandbox>/data/raw` (the guard derives it from its own location) and `DATASET_DIR` is patched to `scratchpad/fm/fake_ds/`. Every literal `Cyber_DataSet` in the sandbox Python files (path_guard, 1_clean `FULL_PATH`, test_path_guard strings) was rewritten to the scratch folder in the forward-slash, double-backslash and `D$` UNC spellings; 0 mentions remain, so no sandbox test or stage names the real dataset folder.
- Before EVERY mutant, `fm/verify_consts.py` imports the mutated guard from the sandbox and asserts both constants resolve inside the scratchpad (it exits with a SAFETY STOP otherwise); the check passed on every mutant run (the runner stops the whole run otherwise) with `DATASET_DIR = .../scratchpad/fm/fake_ds/` and `RAW_DIR = .../scratchpad/fm/sbx/data/raw`. After every mutant the runner lists files in the two sandbox protected folders: none, ever. The old harnesses (`mut.py`, `mut3.py`, `adv3.py`) were NOT run.
- Baseline on the sandbox before mutating: 153 of 153 OK.
- Caveat: the sandbox tests exercise the analog folder, not the real one. Test results are the same code paths; the real-constant checks differ only in the folder string.
- Each mutant: guard-file mutants run `test_path_guard` first, stage-file mutants run their own suite first; a survivor is re-run against all five suites. KILLED means at least one test failed or errored.

## Result
| Set | Mutants | Killed | Survived | Kill rate |
|---|---|---|---|---|
| Old survivors to re-check (M01, M07, M11, M12, M22, M23, M24) | 7 | 7 | 0 | 100% |
| Dedupe tie-break (M21 drop, M32 narrow hash) | 2 | 2 | 0 | 100% |
| Previous new set re-check (P01 to P09, P12, P16, P17, P22 to P26, P30) | 18 | 18 | 0 | 100% |
| NEW on commits 2e2a1ff to 05eeb10 (N01 to N38) | 38 | 25 | 13 | 65.8% |
| Deliberately broken guards (B1, B2) | 2 | 2 | 0 | 100% |
| All | 67 | 54 | 13 | 80.6% |
| All excluding B1 and B2 | 65 | 52 | 13 | 80.0% |

Previous run: 49 of 62 (79.0%). The old weak spots (7 survivors, P02, P03, P12, P16, P17, P22 to P26, P30) are all killed now: the data-engineer's tests are good where I pointed. The new fix code (the consistency checks) has new gaps.

## Survivors (13), each with the reason
| # | Where | Mutant | Why it survives | Safety-critical? |
|---|---|---|---|---|
| N04 | `path_guard` | own host name no longer a "local host" | tests use `localhost`, `127.0.0.1` and the loopback forms only; no test builds `\\<this-machine>\D$\...` | yes (guard) |
| N14 | `2_companies.check_consistency` | infra_reason outside the contract set not refused | no test supplies such a value; the post-write bare `assert` in `print_report` still catches it, AFTER the file is written | yes (consistency check) |
| N15 | stage 2 | companies > hosts check removed | no test; same post-write assert backs it up (`assert n <= total`) | yes |
| N16 | stage 2 | sum(host_count) != member rows check removed | no test; post-write assert backs it up | yes |
| N36 | stage 2 | the N16 check prints instead of `sys.exit` (exit 0) | same missing test (an exit-code test exists only for the identity_source check) | yes |
| N17 | `3_signals.check_consistency` | fan-out/drop check removed | the stage 3 tests only trigger the counted-reconciliation message; no duplicate company_id case | yes |
| N28 | stage 3 | fan-out check prints instead of `sys.exit` | same missing test | yes |
| N19 | stage 3 | sum(host_count) != member host rows check removed | only the counted-host mismatch is tested (hosts with an empty companies file) | yes |
| N21 | `4_score.check_consistency` | empty-why check removed | test uses `why = ' '`, which the invariant query's `trim(why) = ''` clause also catches; a NULL why is caught by no other clause, so this is a real gap for NULL | yes |
| N23 | stage 4 | `FLOOR * urgency <= contact <= urgency` check removed | no test | yes |
| N24 | stage 4 | score range 0 to 100 clauses removed from the invariant query | no test; the post-write assert backs it up | yes |
| N37 | stage 4 | `final_band <> band` clause removed | no test | yes |
| N38 | stage 4 | `decision`/`prompt_version` must be NULL clause removed | no test | yes |

None is an equivalent mutant: each removes a check whose "nothing is written" guarantee is not tested, and the post-write asserts only turn a missing pre-write check into a traceback after the parquet is already on disk (the finding N3 behaviour). The 25 killed new mutants include the important ones: both guard-defaults mutants (N10, N11), UNC and extended prefix stripping (N01, N02, N03, N05, N12), trailing dot and space stripping (N07, N08, N09, N06 for `::$DATA`), the check-after-write ordering in stages 2, 3, 4 (N25, N26, N27: the `write_output` not-called guarantee for the tested cases), guard dropped in every stage and in the sample builder (N32 to N35, N31 for order), `--report` naming (N30) and `main(argv)` injection (N29).

## Safety-critical survivors: yes (guard N04; consistency checks N14 to N17, N19, N21, N23, N24, N28, N36 to N38; the dedupe tie-break has none)
Per the rule for PASS ("no surviving mutant on safety-critical code"), F3 fails. The fix is cheap: one test per check (`write_hosts`/`write_signals` with a crafted input, or the `damaged()` pattern already used in `test_4_score.test_check_consistency_exits_before_writing`, extended to all cases, plus `writer.assert_not_called()` and `exit code 1` per case).

## Full mutant list (latest status per id)
See `scratchpad/fm/final_last.json` (not committed). Order: M01 M07 M11 M12 M22 M23 M24 M21 M32 killed; P01 to P09, P12, P16, P17, P22 to P26, P30 killed; N01 to N03, N05 to N13, N18, N20, N22, N25 to N27, N29 to N35 killed; B1, B2 killed.
