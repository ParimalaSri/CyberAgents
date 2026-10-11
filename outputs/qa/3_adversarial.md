# Step 3: adversarial and edge-case tests of the stages

Method: copies of `pipeline/`, `scripts/denylist_match.py`, `context/` and `.claude/skills/` under the scratchpad (`...\scratchpad\root`), so `ROOT` is scratch and reports go to scratch (see finding F-A in step 2). Synthetic JSONL in `...\scratchpad\work\<case>\`. Stages run as subprocesses with the real command-line options (`--input`, `--output`, `--hosts`, `--companies`, `--contact`, `--review`, `--review-n`). No pandas; DuckDB and plain Python. Nothing under `data/` was read or written.

Harness: `C:\Users\sikha\AppData\Local\Temp\claude\d--CyberAgents\b020cbda-a712-4cbf-a95c-f9fe15473fd9\scratchpad\adv.py` (run: `PYTHONIOENCODING=utf-8 python adv.py`), follow-ups in `adv2.py` next to it. (Scratch files do not carry docstrings; the lint hook complained about that, scratch is outside the repo.)

Result: 26 case rows, 17 PASS, 9 FAIL (E01, E01b, E01c, E01d, E03, E04, E05, E06b, E08); the 9 FAIL rows have 3 root causes (R1 to R3 below).

| ID | Case | Expected | Observed | Result |
|---|---|---|---|---|
| E01 | empty input file | no crash, 0 rows in all layers | stage 1 writes `hosts.parquet`, then crashes: `ZeroDivisionError` at the infrastructure share print (`1_clean.py` report, `100 * infra / total`), exit code 1 | FAIL |
| E01b | stage 2 on empty hosts parquet | no crash | `ZeroDivisionError` in the report, exit 1 | FAIL |
| E01c | stage 3 on empty hosts + empty companies | no crash | `AssertionError: sum(counted_host_count) != counted member host rows` (`sum()` of zero rows is NULL, never equal to 0) | FAIL |
| E01d | stage 4 on empty signals | no crash | accounts parquet written, then `TypeError: unsupported format string passed to NoneType.__format__` in `.claude/skills/scoring-calibration/scripts/score_distribution.py:23` (`mean:.2f` of NULL), exit 1 | FAIL |
| E02 | single row (RDP 3389) | 1 row each layer | 1/1/1/1; band skip, contact_score 8, why "Remote-admin or database services exposed (RDP 3389). Below the review cut-off." | PASS |
| E03 | all rows noise (honeypot tag) | no crash, 0 companies | stage 2 crashes: `AssertionError: sum(host_count) None != member rows 0` | FAIL |
| E04 | all rows infrastructure (Amazon org) | no crash, 0 companies | same stage 2 assertion | FAIL |
| E05 | null / empty / blank org, no cert | 3 hosts, 0 companies | same stage 2 assertion (zero members) | FAIL |
| E06 | unicode orgs: CJK, Cyrillic, combining accent, RTL Arabic, Latin diacritics | 6 companies, "Cafe\u0301" and "Café" merge | 6 companies; norms `cafe securite`, `zoe angstrom`, the CJK, Cyrillic and Arabic strings kept intact (lowercased Cyrillic) | PASS |
| E06b | same input, default Windows pipe encoding (cp1252, no PYTHONIOENCODING) | no crash | stage 1 writes `hosts.parquet`, then `UnicodeEncodeError: 'charmap' codec can't encode characters` when printing the 5 random sample rows; exit 1. Environment dependent (console or redirect encoding), but the project runs on Windows | FAIL |
| E07 | org of 10,000 and 100,000 characters | 2 accounts, no crash | 2/2/2/2 | PASS |
| E08 | duplicate key (ip, port, transport), identical timestamp, rows differ ONLY in non-hashed columns (vulns, hostnames); 6 input shuffles | identical output for any order | 2 distinct outputs over 6 shuffles: kept row is either `max_cvss 9.8, has_kev True, hostnames [a]` or `max_cvss 2.0, has_kev False, hostnames [b]` depending on input order. NON-DETERMINISTIC | FAIL |
| E09 | same, rows differ in `product` (a hashed column) | identical | 1 output over 6 shuffles (`nginx`, 9.8) | PASS |
| E10 | IPv6-only rows (no `ip_str`) | 2 hosts, 1 company | 1 company, `host_ip` = the IPv6 text, identity org | PASS |
| E11 | missing optional raw columns, port/transport null | 3 hosts, no crash | 3 hosts, 1 company | PASS |
| E12 | 5,000 CVEs with half null CVSS, null kev; all-null CVSS with one kev; empty map | vuln_count capped 50; max_cvss null when all null | BigVuln: vuln_count 50, max_cvss 5.5, has_kev False; NullCvss: vuln_count 2, max_cvss NULL, has_kev True, signals kev_exposed True, max_cvss_band 0; Empty: 0/NULL/False (the harness check indexed the wrong row; the values are correct) | PASS |
| E13 | cert expires 1989-12-31, 1990-01-01, 2100-12-31, 2101-01-01, "garbage", 0001, 9999 | outside 1990..2100 or unparseable becomes NULL + `cert_date_invalid` | edges 1990-01-01 and 2100-12-31 kept; the other five NULL and invalid | PASS |
| E14 | company whose 3 hosts are all CDN-tagged cert_o (with KEV, RDP, expired cert) | blind (counted 0); KEV and risky off | counted 0, `host_signals_blind` True, `kev_exposed` False, `risky_service_exposed` False, `cert_expired_or_soon` True (3 hosts). This matches ARCHITECTURE.md line 1052 (cert counts all member hosts) but means a "blind" account can still carry a cert urgency; Info | PASS (per spec) |
| E15 | contact_score arithmetic over the full 101 x 101 grid of (urgency, fit) | exact round-half-up of `u * (0.5 + 0.5 f/100)`, max 100 | 10,201 points, 245 exact .5 ties, 0 mismatches, max 100 | PASS |
| E16 | 5 identical-score accounts, `--review-n 3`, 4 input shuffles | the 3 smallest account_id kept, stable | bands by id order review, review, review, skip, skip; identical over 4 shuffles | PASS |
| E17 | `--review-n` 1,000,000 (larger than accounts) | all review | 5 of 5 review | PASS |
| E18 | `--review-n 0` | 0 review (no would-be contacts) | 0 review | PASS |
| E19 | `--review-n -5` | reject | `AssertionError: review_n must not be negative` (a bare assert with traceback, not an argparse error; stripped by `python -O`) | PASS (Low note) |
| E20 | `--contact 10 --review 50` | refuse or be consistent | `AssertionError: review threshold must be below the contact threshold` (`4_score.py:304`) | PASS (Low note) |
| E21 | thresholds 0/0, 100/100, 40/40 and 101/0 | refuse equal; accept 101/0 | the three equal pairs refused; 101/0 accepted | PASS |
| E22 | exclude rule: 3 noise of 4 hosts vs 1 noise of 3 | first excluded, second not | `Evil Net Corp` exclude, `Edge Net Corp` skip | PASS |

