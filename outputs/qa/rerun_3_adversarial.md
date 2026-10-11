# Rerun R3: adversarial cases

Stage copies re-synced from the repo before the run (committed code at c64550e). Harnesses `adv.py`, `adv2.py` (old cases) and `adv3.py` (new cases) ran on synthetic data in the scratch root; `data/`, `D:/Cyber_DataSet/` and the repo `outputs/dq/` were not touched (git status clean apart from the unrelated agent file; no `qa_probe*` file in the dataset folder).

## Old cases (rerun)

| Case | What | Before | Now | Note |
|---|---|---|---|---|
| E01 | empty input file | FAIL | PASS | 0 rows in all 4 layers, exit 0 |
| E01b, E01c, E01d | empty hosts / companies / signals into stages 2, 3, 4 (adv2) | FAIL | PASS | stage 2 rc 0; stage 3 empty/empty rc 0; stage 4 empty rc 0, output written; stage 1 empty writes hosts |
| E02 | single row | PASS | PASS | |
| E03 | all noise | FAIL | PASS | 5 hosts, 0 companies |
| E04 | all infrastructure | FAIL | PASS | 5 hosts, 0 companies |
| E05 | null, empty, blank orgs | FAIL | PASS | 3 hosts, 0 companies |
| E06 | unicode orgs | PASS | PASS | 6 companies, accent spellings merged |
| E06b | unicode org, default Windows pipe encoding | FAIL | PASS | stage 1 writes and prints without UnicodeEncodeError |
| E07 | 10k and 100k character names | PASS | PASS | |
| E08 | tie differing only in vulns/hostnames, 6 shuffles | FAIL | PASS | 1 distinct output (was 2) |
| E09 | tie differing in a hashed column | PASS | PASS | 1 distinct |
| E10, E11 | IPv6, missing columns | PASS | PASS | |
| E12 | 5000 CVEs, null CVSS | printed FAIL | PASS by my reading | The harness check (adv.py:195) indexes the hosts rows `h[1]` as the NullCvss company, but `ORDER BY org` puts EmptyVuln second. Observed values are right: BigVuln (50, 5.5, no KEV), EmptyVuln (0, None, no KEV), NullCvss (2, None, KEV true). The data-engineer's "harness quirk" is CONFIRMED. |
| E13 | cert date edges 1989/1990/2100/2101/garbage/0001/9999 | PASS | PASS | |
| E14 | all-CDN cert_o company | PASS | PASS | |
| E15 | rounding grid 101x101 | PASS | PASS | 10,201 points, 245 exact ties, 0 mismatches |
| E16 to E18 | 5-way tie at cut, review-n larger, review-n 0 | PASS | PASS | |
| E19 | review-n -5 | PASS (assert) | PASS | now `parser.error`, rc 2, message "--review-n (-5) must not be negative" |
| E20 | contact < review | PASS | PASS | rc 2, clean message |
| E21 | threshold edges | PASS | PASS | |
| E22 | exclude rule 3 of 4 vs 1 of 3 | PASS | PASS | |
| E23 | stage 3 and 4 on empty companies / signals derived from a normal run | PASS or n/a | FAIL on purpose | stage 3 given EMPTY companies and NON-EMPTY hosts stops with `AssertionError: sum(counted_host_count) != counted member host rows`, rc 1. The input is inconsistent (hosts with no companies), so a loud stop is right: CONFIRMED as the data-engineer says. Two small notes: it is a raw traceback, not a clean message; the output file is already written when the assertion fires (N13c). Stage 4 on empty signals: rc 0. The consistent empty/empty case passes (E01c). |

Counts: 28 old rows (24 in `adv.py` plus 4 in `adv2.py`); 27 PASS, 1 intended failure (E23, inconsistent input). The 9 rows that FAILED before (E01, E01b, E01c, E01d, E03, E04, E05, E06b, E08) are all PASS now.

