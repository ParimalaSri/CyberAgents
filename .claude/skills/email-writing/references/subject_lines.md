# Subject lines

Plain, specific, under 8 words and 60 characters. It should read like a note from a colleague.

## Patterns that work
- Observation: "Your public SSH hosts"
- Question: "Who owns your exposed hosts?"
- Plain topic: "Quick note on your external footprint"
- Reply style (follow-ups): "Re: <first subject>"

## Avoid
- Hype or urgency: "URGENT", "Act now", "Last chance"
- Clickbait or curiosity gaps: "You won't believe..."
- Fake familiarity: "Re:" or "Fwd:" on a first email
- Exclamation marks, all caps, emojis
- Claims of compromise: "Your network was breached"

## Process
Write three candidates, pick the one with the most concrete noun from the account data.
Lint with `scripts/lint_email.py`.
