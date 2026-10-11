# Step 1: test suites (branch feat/qa/m2-review, base 8b594cd)

| Suite | Command | Tests | Result | Runtime |
|---|---|---|---|---|
| Stage tests | `python -m unittest scripts.test_1_clean scripts.test_2_companies scripts.test_3_signals scripts.test_4_score` | 101 (17 + 13 + 22 + 49) | OK, 0 fail, 0 error, 0 skipped | 17.7 s |
| Denylist self-test | `python scripts/test_denylist_match.py` | 217 cases | all passed | 0.1 s |
| Hook tests | `python .claude/hooks/test_protect_files.py` | 20 cases | 20/20 passed | 1.0 s |
| DQ check scripts | `python -m unittest discover -s .claude/skills/data-quality-check/scripts -p "test_*.py"` | 62 (17 accounts, 7 companies, 11 signals, 27 contract/hosts) | OK | 56.8 s |

Total: 163 unittest tests + 217 + 20 self-test cases, all green.

Slow (over 30 s): only the DQ accounts-extra module in isolation (34 s, 17 tests, the injected-fault mutation test). The DQ suite as a whole is 57 s. No other test is over 30 s. No skipped tests (no `skip` decorators; output has 0 "skipped"). No flaky behaviour seen in 2 full runs of the stage suite (101/101 both times) and the DQ modules (run again individually, all OK).

Noise: `scripts.test_4_score` prints a markdown report table to stdout during the run (a test of the report writer); harmless but clutters CI logs (Low).

Dependence on `data/`: none of the 6 test files reads `data/silver`, `data/gold`, `data/raw` or `data/sample`. The only "data/..." strings are placeholder path literals inside the DQ tests (`SIGNALS_PLACEHOLDER`, `COMPANIES_PLACEHOLDER`, `HOSTS_PLACEHOLDER`) that are rewritten to temp files, and string cases in the hook test. All stage tests build synthetic JSONL/parquet in temp dirs. They DO read repo config: `context/contracts/*.yml` (DQ tests), and the denylist and cert-default files via `denylist_match` (stage 1/2/4 tests and denylist test, 217 cases check "" not in the real lists). So a change to the real denylist file can break tests (expected coupling, Info).
