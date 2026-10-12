# Step 6: hook review (informational; no hook, setting or data file was edited)

Files read: `.claude/hooks/protect_files.py`, `branch_guard.py`, `_common.py`, `test_protect_files.py`, `.claude/settings.json`.

## 6.1 Existing test
`python .claude/hooks/test_protect_files.py`: 20/20 cases passed.

## 6.2 Extra events (45 crafted events fed as JSON on stdin to both hook scripts, as settings.json wires them)
Harness (scratchpad): `hook_run.py`; events about the secrets file are in `env_events.json` (written with the Write tool, so no shell command contained the text). The "commit on main" cases used a scratch git repository on branch `main` (scratchpad `gitmain`), never the project repo. Nothing was executed except the two hook scripts. The tool matcher of settings.json (`Read|Edit|Write|MultiEdit|NotebookEdit|Bash`) was applied.

Result: 24 of 45 behave as expected, 21 do not (listed). "Slips" = the hooks allow something that should be blocked; "false positive" = blocks something legitimate.

| ID | Event | Expected | Observed | Note |
|---|---|---|---|---|
| H01 | `cp a data/../data/raw/y` | block | blocked | pattern sees `data/raw` inside |
| H02 | `cd data && rm -rf raw/foo` | block | SLIPS | relative path after `cd` has no `data/raw` text |
| H03 | `rm data\raw\x.json` (backslashes) | block | blocked | backslashes are normalised |
| H04 | `git push --force origin feat/qa/x` | block | hooks allow | covered by deny rule `Bash(git push --force:*)` in settings.json |
| H05 | `git push origin main` | block | blocked | branch_guard |
| H06 | `git push origin HEAD:prod` | block | blocked | |
| H07 | `git commit` with the working directory on `main` | block | blocked | but see 6.3 item 9 (empty repo) |
| H08 | Write tool to `data/raw/x.txt` | block | blocked | |
| H09 | Write tool to `data\silver\..\raw\x.txt` | block | SLIPS | `in_raw_data` does not resolve `..` |
| H10 | Write tool to `D:/Cyber_DataSet/x.json` (source dataset) | block | SLIPS | only `data/raw/` is protected; CLAUDE.md also forbids touching `D:/Cyber_DataSet/` |
| H11 | `find data/raw -delete` | block | SLIPS | verb list is `rm, tee, truncate, touch, sed -i, dd of=, cp, mv` and redirects |
| H12 | `python -c "open('data/raw/x','w')..."` | block | SLIPS | interpreters are not inspected |
| H13 | Write tool to `DATA/RAW/x.txt` | block | SLIPS | case-sensitive match on a case-insensitive file system |
| H14 | `echo hi > data/raw/x` | block | blocked | |
| H15 | `git commit` on the feature branch | allow | allowed | |
| H16 | `git push -f origin feat/qa/x` | block | hooks allow | covered by deny rule `Bash(git push -f:*)` |
| H17 | `git push --force-with-lease origin feat/qa/x` | block | hooks allow | whether the deny prefix `git push --force` also matches `--force-with-lease` depends on the permission matcher; not verified |
| H18 | Edit tool with working directory on `main` | block | blocked | |
| H19 | `git reset --hard` on `main` | block | blocked | |
| H20 | `git push origin feat/qa/dev-tools` | allow | BLOCKED (false positive) | `PUSH_TARGET` uses `\b(main\|dev\|prod)\b`; `-` and `/` are word boundaries, so any branch name containing the word dev, prod or main is blocked |
| H21 | `cp data/raw/x.json /tmp/x.json` (read of raw) | allow | allowed | |
| H22 | `rm data/silver/old.parquet` | allow | allowed | |
| H23 | Write tool to `data/silver/x.txt` | allow | allowed | |
| H24 | `mv data/raw/a.json data/raw/b.json` | block | blocked | |
| H25 | `ln -s data/raw /tmp/lnk && echo 1 > /tmp/lnk/x` | block | SLIPS | links are not followed |
| H26 | `git push origin feat/x:refs/heads/main` | block | blocked | |
| V01 | Read tool on the secrets file | block | blocked | |
| V02 | Read tool on `.ENV` (upper case) | block | SLIPS | `is_env_file` compares case-sensitively; Windows is case-insensitive |
| V03 | Read tool on `data\..\<secrets file>` | block | blocked | only the basename is tested |
| V04 | Read tool on the `.example` file | allow | allowed | |
| V05 | Read tool on `<secrets file>.production` | block | blocked | |
| V06 | `cat <secrets file>` | block | blocked | |
| V07 | `grep -rn API_KEY .` (recursive search, no file name in the command) | block | SLIPS | the command never names the file, so a recursive grep prints its secret lines |
| V08 | `cat .en*` (glob) | block | SLIPS | |
| V09 | `cat .e""nv` (shell quoting) | block | SLIPS | |
| V10 | `python -c "print(open('.'+'env').read())"` | block | SLIPS | computed name |
| F01 | `grep -n "\.env" README.md` (pattern only) | allow | BLOCKED (false positive) | |
| F02 | `git commit -m "docs: say never commit .env"` | allow | BLOCKED (false positive) | |
| F03 | heredoc that writes a report mentioning the file | allow | BLOCKED (false positive) | the case I hit in this run |
| F04 | `echo "see .env handling"` | allow | BLOCKED (false positive) | |
| N01 | `ls prod.env` | allow | allowed | |
| N02 | `cat .envrc` | allow | allowed | |
| W01 | Write tool whose CONTENT mentions the file | allow | allowed | the hook only reads the path for file tools, so the same sentence is allowed in a Write but blocked in a heredoc |
| W02 | Write tool to the secrets file | block | blocked | |
| G01 | Grep tool with `path` = the secrets file | block | NOT HOOKED | see 6.3 item 1 |

