# 1. Distributions and shapes (PROVISIONAL constants; sample 5,790 accounts)

## fit_score
- above 0: 2,187 (37.77%); distinct values: 14; max 85
- quantiles p50/p75/p90/p95/p99: [0.0, 15.0, 35.0, 50.0, 65.0]

Value histogram (positive values, bin width 5, one # per 10 accounts, bins with counts):
```
  5-9     173 #################
 15-19    649 ################################################################
 20-24     98 #########
 25-29      2 #
 30-34    146 ##############
 35-39    807 ################################################################################
 45-49      6 #
 50-54    219 #####################
 55-59      4 #
 65-69     62 ######
 70-74      1 #
 80-84     19 #
 85-89      1 #
```
Most common positive values (value, count): [(35, 807), (15, 649), (50, 219), (5, 173), (30, 146), (20, 98), (65, 62), (80, 19)]

## urgency_score
- above 0: 1,324 (22.87%); distinct values: 20; max 100
- quantiles p50/p75/p90/p95/p99: [0.0, 0.0, 40.0, 60.0, 65.0]

Value histogram (positive values, bin width 5, one # per 10 accounts, bins with counts):
```
  5-9     464 ##############################################
 10-14     89 ########
 15-19     59 #####
 20-24     14 #
 25-29     32 ###
 30-34      2 #
 35-39      2 #
 40-44    118 ###########
 45-49     12 #
 50-54    192 ###################
 55-59     43 ####
 60-64    197 ###################
 65-69     47 ####
 70-74     34 ###
 75-79      6 #
 80-84      8 #
 90-94      3 #
 95-99      1 #
100-104     1 #
```
Most common positive values (value, count): [(5, 464), (60, 197), (50, 192), (40, 118), (10, 89), (15, 59), (65, 47), (55, 43)]

## contact_score
- above 0: 1,324 (22.87%); distinct values: 56; max 68
- quantiles p50/p75/p90/p95/p99: [0.0, 0.0, 23.0, 30.0, 42.0]

Value histogram (positive values, bin width 5, one # per 10 accounts, bins with counts):
```
  0-4     462 ##############################################
  5-9     129 ############
 10-14     59 #####
 15-19     10 #
 20-24     91 #########
 25-29    183 ##################
 30-34    191 ###################
 35-39     92 #########
 40-44     57 #####
 45-49     29 ##
 50-54     12 #
 55-59      4 #
 60-64      2 #
 65-69      3 #
```
Most common positive values (value, count): [(3, 424), (30, 125), (25, 110), (20, 58), (5, 54), (35, 44), (4, 38), (33, 32)]

Counts at and around thresholds (value: accounts): [(15, 3), (17, 1), (18, 1), (19, 5), (20, 58), (21, 6), (23, 24), (24, 3), (25, 110), (26, 14), (27, 13), (28, 16), (29, 30), (30, 125), (31, 1), (32, 11), (33, 32), (34, 22), (35, 44), (36, 7), (37, 13), (38, 17), (39, 11), (40, 6), (41, 30), (42, 16), (43, 1), (44, 4), (45, 14)]

## Urgency point table concentration (urgency_score > 0)

Top urgency values (value, count): [(5, 464), (60, 197), (50, 192), (40, 118), (10, 89), (15, 59), (65, 47), (55, 43), (70, 34), (25, 32), (20, 14), (45, 12)]

Positive-urgency accounts: 1324. Distinct positive urgency values: 19

Fit_score value table (all accounts):  [(0, 3603), (5, 173), (15, 649), (20, 98), (25, 2), (30, 146), (35, 807), (45, 6), (50, 219), (55, 4), (65, 62), (70, 1), (80, 19), (85, 1)]

Fit by group: in_territory (placeholder US) true=1346; footprint_band>0=1560; sensitive=55; operator_name_shape=1438

Fit=0 share of accounts with urgency>0: (671, 1324)

Contact score by fit (urgency>0): [(0, 671, 3, 40), (5, 28, 3, 37), (15, 206, 3, 46), (20, 37, 3, 60), (30, 85, 3, 59), (35, 167, 3, 54), (45, 2, 4, 51), (50, 88, 4, 68), (55, 4, 12, 47), (65, 29, 4, 58), (70, 1, 34, 34), (80, 6, 5, 68)]

Correlation fit vs urgency (all): 0.104; among urgency>0: 0.021

## What looks wrong or fragile (analyst reading)
- Urgency has 19 distinct positive values and four bulk values: 5 (SSH only or cert/legacy alone, 464 accounts, 35% of urgent accounts), 40, 50, 60 (118, 192, 197). The vulnerability component (KEV 50 vs CVSS-3 40) plus 10 EOL creates these steps; the table is coarse, so a 5-point threshold move shifts whole blocks, not single accounts.
- Contact score has 56 distinct values but pile-ups: 424 accounts at 3 (urgency 5 x floor 0.5, rounded), 125 at 30, 110 at 25, 58 at 20. Thresholds 20, 25 and 30 sit exactly on tie piles, so moving the review threshold from 20 to 25 or 25 to 30 changes the band of 58, 110 and 125 accounts at once (see step 2). 40 is lightly populated (6 at exactly 40; 30 at 41), a comparatively stable edge.
- Fit has 14 distinct values; 3,603 accounts (62.2%) are at 0 (61.6% was reported before the D10 union penalty; the union penalty makes more accounts clip to 0). Fit is two plateaus: 35 (807, territory plus footprint 1) and 15 (649, footprint band 1 only). It is almost a territory flag (placeholder US) plus a footprint flag; correlation with urgency is 0.104 overall and 0.021 among urgent accounts, so fit and urgency are independent and fit does add a separate dimension, but with a placeholder territory it carries no ICP knowledge.
- 671 of the 1,324 urgent accounts (50.7%) have fit 0, so their contact score is exactly urgency x 0.5 (rounded).
