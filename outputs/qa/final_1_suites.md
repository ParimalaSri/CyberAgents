# Final F1: test suites from the committed code (05eeb10), and whether a test can write into the real protected folders

## Counts, runtime, noise, flakiness

| Suite (command as given) | Tests | Result run 1 | Result run 2 | Runtime (s) run 1 / run 2 | Lines printed |
|---|---|---|---|---|---|
| `python -m unittest scripts.test_1_clean scripts.test_2_companies scripts.test_3_signals scripts.test_4_score scripts.test_path_guard` | 153 (27 + 20 + 30 + 65 + 11) | OK | OK | 30.2 / 56.7 (run 2 overlapped my other jobs) | 5 |
| `python scripts/test_denylist_match.py` | 217 cases | all passed | all passed | under 1 | 1 |
| `python .claude/hooks/test_protect_files.py` | 20 | 20/20 | 20/20 | about 2 | 1 |
| `python -m unittest discover -s .claude/skills/data-quality-check/scripts -p "test_*.py"` | 62 | OK | not repeated (88 s) | 88.0 | 4 |

Per suite, run alone (seconds; lines printed): test_1_clean 27 tests, 9 s, 5 lines; test_2_companies 20 tests, 4 s, 5 lines; test_3_signals 30 tests, 9 s, 5 lines; test_4_score 65 tests, 20 s, 5 lines; test_path_guard 11 tests, 0.3 s, 5 lines. Noise target met: every stage suite prints exactly the 5 lines of unittest (dots, rule, Ran, blank, OK); stage 2 no longer prints its 126-line report (finding 10 fixed for stage 2). The expected count of 153 matches exactly.

Flakiness: the five stage suites ran three times in total (combined twice, each suite once alone), all green; the sandbox baseline (a fourth copy of the same code) was also 153 OK. No flaky test seen. Runtime varies with machine load (30 s vs 57 s combined).

The stray file `D:/Cyber_DataSet/qa_guard_test.parquet`: I did NOT look at that folder (rule). The main session says it is still present; these runs were green with it present, which is expected because no committed test refers to the real dataset folder (see below).

## Can any test or module write into the real `data/raw` or the dataset folder?

Answer: no, with the evidence below. Not by construction of the targets, and a broken guard does not change that.

1. Static: `grep -n "Cyber_DataSet" scripts/test_*.py` hits only `scripts/test_path_guard.py`, in `test_real_defaults_by_string_only` (calls `forbidden_reason(str)` only, no write) and `test_constants_and_no_switch` (compares the constant). `test_no_test_module_writes_to_the_dataset_folder` additionally fails any line that combines the folder name with a write, `--out`, `--report`, `run_cli`, `run_main`, `.main(`, `subprocess`, `shutil`, `unlink` and so on (it is a regex scan, a tripwire, not a proof, but it covers the pattern that caused the incident).
2. Every write target in the refusal tests comes from `scripts/guard_test_support.py`: `scratch_protected()` makes a `tempfile.TemporaryDirectory()` with `ds_scratch` and `raw_scratch`, loads a FRESH copy of the guard and patches that copy's `DATASET_DIR` and `RAW_DIR` to the scratch folders. `forbidden_targets()` returns paths built only from `scratch.root`, `scratch.raw`, `scratch.dataset`. `run_main()` patches `stage.load_guard` to return the scratch guard, so the stage under test consults the scratch guard (the real module object is never mutated). The four stage-level refusal tests (`test_output_under_raw_or_dataset_folder_refused` in test_1 to test_4) all call `assert_stage_refuses`, which passes only these targets, plus `--report` targets from the same set and a `safe` path in a temp dir; they assert the exit value is a refusal string, that `scratch_files()` is empty, and that the safe output or report was not created. Inputs and outputs of the other tests are in `tempfile` dirs.
3. `test_path_guard.RealFoldersNotTouchedTests` and a module cleanup snapshot the real `data/raw` (names and mtime) and fail if it changes. They do not watch the dataset folder (cannot, by rule), which is acceptable because of point 2.
4. Dynamic, with deliberately broken guards in a SANDBOX COPY (scratchpad `fm/sbx`, both protected-folder constants patched into the scratchpad and verified by importing the mutated module and asserting both lie inside the scratchpad, before every run; the sandbox also had every literal `Cyber_DataSet` in the Python files rewritten to the scratch folder, 0 mentions left):
   - B1, `forbidden_reason` always returns None: 153 tests ran, 9 failed (the four stage refusal tests, `test_data_raw_outside_the_repo_refused`, `test_links_into_protected_folders_refused`, `test_real_defaults_by_string_only`, `test_scratch_forms_refused`, `test_sample_builder_refuses_protected_output`). Files left in the two sandbox protected folders afterwards: none.
   - B2, `check_output_path` never exits: 6 failures (four stage refusal tests, `test_scratch_forms_refused`, the sample builder test). Files left in the sandbox protected folders: none.
   - The real `data/raw` listing (names, sizes, mtimes) was identical before and after the broken-guard runs.
   The failed assertions are inside temp dirs that the tests delete; the sandbox protected folders stayed empty, which shows the tests never aim at the module-level constants at all.
5. Residual risks (not safety holes in the tests): (a) `test_path_guard` real-constant checks (`test_real_defaults_by_string_only`) call the guard with strings that name the real dataset folder; the guard does a path lookup (realpath) on them, no write. (b) A new test written later that uses the real constant would not be stopped except by the regex tripwire.

Verdict F1: PASS. All suites green at the expected counts with the stray file present, quiet, repeatable; no test or module can reach the real protected folders, including with a broken guard.