## 6.3 Findings
1. (High, not executed; reasoned from the config) `settings.json` matcher for PreToolUse is `Read|Edit|Write|MultiEdit|NotebookEdit|Bash`. The Grep and Glob tools are not in it, and `protect_files.py` only reads `file_path` and `notebook_path`, not Grep's `path` or `glob`. The deny rules (`Read(./.env)` and so on) cover Read, Edit and Write only. So a Grep-tool call with `path` pointing at the secrets file and `output_mode: content` would print its lines. I did NOT run it (the owner has not approved any such search). Suggested fix: add `Grep|Glob` to the matcher and test `path` and `glob`; add `Grep(./.env)` style deny rules. Owner: owner (settings are protected).
2. (Medium) Case-insensitive file system: `.ENV` (V02) and `DATA/RAW` (H13) slip. Compare lowercased.
3. (Medium) `data/raw` check does not resolve `..` (H09), `cd`-relative paths (H02), links (H25), `find -delete` (H11) or interpreters (H12). Mitigation already in code: stage and sample scripts guard their own targets only in `build_spread_sample.py`; stages have none (step 2 F-B).
4. (Medium) `D:/Cyber_DataSet/` is not protected by any hook or deny rule (H10), although CLAUDE.md section 8 says never to modify it. Add it to `in_raw_data` and to the deny list (`Edit(D:/Cyber_DataSet/**)`, `Write(...)`).
5. (Medium, false positive) The secrets-file rule blocks any command whose text contains the name (F01 to F04). Characterisation from the source: `ENV_IN_COMMAND = (?<![\w.])\.env(?!\.example)(?![\w])` is applied to the whole command string, so the name is matched wherever it appears: in a grep pattern, a commit message, an echo, a comment, a heredoc body. The lookbehind exempts only names that follow a word character or a dot (`prod.env`), the lookahead only `.example` and word characters (`.envrc`). It never asks whether the command can actually read or write the file. This blocked my step 2 report (a heredoc) and would block any commit message that mentions the file. The same rule misses real access that does not name the file (V07, V08, V09, V10).
6. (Low, false positive) `PUSH_TARGET` blocks feature branches whose names contain dev, prod or main as a word (H20). Anchor to the refspec target: `(?:^|[\s:/])(?:refs/heads/)?(main|dev|prod)(?:\s|$)` after removing the source of a `src:dst` pair, or parse the push arguments.
7. (Low) Force push on a feature branch is not handled by the hooks; it relies on deny prefixes (`git push --force:*`, `git push -f:*`). A flag placed after the refspec (`git push origin feat/x --force`) or `--force-with-lease` may not match a prefix rule; not verified.
8. (Low) `write` hook inconsistency W01: file tools are checked by path only, Bash by text. Not a security hole, but it explains why the same sentence is allowed in one tool and blocked in the other.
9. (Low) `current_branch` returns an empty string when `git rev-parse --abbrev-ref HEAD` fails. In a repository with no commit yet (my first run of H07, H18, H19 before the scratch repo had a commit) every branch check is skipped: the three cases were all ALLOWED until I created a commit. A fresh clone is not affected, but an unborn branch is. Use `git symbolic-ref --short HEAD`.

