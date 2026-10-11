# Writing the `why` explanation

Every account, in every band, carries a `why` a salesperson can read without opening the data.

## Rules
- One to two sentences, under 40 words.
- Lead with the strongest reason, then the second. Name the concrete signal and its value.
- Say what it means for the buyer ("exposed remote admin panel"), not the column name.
- Only use facts present in the account's data. No guessing at industry or intent.
- Be honest about weakness: if the account is borderline, say what is missing.

## Good
- "14 internet-facing hosts running an outdated OpenSSH, in a mid-size fintech (ICP segment 2)."
- "Strong fit (large footprint) but no risk signals this quarter, so not urgent."

## Bad
- "High score." (no reason)
- "Likely to have been breached." (unsupported claim)
- "fit_score=82, urgency_score=61" (column dump, not an explanation)

## Rule-based `why` (contact and skip bands)
Generated deterministically in `4_score` by joining the top 2 signal contributions into a
sentence template. The LLM writes `why` only for `review` accounts.
