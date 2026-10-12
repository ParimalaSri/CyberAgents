# Final2 G1: suites from the committed code (branch feat/qa/m2-final2 at 10e75fa)

| Suite | Result | Runtime | Output lines |
|---|---|---|---|
| scripts.test_1_clean | 27 OK | 8.2 s | 5 |
| scripts.test_2_companies | 32 OK | 5.1 s | 5 |
| scripts.test_3_signals | 40 OK | 11.4 s | 5 |
| scripts.test_4_score | 82 OK | 25.8 s | 5 |
| scripts.test_path_guard | 19 OK | 0.4 s | 5 |
| Subtotal (matches the reported 200) | 200 OK | | |
| scripts/test_denylist_match.py | 217 passed | <1 s | 1 |
| .claude/hooks/test_protect_files.py | 20/20 | ~1 s | 1 |
| data-quality-check discover | 62 OK | 55.4 s | 5 |
| python -O test_2_companies / 3_signals / 4_score / path_guard | 32 / 40 / 82 / 19 OK | 5.2 / 11.1 / 25.0 / 0.4 s | 5 each |

Noise: 5 lines per unittest module (Ran N / OK), no report tables. `git status` after all runs: only the pre-existing `.claude/agents/senior-data-engineer.md`; no file created in the repo.
Stray file: I did not look in D:/Cyber_DataSet. The tests use scratch stand-ins (earlier finding), so the result does not depend on it; per the task the file is present and the suites passed regardless (not independently observed by me).
