---
name: how-i-build-log
description: Keep a running log of where AI saved time and where it cost time, and turn it plus the change log into the half-to-one page "How I Build" reflection. Use at the end of a task or milestone to record a note, or when asked to draft docs/HOW_I_BUILD.md.
argument-hint: <note | draft>
version: 1.0.0
---

# how-i-build-log

Arguments: `$ARGUMENTS`

## When to use
- After a task: record what worked, what cost time, any weakness spotted. Takes one line.
- At the end: draft the reflection deliverable.
- NOT a replacement for `docs/ISSUES.md` (bugs) or git history (changes).

## Steps (record a note)
1. Append a dated bullet under a `## Running log` heading in `docs/HOW_I_BUILD.md` (create the
   heading if missing). Use one of these tags: `SAVED` (AI faster than by hand), `COST` (AI slower
   or needed rework), `WEAKNESS` (a known limitation), `TOOL` (which tool and for what).
   Include rough minutes and the concrete reason, e.g.
   `- 2026-10-11 SAVED ~40m: hooks and skill scaffolding generated and tested in one session.`
2. Be honest, especially on `COST`: wrong first attempts, tools that were blocked, rework.

## Steps (draft the reflection)
1. Read the running log, `docs/ISSUES.md`, `git log --oneline`, and `.claude/logs/changes.jsonl`
   for counts (edits per branch, number of sessions).
2. Draft half to one page covering the brief's three points:
   - **Dev loop and tools:** how work moved (plan mode, skills, subagents, hooks, branches/PRs), which tools (Claude Code, API scripts)
   - **Where AI saved the most time vs cost more than doing it by hand:** specific examples with rough numbers
   - **One known weakness** you would flag when handing the project to a teammate
3. Keep it concrete and first-person; no marketing language. Show the draft to the user to edit;
   the final reflection is theirs.

## Outputs
Updated `docs/HOW_I_BUILD.md` (running log, then the reflection).

## Rules
- Facts only: reference real tasks, commits and issues. No invented numbers; mark estimates as estimates.
- Do not rewrite the user's own notes without being asked.

## Worked example
> `/how-i-build-log note`  ("hook script blocked by Windows policy; needed a different approach")

Appends: `- 2026-10-11 COST ~15m: pandas DLL blocked by Application Control; local UI testing limited.`
