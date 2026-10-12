---
paths:
  - "**/*.py"
---

# Code style (enforced by `.claude/hooks/lint_check.py` and ruff)
- Every function and class has a ONE-LINE docstring saying what it does.
- Naming: `snake_case` for files, functions, variables; `PascalCase` for classes; `UPPER_SNAKE` for constants. Pipeline stages are `N_name.py` (`1_clean.py`). Prompts are `prompts/<feature>/vN.md`. Branches are `feat/<role>/<task>`.
- Use the same name for the same concept across all layers (e.g. `company_id`, `account_id`). Do not invent synonyms.
- Fix hook feedback before moving on. Do not silence the linter.