## New cases (20 rows, all on the changed code)

| # | Case | Expected | Observed | Result |
|---|---|---|---|---|
| N01 | `--report` WITH `--output`, stages 2 to 4 | report at the given path; no report next to the output | 3 of 3 wrote the report at the given path; none next to the output | PASS |
| N02 | `--report` WITHOUT `--output` (stage 2, defaults inside the scratch root) | default output written, report at the given path only, default report untouched | as expected | PASS |
| N02b | no `--output`, no `--report` | `outputs/dq/companies_stage_<date>.md` | that file | PASS |
| N03 | `--output` only | report next to the output | `companies_stage_report.md` next to the output | PASS |
| N05 | `--output data/raw/x` relative (cwd = root), stages 1 to 4 | refused, no file | 4 of 4 rc 1 with "refusing"; no file | PASS |
| N06 | `--output data/silver/../raw/x` | refused | 4 of 4 | PASS |
| N07 | `--output DATA/RAW/x` upper case | refused | 4 of 4 | PASS |
| N08 | `--output D:/Cyber_DataSet/qa_probe.parquet` | refused | 4 of 4 refused; no file in the dataset folder | PASS |
| N09 | `--report data/raw/x.md` (stages 2 to 4) | refused, output not written | 3 of 3 refused; output not written | PASS |
| N10 | `--review` equal to `--contact` | rc 2 | rc 2 "--review (40) must be below --contact (40)" | PASS |
| N11 | `--review-n` 1, would-be count, count+1, 0 (5 accounts at score 8) | contact X=9: review 1, 5, 5, 0; X=8: all 5 held in review at n=1, 5, 6 | (9,1)=1 (9,5)=5 (9,6)=5 (9,0)=0 (8,1)=5 (8,5)=5 (8,6)=5 | PASS |
| N12 | non-integer args: `abc`, `4.5`, empty string, `1e2`, missing value, `--contact -1` | rc 2 argparse error | all rc 2 with a clean message; `--review-n 99999999999999999999` rc 0 (accepted, behaves as "all above the floor") | PASS (Info on the huge value) |
| N13 | empty raw through stages 1 to 4 | 0 rows each | [0, 0, 0, 0] | PASS |
| N13b | zero-row companies and zero-row hosts into stage 3 | rc 0, 0 rows | rc 0, 0 rows | PASS |
| N13c | zero-row companies, non-empty hosts into stage 3 | loud failure | rc 1 AssertionError; output file left on disk | PASS (note) |
| N14 | one company with 1,000 hosts, 3 input orders | 1 account, host_count 1000, identical | ('Thousand Hosts Corp', 1000, 'skip', 9); identical over 3 orders | PASS |
| N15 | org names `!!!`, `---`, `...`, `()` | no empty-name company | 4 hosts classified `null_org`, 1 company (Real Name Corp) | PASS |
| N16 | two rows, same keys, timestamps, kept columns, differing in raw vulns payload only (derived values equal, and derived values different), 6 shuffles | 1 output | 1 distinct output in both variants | PASS |
| N17 | raw JSON with unknown extra fields | ignored | 2 hosts, 1 company, 1 account | PASS |
| N18 | hosts parquet with two extra columns into stages 2 and 3 | same as without | signals identical | PASS |

Counts: 20 of 20 PASS (my first N01 run showed FAIL because the harness left reports from the base chain in the same folder; rerun on a cleaned folder is PASS and the cause is the harness, not the code).

No crash, silent wrong result or non-determinism found in the new cases.

## Observations, not failures
- N13c: when stage 3 stops on its consistency assertion the parquet output is already on disk (`3_signals.py` writes before the check). A reader of that file after a failed run would see a file for an inconsistent input. Low; suggest asserting before the write or deleting the output on failure.
- Stage 2 `--report` and the guard check order: the guard runs after `choose_report_path` but before any write (confirmed by N05 to N09: no file or output appeared).
