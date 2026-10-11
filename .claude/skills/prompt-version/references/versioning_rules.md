# Prompt versioning rules

1. A prompt is a file: `prompts/<feature>/vN.md`. Never inline prompt text in code.
2. A change of any kind (even one word) is a NEW file. An old version is never edited or deleted.
3. Every file has front matter: `version`, `feature`, `parent`, `date`, `change` (one line why).
4. Every LLM call logs `prompt_version`, so a trace line can always be tied to its exact text.
5. A new version is not "better" until `eval-run` says so against the previous version.
6. The output contract (JSON schema) changes only with a version bump, and the validator in
   `llm/client.py` is updated in the same PR.
7. Features currently in scope: `account_scoring` (Haiku), `outreach` (Sonnet),
   `email_writing` (Sonnet). Add a new folder only with a new feature.
8. Record the model per version in the front matter if it differs from the project default.
9. Keep the diff small: change one thing per version so an eval difference has one cause.
