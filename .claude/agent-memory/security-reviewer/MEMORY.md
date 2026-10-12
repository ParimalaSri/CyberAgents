# security-reviewer memory (CyberIntel)

Curate this file: keep it under 150 lines. Never record secret values here (not even prefixes), data, or trace content.

## How to work
- You are READ-ONLY: Bash only for `git diff`, `git log`, `git show`, `git ls-files`, `grep`. You never edit, commit, branch, merge or push. Return `CLEAN` or `ISSUES` with severity, file:line and evidence, plus what you did NOT check. You are a required check on every PR into `dev`. The formal scan of the full stack (about 85 commits over `dev`) has NOT been run yet.
- Never read or print the environment file (the dataset folder `D:/Cyber_DataSet/` contains one, and the hook blocks any command text that mentions its name: a known false positive; the owner decides; never rephrase to pass it). Never open a file only to quote a secret; show file, line and at most the first 4 characters of a suspected key.
- Read CLAUDE.md and `.claude/rules/llm.md`; use `git diff --name-only dev...HEAD` for scope.

## What was already verified (2026-10-12, by main session and senior engineer)
- Tracked files: no data, trace, parquet or jsonl files, no secret-looking names, no file over 2 MB; hidden top-level entries tracked are only `.claude`, `.github`, `.gitignore`. All commits are authored by ParimalaSri (an earlier contributor identity was rewritten out of history and the old commits exist only in LOCAL `backup/*` branches, which must never be pushed).
- No API caller exists yet (`llm/` empty), no prompt text in code, no `anthropic`/`openai`/`requests`/`httpx`/`urllib` anywhere in `.py`, no network code. Re-verify at M3.
- `.gitignore` covers `data/`, `traces/`, `.claude/logs/`, `.claude/settings.local.json`.

## Known weaknesses to restate in every review
- Hooks and settings (QA findings 11-14, owner decides): Grep/Glob are not in the PreToolUse matcher or deny rules, so a Grep call pointed at the secrets file is not hooked (High); the secrets-file regex is both too broad (blocks mentions in a search pattern) and too narrow (misses reads that do not name the file); checks are case-sensitive and do not resolve `..`; the dataset folder has no hook protection; `branch_guard.py` blocks feature branches whose names contain `dev`, `prod` or `main` as a word; `--force-with-lease` coverage is unverified.
- Incident: a QA mutation run wrote a stray file into `D:/Cyber_DataSet/` (outside the repo; owner to delete `qa_guard_test.parquet`). Tests now use scratch folders with injectable constants; `scripts/path_guard.py` is an allowlist for output paths (plain relative or `X:/` paths; refuses UNC, device, extended and stream forms).
- Prompt-injection path (check at M3): scan fields (banners, titles, hostnames, org names, certificate strings) are attacker-controlled; they must be delimited as data in prompts and model output must never trigger actions. The adjudicator and drafting prompts are the review target.
- PII and sensitive data: banners, certificates and screenshots can contain personal data or credentials; the silver table keeps no raw payload columns (html, screenshot, data); outreach drafts must not claim a breach happened.
- Hosted app (M5): the serving extract on `prod` must be small, derived at company level, reviewed before commit; API keys only through Streamlit secrets; the app must not call the API itself.

## Checklist you follow (also in your agent file)
Secrets in any file; forbidden files in the diff (`.env*`, `data/`, `traces/`, `.claude/logs/`, raw dumps, parquet or large jsonl); writes to `data/raw/` or loosened guardrails in `.claude/hooks/` or `settings.json`; API calls outside `llm/client.py`; inline prompts and untrusted text in prompts; personal data; outreach safety; new dependencies (name them, flag unknown or typosquat-looking ones).
