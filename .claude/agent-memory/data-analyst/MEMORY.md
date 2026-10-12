# data-analyst memory (CyberIntel)

Curate this file: keep it under 150 lines. No data, secrets or trace content here.

## How to work
- You calibrate and analyse; the owner and senior engineer decide. Your ONLY writable path is `outputs/calibration/`; read-only on `data/`. Your labels (operator/organisation reads) are names-only, one reviewer, and are NOT eval ground truth (labels in `evals/labeled.jsonl` are the owner's).
- Read CLAUDE.md, the `scoring-calibration` skill, then only the records you need (grep `### D9`, `### D10`, `### D11`, `### D12`; never read `docs/ARCHITECTURE.md` whole, about 1,300 lines). Small steps: one narrow scratch table joining accounts and signals on `company_id`, write each result file as you finish it, commit at the end (long runs stall at about 10 minutes).
- Branch `feat/data-analyst/<task>` from the current tip; explicit `git add outputs/calibration`; trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; never push or merge. No pandas. Never touch `data/raw/` or `D:/Cyber_DataSet/`.
- Seeds already used for name reads: 5, 7, 10, 23. Use a new seed and say which. Propose weights/thresholds; never present provisional constants as decisions.

## What the first calibration found (sample, 5,790 accounts, provisional constants)
- Scores are coarse: fit has 14 distinct values (plateaus 35 and 15, 62% zero), urgency 20 values (5, 40, 50, 60 hold most), contact_score 56 values. Ties pile at 3 (424), 25 (110), 30 (125), 20 (58): a score threshold is the wrong tool for the review band, so D11 uses a count-capped top-N (REVIEW_N provisional 200, floor 20). Fit and urgency are almost uncorrelated (0.10).
- Would-be contacts (51 after territory 0, 107 before) depend ENTIRELY on KEV/CVSS points (removing them leaves 0), which are banner-inferred (RAW-006). Removing the placeholder US territory points removed 56 of 107; "everyone in territory" added 171. 77.65% of companies have no urgency signal.
- Form (b) (multiplicative, FLOOR 0.5) vs a weighted sum: Spearman about 0.68 overall, 0.87 among urgent accounts; top-107 overlap 105; keep (b) (fit alone can never create a contact).
- T2 operator pattern FAILED the gate on seed 23: 23 operator / 16 unsure / 1 organisation of 40 (57.5% vs the 32/40 bar); the `net` suffix branch was the cause (5 of 22 operators, 16 unsure bare names). Without it the other 202 names read 18 of 18. D11.1 dropped that branch. T1 on a fresh 20: 13 operator, 7 unsure, 0 organisation.
- Second read of the 107 would-be contacts: 48 operator, 37 unsure, 22 organisation (79% operator or unsure); the D7.2a trigger (more than 5 of the top 50 operator or unsure) tripped (41 of 50). The T1/T2 flags catch about a quarter of the operators; organisations in the list include Jingdong, NCR, HPE, U.S. Marshals Service, universities, Prudential, Comodo (a security vendor, excluded under D2 for infrastructure but present as an account).
- Duplicates in the top 50: PDR / P.D.R Solutions FZC (same company), Leaseweb Deutschland / USA / Netherlands. DQ-007: no fuzzy matching in v1; a presentation-level `group_key` is planned for M5.
- Skip band: 659 skip accounts with urgency above 0 had max contact_score 19; "Exposure is limited." read as reassurance (DQ-013, fixed in D11/D12: "Below the review cut-off." and a neutral rank clause on KEV/CVSS skip rows).
- Rep capacity table (the owner has not supplied capacity): 25/week needs about 50-199 review calls, 50/week about 101-390, 100/week 221-669, 200/week 420 to the whole file; at 200/week the sample cannot fill the list (only 1,324 accounts have any urgency).

## Redo after owner inputs
- Territory list (contact count and which accounts reach review change), rep capacity (sets N), operator-type reference by ASN (would replace the name flags), whether banner-inferred KEV/CVSS may lead the ranking, a verdict on security vendors.
- After the M3 adjudicator runs: measure clearance rate (overall and for singletons), re-measure the D7.2a metric on the FINAL list (top 50 by final contact_score, target at most 5 operator or unsure, else reopen with the ASN reference), and re-check ties at the cut.
