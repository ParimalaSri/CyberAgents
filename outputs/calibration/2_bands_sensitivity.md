# 2. Band sizes, sensitivity, caps, capacity (PROVISIONAL constants; 5,790 accounts, 1 excluded)

Definition: 'would-be contact' = contact_score >= X and not excluded (band_uncapped = contact). Under D10 every would-be contact is held in review (operator_unverified), so the stored band 'contact' count is 0; the review band stored = review-range + would-be contacts.

## Grid: would-be contact / review (score range only) / skip
Rows X (contact), columns Y (review). Cell = contact / review / skip.

| X \ Y | 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|
| 30 | 390 / 343 / 5056 | 390 / 284 / 5115 | 390 / 274 / 5125 | 390 / 183 / 5216 | n/a |
| 35 | 199 / 534 / 5056 | 199 / 475 / 5115 | 199 / 465 / 5125 | 199 / 374 / 5216 | 199 / 191 / 5399 |
| 40 | 107 / 626 / 5056 | 107 / 567 / 5115 | 107 / 557 / 5125 | 107 / 466 / 5216 | 107 / 283 / 5399 |
| 45 | 50 / 683 / 5056 | 50 / 624 / 5115 | 50 / 614 / 5125 | 50 / 523 / 5216 | 50 / 340 / 5399 |
| 50 | 21 / 712 / 5056 | 21 / 653 / 5115 | 21 / 643 / 5125 | 21 / 552 / 5216 | 21 / 369 / 5399 |
| 55 | 9 / 724 / 5056 | 9 / 665 / 5115 | 9 / 655 / 5125 | 9 / 564 / 5216 | 9 / 381 / 5399 |

Provisional 40/20: would-be contact 107 (1.85%), review range 557 (9.62%), skip 5125 (88.51%); stored review band = 557+107 = 664, exclude 1.

## Plus or minus 5 sensitivity (accounts that change uncapped band; baseline 40/20)

| change | accounts changing band | detail |
|---|---|---|
| contact 40 -> 35 | 92 | (199, 465, 5125) (c/r/s) |
| contact 40 -> 45 | 57 | (50, 614, 5125) (c/r/s) |
| review 20 -> 15 | 10 | (107, 567, 5115) (c/r/s) |
| review 20 -> 25 | 91 | (107, 466, 5216) (c/r/s) |

Tie piles that drive the review-threshold sensitivity (accounts with contact_score exactly): 20:58, 25:110, 30:125, 15:3; the review edge sits on a pile at 20, 25 and 30.

Finer review-threshold scan with contact fixed at 40 (Y: review range size): [(10, 626), (12, 601), (15, 567), (18, 563), (20, 557), (21, 499), (23, 493), (24, 469), (25, 466), (26, 356), (28, 329), (29, 313), (30, 283), (31, 158), (32, 157)]

## Effect of each cap on would-be contacts (recomputed from signals at each X)

| X | would-be | singleton | low conf | operator_name_shape (T1/T2 union) | any of the three | none of the three (clean) | operator_unverified (all) |
|---|---|---|---|---|---|---|---|
| 30 | 390 | 155 | 12 | 92 | 224 | 166 | 390 |
| 35 | 199 | 37 | 6 | 27 | 63 | 136 | 199 |
| 40 | 107 | 24 | 4 | 13 | 37 | 70 | 107 |
| 45 | 50 | 2 | 1 | 5 | 7 | 43 | 50 |
| 50 | 21 | 0 | 0 | 3 | 3 | 18 | 21 |

At X=40 (107 would-be contacts): singleton 24; operator shape 13 (T1 9, T2-only 4, T2 total 8); singleton and operator 1; low confidence 4.
Cap counts from the stored cap_reasons at 40: [('operator_unverified', 70), ('operator_unverified,singleton', 20), ('operator_name_shape,operator_unverified', 12), ('low_confidence,operator_unverified,singleton', 3), ('low_confidence,operator_unverified', 1), ('operator_name_shape,operator_unverified,singleton', 1)]

