# 3. contact_score form (a) weighted sum vs (b) multiplicative (urgency gated by fit); PROVISIONAL

Form (a) uses the stage placeholder W_F_PCT = 30 (the stage says: 'D9 gives no value, so this is a placeholder invented only to exercise form (a)'); the comparison depends on it and is illustrative. Form (b) is the stage default with FLOOR 0.5. Both use the same fit_score (which already carries the D10 operator penalty) and urgency_score. I recomputed (a) with the stage formula (30*fit + 70*urgency + 50) // 100 in DuckDB; I did not run the stage with CONTACT_FORM = 'a'. Ranking ties are broken by the stage order (urgency desc, host_count desc, account_id).

- Spearman rank correlation of (a) and (b), all 5,789 non-excluded: 0.677; Pearson on scores 0.942.
- Spearman among the 1,324 accounts with urgency > 0 (the only ones where (b) is non-zero): about 0.870 (note: the a-score is non-zero for 2,187+ fit>0 accounts with no urgency).
- Accounts with score > 0: (a) 2857, (b) 1323.
- Top 25 overlap (by rank, same size lists): 23 of 25.
- Top 50 overlap (by rank, same size lists): 49 of 50.
- Top 107 overlap (by rank, same size lists): 105 of 107.

## Which form separates strong-urgency-and-fit from exposed non-buyers
Groups (defined by raw signals, not by names): S = urgency >= 50 AND fit >= 35 (strong exposure and some fit); N = urgency >= 50 AND fit = 0 (exposed non-buyers, in this data: outside placeholder territory, one IP, or operator-shaped); Z = urgency = 0 AND fit >= 50 (fit only, nothing exposed).

Group sizes: S 112, N 273, Z 178.

| list | form | size | S in list | N in list | Z in list | other |
|---|---|---|---|---|---|---|
| top 50 | (a) W_F=30 | 50 | 37 | 0 | 0 | 13 |
| top 50 | (b) floor 0.5 | 50 | 38 | 0 | 0 | 12 |
| top 107 | (a) W_F=30 | 107 | 70 | 4 | 0 | 33 |
| top 107 | (b) floor 0.5 | 107 | 72 | 2 | 0 | 33 |
| top 200 | (a) W_F=30 | 200 | 93 | 16 | 0 | 91 |
| top 200 | (b) floor 0.5 | 200 | 93 | 16 | 0 | 91 |

Mean rank (1 = best): S under (a) 103, N under (a) 391; S under (b) 94, N under (b) 391. A form separates better when the S-to-N rank gap is larger.

Under (a) with threshold 40: 421 accounts reach >= 40; under (b) 107. Under (a) at the top 107, the lowest urgency in the list is 50 (b: 50); highest-urgency account with fit 0 under (a) ranks 52, under (b) ranks 102.

Urgency 100 accounts and exposure: top 10 under (a) (name, urgency, fit, a, b): [('Beijing Jingdong 360 Degree ', 90, 50, 78, 68), ('Wowrack.com', 90, 50, 78, 68), ('NCR Corporation', 75, 80, 77, 68), ('Strato Rechenzentrum, Berlin', 100, 20, 76, 60), ('Aruba S.p.A. - Cloud Service', 95, 20, 73, 57), ('Leaseweb Deutschland GmbH', 90, 30, 72, 59), ('HEWLETT PACKARD ENTERPRISE C', 80, 50, 71, 60), ('Eonix Corporation', 70, 65, 69, 58), ('U.S. Marshals Service in acc', 75, 50, 68, 56), ('Interserver, Inc', 80, 35, 67, 54)]

Top 10 under (b): [('Beijing Jingdong 360 Degree ', 90, 50, 78, 68), ('Wowrack.com', 90, 50, 78, 68), ('NCR Corporation', 75, 80, 77, 68), ('Strato Rechenzentrum, Berlin', 100, 20, 76, 60), ('HEWLETT PACKARD ENTERPRISE C', 80, 50, 71, 60), ('Leaseweb Deutschland GmbH', 90, 30, 72, 59), ('Eonix Corporation', 70, 65, 69, 58), ('Aruba S.p.A. - Cloud Service', 95, 20, 73, 57), ('U.S. Marshals Service in acc', 75, 50, 68, 56), ('Interserver, Inc', 80, 35, 67, 54)]

## Reading and recommendation (proposal)
- At the head of the list the two forms agree: top 25 share 23, top 50 share 49, top 107 share 105. Where they differ is below the head: (a) gives a positive score to 2,857 accounts because fit alone adds points (up to 0.3 x 85 = 25), (b) to 1,323 (only accounts with some urgency). Overall Spearman 0.677 reflects that fit-only block, not a disagreement about the exposed accounts (0.870 among urgent accounts, my computation).
- Separation of strong-and-fit from exposed non-buyers: (b) is slightly better. In the top 107, (b) holds 72 S and 2 N; (a) holds 70 S and 4 N. The best-ranked exposed non-buyer (urgency 50 or more, fit 0) sits at rank 102 under (b) and 52 under (a). Beyond rank 200 there is no difference in S or N counts. The gap is small and rests on one placeholder W_F (30); a larger W_F would move (a) toward the (b)-like gating and a smaller one toward urgency-only.
- Fit-only accounts (Z, 178 accounts with urgency 0 and fit 50 or more) reach the top 200 under neither form; at threshold 40, (a) would add 421 accounts to the would-be contact set against 107 under (b), but that is a threshold effect (the scales differ), so thresholds are not transferable between forms.
- Recommendation: keep (b). Reasons from the data: it keeps accounts without exposure at 0 (right for "who needs help now"; 77% of accounts have no urgency), it never lets fit alone create a contact or review account, it ranks fit 0 exposed accounts lower, and its single extra constant (FLOOR 0.5) is easier to explain than a weight W_F that D9 never defined. Cost: both forms depend on the same weak fit_score, and on this sample the choice changes at most 2 of the top 107, so the form matters less than the point table and the operator cap.
