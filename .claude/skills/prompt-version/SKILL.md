---
name: prompt-version
description: Create, list and diff versioned prompt files in prompts/<feature>/vN.md. A new prompt is always a new version file; old versions are never overwritten. Use when asked to change, improve, add or compare a prompt.
argument-hint: <new|list|diff> <feature> [...]
version: 1.0.0
---

# prompt-version

Arguments: `$ARGUMENTS`

## When to use
- Any prompt change, however small; adding a prompt for a new feature; comparing v1 with v2.
- NOT for judging which prompt is better (use `eval-run`).

## Inputs
- Feature folder name (`account_scoring`, `outreach`, `email_writing`)
- A one-line reason for the change
- Template and rules: `references/prompt_template.md`, `references/versioning_rules.md`

## Steps
1. List versions: `python .claude/skills/prompt-version/scripts/prompt_tool.py list <feature>`
2. Create the next one (copies the latest as the parent):
   `python .claude/skills/prompt-version/scripts/prompt_tool.py new <feature> --change "<why>"`
   The tool refuses to overwrite an existing file.
3. Edit ONLY the new file. Change one thing at a time.
4. Show the change: `python .claude/skills/prompt-version/scripts/prompt_tool.py diff <feature> v1 v2`
5. Run `eval-run --prompt vN --baseline vM` before anyone calls the new version better.
6. Commit the new file on a feature branch; `llm-engineer` owns prompts, `qa-engineer` reviews.

## Outputs
`prompts/<feature>/vN.md` with front matter (version, parent, date, change) and a diff for the PR.

## Rules
- New prompt = new version file. Never edit or delete an old version. No inline prompt text in code.
- The JSON output contract matches the skill's schema; changing it needs a version bump and a validator update.

## Worked example
> `/prompt-version new account_scoring`  (change: "require citing two signals")

Creates `prompts/account_scoring/v2.md` with `parent: v1`, then `diff account_scoring v1 v2`
shows only the added rule, ready for `eval-run`.

## Files
- `scripts/prompt_tool.py` list, new, diff
- `references/prompt_template.md` skeleton with front matter and placeholders
- `references/versioning_rules.md` the rules
