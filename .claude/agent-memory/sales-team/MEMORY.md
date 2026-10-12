# sales-team memory (CyberIntel)

Curate this file: keep it under 100 lines. No data, secrets or trace content here. You have NOT been asked for feedback yet (the app does not exist); this records the usability problems already found so you start informed.

## Role reminders
- You are a simulated B2B cybersecurity sales rep with about ten minutes to decide who to call first. Your feedback is usability input, NOT ground truth and NEVER eval labels. You are read-only (Read, Grep, Glob): you write nothing. End every reply with "Simulated feedback; confirm with a real rep."
- Read `context/business.md` and `context/icp.md` first; their `[OWNER]` blanks (product, buyer titles, capacity, territories, industries) are still empty, so say what you cannot judge.

## What a rep will see today (known facts)
- The ranked list has NO `contact` band until the M3 adjudicator exists: every would-be contact (51 on the 100K sample) is held in `review` with the clause "Not yet checked that this is an end-user organisation, not a network operator." The app should label the list "to review", not "contact".
- Most high-urgency accounts are network operators (hosting, ISP, telecom, cloud): about 79-86% of the would-be contacts read as operator or unsure by name (one reviewer). A rep who calls a hosting provider loses trust. The `why` carries "Name looks like a network operator." on flagged review rows, but the flag catches only about a quarter of operators.
- `why` text rules: plain English, at most 40 words, names the top one or two signals with values, never claims a breach happened. KEV and CVSS sentences are version-matched, not confirmed vulnerabilities ("running software whose version matches the CISA known-exploited list"; "worst version-matched vulnerability scores CVSS X").
- Skip means "not prioritised in this run", not "safe": "Below the review cut-off." (and "Ranked below this run's review list; a rank, not a judgement of risk." on KEV/CVSS skip rows). Earlier wording "Exposure is limited." read as reassurance and was removed.
- Territory is not applied yet (points 0 until the owner supplies a list); country shown is the host IP country, not headquarters. The data has no industry, headcount or revenue.
- Duplicate-looking accounts appear (PDR and P.D.R Solutions FZC; Leaseweb Deutschland / USA / Netherlands): no fuzzy matching in v1; a presentation-level grouping key is planned.
- Resolved companies are only about 13-14% of scanned rows; the rest sits on shared infrastructure. Expect a short, partly operator-heavy list, not market coverage.

## Questions worth asking when you review the app
Can I act in one minute? Do I believe the `why`? Which accounts would I never call, and why (operators, security vendors such as Comodo, universities if not wanted)? What is missing (contact person, industry, size, last seen)? Would I send the draft outreach as written (calm, factual, one call to action)?
