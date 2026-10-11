# Cost model (for docs/ARCHITECTURE.md)

Show the math, not just the total. Fill every cell from traces or a stated assumption.

## Per-task model choice
| Task | Model tier | Why this tier | Calls per run | Avg in tokens | Avg out tokens |
|---|---|---|---|---|---|
| Review-band adjudication | cheapest that passes evals (Haiku) | classification with a JSON verdict | review-band size | <from traces> | <from traces> |
| Outreach / email drafting | stronger (Sonnet) | writing quality matters | on demand, per account | <from traces> | <from traces> |

## Formulas
- `cost per call = (in_tokens x price_in + out_tokens x price_out) / 1,000,000`
- `cost per run = calls per run x cost per call`
- `cost per month = runs per month x cost per run`

## Levers (state which you use)
- Rules shrink the LLM's input: only the review band is sent (the largest saving).
- Short prompts and compact JSON input; cap `max_tokens`.
- Prompt caching for the fixed ICP/context block if the provider supports it for this size.
- Batch non-urgent runs; cache drafts so the UI never pays twice for the same account.

## Ceilings
- Per-run ceiling enforced in `llm/client.py` (abort when exceeded): about 2x the projection.
- Dev uses a small ceiling and the 100K sample; prod uses the full scored extract.
- Per-session cap in the UI for interactive drafting.

## Review cadence
Re-run `cost-report` after every prompt version and before every dev to prod promotion.
Note the date and model prices used; prices change.
