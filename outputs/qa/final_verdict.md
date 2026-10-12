FAIL

# QA final verdict: M2 stages 1 to 4 after commits 2e2a1ff, 55f4fee, 85bae1b, 05eeb10 (branch `feat/qa/m2-final` from `feat/data-engineer/qa-rerun-fixes` at 05eeb10; reviewer `qa-engineer`)

Supersedes `rerun_verdict.md` (left intact). Rule set by the task: PASS only if F1, F2 and F4 have no FAIL and F3 has no surviving mutant on safety-critical code.

| Step | Result | File |
|---|---|---|
| F1 suites | PASS: 153 + 217 + 20 + 62 tests green, quiet (5 lines per stage suite), repeatable; no test can write into the real protected folders, also with a broken guard | `final_1_suites.md` |
| F2 guard | FAIL: 26 of 26 old cases pass (row 18 judged: the old expectation was wrong); of 79 new rows, 60 PASS, 2 PASS (crash, no write), 8 info, 2 not run (symlinks need privilege), 7 FAIL | `final_2_guard.md` |
| F3 mutation | FAIL (rule): 54 of 67 killed (80.6%); all 7 old survivors and all 18 earlier new survivors killed; 13 survivors among the 38 new mutants, all on safety-critical code (the new consistency checks, one guard branch) | `final_3_mutation.md` |
| F4 determinism | PASS: stages 1 to 4 identical to the stored files (97,758 / 5,790 / 5,790 / 5,790 rows; EXCEPT ALL both ways 0, positional mismatches 0, ordered md5 equal), and stage 1 on a shuffled copy identical | `final_4_determinism.md` |
| F5 findings | all of 1 to 10 fixed except finding 8 (partly); N1 partly, N2 fixed, N3 fixed for tested cases, N4 fixed, N5 not fixed; new NF-1 to NF-5 | `final_5_findings.md` |

## Why FAIL
1. F2, guard (Low severity, deliberate-crafting only): the guard still allows paths that reach the protected folders in six more spellings. Reproduction strings (`forbidden_reason` returns None for each; on a scratch analog each wrote a file or a stream):
   - `\\?\GLOBALROOT\Device\HarddiskVolume5\Cyber_DataSet\x.parquet`
   - `\\?\Volume{fcf459af-bb60-412a-960c-6979b1cc2127}\Cyber_DataSet\x.parquet`
   - `\??\D:\Cyber_DataSet\x`
   - `\\192.168.1.7\D$\Cyber_DataSet\x` (own LAN IP) and `\\0-0-0-0-0-0-0-1.ipv6-literal.net\D$\Cyber_DataSet\x`
   - `D:/Cyber_DataSet:evil` and `D:/CyberAgents/data/raw:evil` (alternate data stream on the folder itself)
   The data/raw side is held by the "any data then raw parts" clause except for the stream case. The family is open-ended; spelling-by-spelling stripping will not close it. Recommended fix in `final_2_guard.md` section 3 (plain-drive-paths-only rule, or file identity check).
2. F3, tests (Medium): 13 mutants survive, on exactly the code the rule names. The consistency checks added in 2e2a1ff to 05eeb10 are each tested for one failing input per stage; removing any other check (stage 2 infra_reason, companies > hosts, member-sum; stage 3 fan-out, host_count reconciliation; stage 4 NULL why, contact floor, score range, `final_band <> band`, decision/prompt_version) leaves every test green, and the guard's own-host-name UNC branch is untested. The bare post-write `assert`s still exist, so a missing pre-write check only turns into a traceback after the parquet is written.

The dedupe tie-break, which is the third safety-critical item, has no surviving mutant (M21, M32, P22 to P26 killed) and is deterministic on the real sample.

## What is good (so the senior reviewer does not have to re-derive it)
Everything the previous rerun asked for was done: tests use scratch stand-ins (the stray-file failure mode is gone, proved with broken guards in a sandbox), quiet suites, report path next to a scratch output, every earlier survivor killed, drive-relative case understood, the stored layers reproduce exactly.