## 6.4 What `.claude/settings.json` deny rules cover
`Read(./.env)`, `Read(./.env.*)`, `Edit(./.env)`, `Edit(./.env.*)`, `Write(./.env)`, `Write(./.env.*)`; `Edit(./data/raw/**)`, `Write(./data/raw/**)`; `Bash(git push --force:*)`, `Bash(git push -f:*)`. Not covered by deny rules: Bash writes to data/raw (hook only), `D:/Cyber_DataSet/`, MultiEdit and NotebookEdit on the protected paths, Grep and Glob on the secrets file, `git push --force-with-lease`.

## 6.5 Proposal for the owner (NOT applied): a narrower rule that still blocks reading or writing the file
Idea: stop regex-matching the name anywhere in the text; parse the command (heredoc bodies removed, quotes collapsed by `shlex`, split into simple commands) and block when the name (or a leading-dot glob that can expand to it) is an ARGUMENT or REDIRECT TARGET of a command that is not text-only. Exempt: the pattern operand of grep and rg, `git ... -m/--grep` values and `echo`/`printf` arguments. Add what the old rule misses: recursive grep or `rg --hidden` over a folder without an exclude, glob and quoting tricks. Fail closed when the command cannot be parsed. Limits: interpreter code (`python -c`, `bash -c`, command substitution inside an exempt `echo`) cannot be seen, so the Read deny rules and the file-tool path checks stay as they are.

Prototype (scratchpad `proto_rule.py`, cases in `proto_cases.json`; tested, not installed): all 31 own cases and the 11 Bash cases of this review pass, 0 mismatches (V10, the computed name, is the documented residual and is allowed). Test cases to add to `test_protect_files.py`:

| Command (the secrets file is written as the dotenv name) | Expected |
|---|---|
| `cat <name>`; `cat ./config/<name>`; `cat <name>.production`; `type <name>`; `cp <name> /tmp/x`; `source <name>`; `. ./<name>` | block |
| `echo X=1 > <name>`; `echo X=1 >> ./<name>`; heredoc whose target is `cat > <name>` | block |
| `grep KEY <name>`; `grep -n KEY README.md <name>` | block |
| `cat .en*`; `cat .e""nv`; `cat '.e'nv` | block |
| `grep -rn API_KEY .`; `rg --hidden API_KEY` | block |
| `cat <name>.example` | allow |
| `ls prod.env`; `cat .envrc` | allow |
| `grep -n "\.env" README.md`; `grep -rn ".env" docs/`; `rg -n "\.env" docs`; `grep -e <name> README.md` | allow |
| `git commit -m "docs: say never commit <name>"`; `git log --grep=<name>`; `echo "see <name> handling"`; `printf '%s' '<name> is secret'` | allow |
| heredoc writing `outputs/qa/x.md` whose body mentions the name | allow |
| `grep -rn API_KEY src/` | allow |
| `python -c "print(open('.'+'env').read())"` | allow (documented residual; covered by the Read deny rule only for the Read tool) |

Note on case: the production rule should also lowercase the basename before comparing (finding 2).
