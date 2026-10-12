# Checker upgrade: shared denylist matcher (closes RAW-010), 2026-10-11

Branch `feat/data-quality/contract-matcher`. Files: `.claude/skills/data-quality-check/scripts/check_contract.py`,
`.../scripts/test_check_contract.py`, `.../references/contract_example.yml`, `docs/ISSUES.md`.

## What changed
- `check_denylist`: imports `scripts/denylist_match.py` (repo root = `Path(__file__).resolve().parents[4]`, verified; works from any cwd).
  - Old form `{column, file}`: unchanged semantics (exact names) but BOTH sides now go through `normalise()`.
  - New form `{column, rules: shared}` (optional `context_dir`): `load_rules` + `match_name(value, "org", rules)`; exact, prefix, pattern, keyword.
    Fails if any value matches; evidence = distinct match count, row count, up to 5 examples with rule type and entry.
    The field is fixed to "org" (D5): there is no option to match isp text.
  - Missing matcher or rule file: the check FAILS with "cannot import shared matcher" / "cannot load denylist rules".
- New `infra_reason` check: values must be in `INFRA_REASONS`; `isp_*` and unknown values fail; `nullable: false` optional.
- New `shares` check (generic): shares of a category column (optional weight column) sum to 100% with no nulls and only `allowed` values;
  share of `resolved_values` inside `resolved_min..resolved_max`. It needs no layer schema beyond the column names in the contract.
  Not verified against the real `companies` layer (not built yet); whether the share is by host rows (weight `host_count`) or company rows is a
  decision for the 2_companies contract.
- Bug found in my own first draft by the tests: an empty `infra_reason: {}` block was falsy and silently skipped; fixed (`is None` test).

## Tests
- `python .claude/skills/data-quality-check/scripts/test_check_contract.py`: 20 tests, OK (also OK when run from `/`).
- `python scripts/test_denylist_match.py`: 106 cases passed.
- Covered: old-form pass/fail/accent+case variants/not prefix/missing file; shared exact, prefix ("Microsoft Azure"), patterns (CIDR text, glob),
  org keyword ("Acme Telecom Ltd") and plain keyword, accents ("Telefónica Chile", "Microsóft Corporation"), real names not flagged
  (Stripe, Acme Bank, OVHTECH, Webhosting Pioneers, Vpnsoft), max 5 examples, isp column ignored, missing rule dir, missing matcher
  (checker copied to a tree without `scripts/`), run from another cwd, infra_reason values, shares.

## Old vs new coverage on `data/sample/spread_100k.jsonl` orgs (scratch table, not committed)
Distinct non-null `org` values: 6,579 (read_json sample_size=20000, maximum_object_size=33554432, ignore_errors=true). Each is one row.

| logic | distinct orgs flagged |
|---|---|
| OLD (lower/trim exact match against `context/denylist.txt`) | 205 |
| OLD form after this change (exact file, both sides normalised) | 241 |
| NEW shared rules | 897 (exact 241, keyword 583, prefix 70, pattern 3) |

692 orgs are flagged by the new shared rules and were missed by the old logic. Examples: Kraut.Hosting (keyword hosting), CHINANET XIZANG PROVINCE NETWORK
(chinanet), Pakistan Telecommunication Company Limited (telecommunication), Zscaler Israel TLV2 (prefix zscaler), Maxis Broadband Sdn.Bhd (broadband).
Keyword sample eyeballed (10): all look like ISP, telecom, hosting or VPS names; two are ambiguous by name alone ("Atlantic Broadband", "Netic email hosting"
could be a small ISP or a mail host), consistent with the 90% gate in RAW-013. That is a rule decision, not a checker defect.
Not measured here: row-level counts (distinct orgs only), the other columns (isp, ip, tags, cloud.provider) that make up the full D4 rule.