## Conditions that apply to any later PASS
1. NOT VERIFIED: "no script reads the environment file". The guardrail hook blocks a search containing the file name; owner decides.
2. Hook and settings findings 11 to 14 sit with the owner (restated in `final_5_findings.md`); not re-tested; the fix commits did not touch hooks.
3. The stray file `D:/Cyber_DataSet/qa_guard_test.parquet` (created by my earlier mutation run) is the owner's to delete; I did not look at, touch or delete anything in that folder in this run.
4. The full dataset was not run (stage 1 `--full`, memory, runtime, tie behaviour at scale).

## Mutation kill rate
54 of 67 killed (80.6%); 52 of 65 excluding the two deliberately broken guards (80.0%). By group: old survivors 7 of 7; dedupe 2 of 2; earlier new set 18 of 18; new set 25 of 38 (65.8%); broken guards 2 of 2.

## What I did NOT verify
- The environment-file search (see above).
- Hooks and settings (findings 11 to 14).
- The full dataset.
- Symlinks to protected folders (`mklink /D` needs a privilege; only junctions and a junction chain were tested).
- Whether the six open spellings are writable on the REAL folders: proved only on scratch analogs on C: (the real device name `\Device\HarddiskVolume5` and the volume GUID were read with QueryDosDevice and GetVolumeNameForVolumeMountPoint; the guard was shown to allow the strings; no write was attempted). Whether `\\<LAN IP>\D$` works here depends on admin shares being reachable (it did on C$).
- The real D: drive has no 8.3 short names (GetShortPathNameW returned the long name), so no short-name alias exists there; on the analog the guard handled short names.
- Per-drive cwd inherited by a child process (the stages spawn none for writes).
- DuckDB handling of the exotic spellings (a Python `open` oracle was used; DuckDB was checked only for drive-relative `C:sub/a.parquet`).
- Whether D:\Cyber_DataSet still holds the stray file and whether anything else changed there: not looked at (main session snapshots).
- Mutants were run on a sandbox where the dataset-folder literals are replaced by a scratch folder, so the tests ran against the analog.
- No LLM code exists: no LLM behaviour verdict, no evals. Weights, bands and denylist accuracy are provisional and not judged.

## No harness wrote outside the scratchpad (exact commands that could have)
- Repo test suites (F1) run in `D:\CyberAgents`: tests write only inside `tempfile` folders (asserted by the suites; `git status` clean afterwards except my `outputs/qa` files).
- F2 oracle (`pg2/final_pg.py`): writes only inside `scratchpad/pg2/an` (verified by an assert before any write, which checks the analog paths resolve inside the scratchpad). Real-constant cases are `forbidden_reason(string)` only. `pg/pg_break_final.py` calls `forbidden_reason` only (the `mklink` lines were removed; it follows two pre-existing junctions through `realpath`, a lookup).
- F3: mutated files only in `scratchpad/fm/sbx`; constants verified inside the scratchpad before every mutant; the sandbox protected folders stayed empty; `D:/CyberAgents/data/raw` listing identical before and after the broken-guard run.
- F4: `--output` into `scratchpad/f4/` only; the shuffled 1 GB copy was created and deleted in the scratchpad.
- Queries that touched the dataset folder metadata: the guard's `realpath` on strings naming it, `GetShortPathNameW("D:/Cyber_DataSet")` and the two junction lookups (read-only).
- Files written in the repo: `outputs/qa/final_*.md` only.

## Recommendation to the senior reviewer
Do not approve yet. The code and tests are much better than at the last rerun, and the data is reproducible, but two items remain on the rule's own safety list. Ask the data-engineer for (a) a guard rule that does not enumerate spellings (plain drive paths only, or file identity), with the six strings above as tests on the scratch analog, and (b) one test per consistency check, including exit code 1 and no output file. Then I rerun F2 and F3 (about 25 minutes). The owner decides separately on the stray file, the environment-file search and findings 11 to 14.