## Failures, root causes and reproductions

R1 (Medium) Non-deterministic dedupe tie-break. `pipeline/1_clean.py:211` orders ties by `hash(org, isp, product, version, shodan_module, cert_subject_o, cast(tags AS VARCHAR))`. Two raw rows with the same (host_ip, port, transport, timestamp) that differ only in a column outside that hash (vulns, hostnames, domains, ssl versions, cert dates, cpe, os, asn, country) tie, and `row_number()` then follows input order. Consequence: `max_cvss`, `has_kev`, `vuln_count` and urgency can change between runs of identical data. Reproduction: `PYTHONIOENCODING=utf-8 python <scratchpad>\adv.py` (case E08), or two JSON lines for `9.9.9.9:80` with the same timestamp and org, different `vulns`, fed in both orders to `python pipeline/1_clean.py --input f.jsonl --output o.parquet`. Suggested fix: add every kept column (or a hash of the whole raw row) to the tie-break. Owner: data-engineer. Step 4 measures whether the real sample is exposed.

R2 (Low/Medium) Zero-row batches crash the stages (E01, E01b, E01c, E01d, E03, E04, E05). Roots: `ZeroDivisionError` in the stage 1 and 2 reports (`100 * x / total`), `sum()` over zero rows returns NULL in the stage 2 assertion (`sum(host_count) None != member rows 0`) and the stage 3 assertion, and the stage 4 helper `score_distribution.py:23` formats a NULL mean. The output parquet is written first in every case (checked: `hosts`, `companies`, `signals0`, `a0` exist), and the crash happens in the report or assertion that follows, but the process exits 1, so any orchestration that checks the exit code stops. A real dev slice that happens to have no org-named companies (small sample, all noise) hits it. Reproduction: `python pipeline/1_clean.py --input empty.jsonl --output o.parquet` with an empty file; stage 2 with a hosts parquet that has only noise or infrastructure rows. Fix: `coalesce(sum(...), 0)` and guard the divisions (or print "n/a"). Owner: data-engineer (and the skill script owner for `score_distribution.py`).

R3 (Low) Stage 1 prints raw org text and crashes under a cp1252 stdout (E06b), after the output file is written. Fix: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` or print with `ascii()`. Owner: data-engineer.

R4 (Low) Threshold validation uses `assert` (E19, E20): fine for a dev tool, but not an argparse error, and removed with `python -O`. Info.

R5 (Info) E14: `cert_expired_or_soon` is true on a company with `host_signals_blind`; documented in ARCHITECTURE.md line 1052. Mentioned for the senior reviewer only.

No silent wrong result was found in the edge cases other than R1.
