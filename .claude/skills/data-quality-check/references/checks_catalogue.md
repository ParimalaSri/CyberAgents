# Checks catalogue

Always run these for the layers named. Each maps to a contract rule so a bug, once found,
can never come back silently.

| Layer | Check | Contract mechanism | Catches |
|---|---|---|---|
| hosts | key unique, no null key | `key`, `nullable: false` | duplicate ingest |
| hosts | dates not in the future | custom SQL | bad parsing |
| companies | `companies <= hosts` | `row_rule` op `<=` | grouping that creates rows |
| companies | no hyperscaler / CDN / ISP names | `denylist` | denylist leakage |
| companies | no empty / whitespace names | custom SQL | cleaning gaps |
| companies | unresolved share reported | custom SQL or report note | hidden unresolved data |
| signals | row count == companies row count | `row_rule` op `==` | join fan-out |
| signals | signal flags are 0/1 or within range | `min` / `max` | broken derivations |
| accounts | scores within 0 to 100 | `min: 0`, `max: 100` | scaling bugs |
| accounts | every account has a band | custom SQL | missing banding |
| accounts | `why` non-empty | custom SQL | unexplained accounts |
| accounts | band is one of contact/review/skip/exclude | custom SQL | typos |

## Judgement checks (not automatable, do by eye and record)
- Look at 10 random rows. Would a salesperson believe each one?
- Look at the top 20 and bottom 20 by score. Do both ends make sense?
- Compare against the previous layer: is every row count change explained?

## Verdict format
`PASS` or `FAIL` plus evidence (counts, example rows). Reviewers never fix the code. They file
the failure in `docs/ISSUES.md` (symptom, root cause, fix, contract rule that catches it) and
hand it back to the author.