Reading: D9.8 reported 108 would-be contacts before D10 and the table now gives 107; I did not trace the one-account difference (probably the D10 union penalty lowering a score below 40, unverified). Excluding the three name/shape caps, the 'clean' set is the number in the column 'none of the three'; the singleton cap alone removes the 'singleton' column. Under D10 all would-be contacts are held regardless, so today the caps change nothing in the stored band; they matter once an adjudicator or ASN reference replaces operator_unverified.

## Rep capacity scenarios (capacity NOT supplied by the owner; shown at 25, 50, 100, 200 accounts per week)

Method. A rep list of C accounts per week must come from accounts adjudicated as organisations. Assume the final list is filled from the ranked pool (by contact_score) after adjudication. The pool size N the adjudicator must read = C / r, where r is the share of the top-ranked accounts that clear as real end-user organisations. Evidence for r is thin: earlier names-only reads gave 13 of 70 organisation (19%) for the pre-D10 contacts and 7 of 50 (14%) in the top 50; my own read is in step 5 (r from names only, one reviewer). So r is shown at 15%, 30% and 50%. Calls use the section 7 assumptions (900 input, 120 output tokens per call); counts only, no prices. The pool is the top N by contact_score; because of tie piles the score at rank N is the cut and the real count is the number at or above it.

Reference: the pool is a standing list, not a weekly refresh: the sample has no recency (61-minute scan), so 'per week' means how many accounts a rep can work from the list per week, and the list is consumed over time.

| capacity C | r | pool N=C/r | contact_score at rank N | accounts at or above that score | input tokens (N x 900) | output tokens (N x 120) | pool as share of 5,790 |
|---|---|---|---|---|---|---|---|
| 25 | 15% | 167 | 35 | 199 | 0.179M | 0.024M | 3.4% |
| 25 | 30% | 83 | 41 | 101 | 0.091M | 0.012M | 1.7% |
| 25 | 50% | 50 | 45 | 50 | 0.045M | 0.006M | 0.9% |
| 50 | 15% | 333 | 30 | 390 | 0.351M | 0.047M | 6.7% |
| 50 | 30% | 167 | 35 | 199 | 0.179M | 0.024M | 3.4% |
| 50 | 50% | 100 | 41 | 101 | 0.091M | 0.012M | 1.7% |
| 100 | 15% | 667 | 19 | 669 | 0.602M | 0.080M | 11.6% |
| 100 | 30% | 333 | 30 | 390 | 0.351M | 0.047M | 6.7% |
| 100 | 50% | 200 | 34 | 221 | 0.199M | 0.027M | 3.8% |
| 200 | 15% | 1333 | 0 | 5789 | 5.210M | 0.695M | 100.0% |
| 200 | 30% | 667 | 19 | 669 | 0.602M | 0.080M | 11.6% |
| 200 | 50% | 400 | 29 | 420 | 0.378M | 0.050M | 7.3% |

Notes on the table. (i) The row C = 200, r = 15% asks for 1,333 accounts but only 1,324 have any urgency, so the cut falls to a score of 0 and the "pool" becomes the whole file (5,789): the sample cannot fill a 200-a-week list at a 15% clearance rate with exposure-led accounts. (ii) Reference: the provisional review band (664 accounts) = 0.60M input and 0.08M output tokens at 900 / 120 per call (the D9.8 figure 0.53M / 0.07M was for 593 calls before D10 added the 107 would-be contacts to review). (iii) Pool sizes use the top-N-by-score cut; the "accounts at or above that score" column is the real call count, larger than N where the cut lands on a tie pile (for example N = 333 gives 390 calls because 125 accounts tie at 30).

What this means for review. For every capacity the review band is a count-capped top-N (D9.7), not a score threshold, because the review edges at 20, 25 and 30 sit on tie piles of 58, 110 and 125 accounts. At the clearance rates above, review needs are: 25 per week about 50 to 199 calls; 50 per week about 101 to 390; 100 per week about 221 to 669; 200 per week 420 to the whole file. The provisional 40/20 (664 calls) is about right for 100 a week at a low clearance rate and larger than needed for 25 or 50 a week. Capacity is the owner's input and is still blank; nothing here is a decision.
