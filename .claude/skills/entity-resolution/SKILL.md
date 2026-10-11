---
name: entity-resolution
description: Group raw host/organisation rows into companies with precision first - normalise names, exclude cloud/CDN/ISP denylist names, and report the unresolved share openly. Use when building or fixing 2_companies, when companies look split or wrongly merged, or when the unresolved percentage is unclear.
argument-hint: <name-column> [--denylist file]
version: 1.0.0
---

# entity-resolution

Arguments: `$ARGUMENTS`

## When to use
- Building `pipeline/2_companies.py`, or debugging duplicate or merged companies.
- NOT for scoring or signals.

## Inputs
- `data/silver/hosts.parquet`, the candidate entity columns from `data-profiling`
  (organisation name, domain, ASN or owner fields)
- A denylist file (`context/denylist.txt`, one lowercase name per line) of hyperscalers, CDNs,
  ISPs, hosting providers and registrars: they own the hosts but are not our customers

## Steps
1. Preview the collapse:
   `python .claude/skills/entity-resolution/scripts/cluster_preview.py data/silver/hosts.parquet --column <name_col> --denylist context/denylist.txt`
   It shows the unresolved share, raw vs normalised distinct names, denylist hits, the biggest
   clusters and clusters that merge several spellings.
2. Resolve in tiers, strongest evidence first: a shared domain, then an exact normalised
   name. Fuzzy matching alone never merges two names; it only proposes candidates for review.
3. Read the "merging several spellings" list by eye for false merges ("Acme Bank" vs "Acme Bakery").
   When unsure, keep rows apart: precision over recall.
4. Exclude denylist names before counting companies, and extend the denylist from the most
   frequent organisation values.
5. Write companies with a stable `company_id` and a `host_count`; keep the unresolved rows
   in the layer or a side count. Report the unresolved percentage openly in the stage report and docs.
6. Hand to `data-quality-check` (rules: `companies <= hosts`, no denylist names, unique `company_id`).

## Outputs
- Logic for `pipeline/2_companies.py` (deterministic SQL/Python), denylist file
- Unresolved percentage and cluster examples for `docs/ARCHITECTURE.md`; bugs in `docs/ISSUES.md`

## Rules
- Precision over recall. Never hide the unresolved share.
- Deterministic rules only; no LLM for grouping.
- No cloud/CDN/ISP names as companies.

## Worked example
> `/entity-resolution org --denylist context/denylist.txt`

Output: 100,000 rows, 18.2% unresolved; 7,311 raw names -> 6,402 normalised; denylist hits
`amazon.com, inc. (11,402)`; "Acme Inc" / "ACME, Inc." / "Acme" merge into one cluster. (Illustrative.)

## Files
- `scripts/cluster_preview.py` normalisation and cluster preview (optional helper)
