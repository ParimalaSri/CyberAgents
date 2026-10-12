---
paths:
  - "llm/**"
  - "prompts/**"
  - "evals/**"
---

# LLM calls
- ALL LLM calls go through `llm/client.py`. Never call the API anywhere else.
- Every call is logged to `traces/<env>.jsonl` with: timestamp, request, response, model, prompt_version, input_tokens, output_tokens, latency_ms, cost_usd, decision, account_id.
- Prompts live in `prompts/<feature>/vN.md`. Never inline prompt text in code. New prompt = new version file. Never overwrite an old version.
- Use the cheapest model that works: Haiku for classification, Sonnet for drafting.
- Enforce a per-run cost ceiling in code. Abort if exceeded.
- LLM output must be validated JSON. Retry once on failure, then mark `needs_human`.
- The LLM is used ONLY for judgement on the ambiguous "review" band, and for text generation (summaries, outreach).

# Evals
- The labelled set (`evals/labeled.jsonl`, 20 to 30 examples) is labelled BY THE OWNER. Claude may suggest candidate labels with reasoning, but the final label is theirs. Do not overwrite labels.
- `python evals/run_eval.py --prompt v2 --baseline v1` prints precision, recall, and a comparison against the previous prompt version, and saves to `evals/results/`.
