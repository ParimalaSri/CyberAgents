# Outreach tone guide

## Principles
- **Factual, calm, specific.** Mention one or two observed facts from the account's data.
  Never claim a breach, an attack or a compromise happened.
- **Soft framing.** "We noticed ... publicly visible" not "your systems are exposed to hackers".
- **One call to action.** A 15-minute review or a short question. Nothing else.
- **Short.** Email under 120 words, LinkedIn under 60. First line is about them, not us.
- **No fabrication.** Use only values in the account row. No invented names, numbers or news.

## Structure (email)
1. Subject: specific and plain (under 8 words), no clickbait.
2. Line 1: the observation ("Your public footprint includes 14 hosts running outdated OpenSSH").
3. Line 2: why it matters, in one sentence, no scare words.
4. Line 3: what we offer, tied to `context/business.md`.
5. Close: one question or one proposed time-boxed step.

## Personalisation levers (use at most two)
- Segment or industry from the ICP match
- The strongest risk signal and its value
- Size or footprint ("a footprint of 40 hosts")

## Persona adjustments
- Security lead: technical, name the exposure precisely.
- IT / ops lead: operational impact, effort to fix.
- Executive: business risk in one sentence, no jargon.

## Before returning
Run `scripts/validate_draft.py`; fix FAIL items. The `signals_used` list lets a human check
each claim against the data.
