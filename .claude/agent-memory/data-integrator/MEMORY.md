# data-integrator memory (CyberIntel)

Curate this file: keep it under 150 lines. No data, secrets or trace content here.

## How to work
- Read CLAUDE.md, then only the sections/records you need (grep `### D<n>` in `docs/ARCHITECTURE.md`; do not read it whole, about 1,300 lines). Small steps, commit after each, one narrow scratch table (extract the few columns you need once into the scratchpad; never rescan the 1 GB JSONL per question). Two earlier runs stalled at about 10 minutes.
- Branch `feat/data-integrator/<task>` from the current tip; explicit `git add <paths>`; trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; never push or merge; leave the owner's uncommitted `.claude/agents/senior-data-engineer.md` alone.
- Never touch `data/raw/` or `D:/Cyber_DataSet/` (outside the repo; it holds the source files AND an environment file that must never be read or printed). If a hook blocks you, stop and tell the owner; never rephrase text to pass it.
- No pandas (policy-blocked). DuckDB and plain Python. Python heredocs mangle backslashes: use Write/Edit for regexes.

## The data (facts)
- Source: Shodan-style internet-scan dump, JSON Lines, one row per service banner on one IP:port; snapshot 2026-09-14 (the brief's link is a different snapshot, 2026-10-08). About 7.6-8.9M rows (estimate), about 61-71 minutes of scanning, so `timestamp` has NO usable spread (no recency signal).
- 78+ top-level columns, many sparse protocol structs. DuckDB read options: `sample_size=20000, maximum_object_size=33554432, ignore_errors=true`. Arrays need `len()`, not `cardinality()`. `vulns` is a MAP.
- The head-of-file sample is biased (one 12-minute window, port 12304 = 10.6% vs 0.22% spread). The dev sample is the SPREAD sample: `scripts/build_spread_sample.py` (1,000 positions x 100 lines, seed 42, from the decompressed `.json`; refuses protected output paths). `.zst` and `.json` matched on the first 512 MiB only.
- About 86% of rows sit on cloud/CDN/hosting/ISP organisations (infrastructure) and cannot be attributed to a customer; about 13-14% resolve to a company. Report the real unresolved share every time.

## Denylist work (your files: `scripts/denylist_match.py`, `context/denylist*.txt`, `cert_default_names.txt`)
- Files: exact (`denylist.txt`), prefix families, patterns (CIDR/globs), keywords (scope `org:` for org-text-only; compound `*hosting`), cert defaults. `normalise()` folds Latin accents, keeps non-Latin scripts, never returns empty for them. Entries under 4 characters (`ace`, `wix`, `ibm`, `ovh`) are exact-only.
- D5: the isp text NEVER excludes a row (a precision gate showed only 44% of isp-only exclusions were infrastructure; customers behind big carriers were being lost). Cloud provider, cloud/cdn tags and CIDR-on-IP rules still apply. `INFRA_REASONS` = cloud_provider, tag_rule, ip_pattern, org_exact, org_prefix, org_pattern, org_keyword; a test pins the set.
- Gate method for any new rule: hand-review up to 50 distinct newly matched orgs (largest first, then a seeded random sample), classify INFRA vs REAL/UNSURE from the name only, UNSURE counts as REAL, enable only at 90% or more. Record failed gates (they are not applied). Single reviewer, names only: say so. A hand list does not scale to the full file (D7.2): do not chase individual names.
- Lessons: carrier names match customers via the isp text (A1 Telekom Austria customers), so telecom words are org-scoped; `telecomunicacoes` merged with its accented form failed the gate after folding; Netflix/Meta/Facebook were excluded by prefix on hostname evidence (D7.1) not by the name gate; `huawei` was added as a family completion (D8.2).
- After any rule change: run `python scripts/test_denylist_match.py` (217 cases), update `outputs/denylist_*.md` and RAW-013, and tell the data-quality-engineer (the contract check imports your matcher, so its results change).

## Open items
- Names-only, single-reviewer validation of the whole denylist on a 100K sample; the full-file operator residual is unmeasured (D7.2a trigger: more than 5 of the top 50 by final contact_score read as operators; it tripped on the sample).
- The owner may supply an operator-type reference keyed on ASN (ASdb/PeeringDB): that would replace name lists for operators.
