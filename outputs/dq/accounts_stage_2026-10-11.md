# Accounts stage report (2026-10-11)

**PROVISIONAL CONSTANTS: not calibrated, not owner-approved.** Points, FLOOR, thresholds and the T1-only penalty are the D9.7 starting point, used so the stage can be exercised; read no band here as a decision. Contact form: (b), FLOOR 0.50, X = 40, Y = 20.

## 1. Row counts

signals 5,790 = accounts 5,790 (asserted; account_id unique, equal to company_id). Output: D:/CyberAgents/data/gold/accounts.parquet.

## 2. Score distributions (score_distribution.py)

```
fit_score: n=5,790 min=0 max=85 mean=11.46
  p5   0.00
  p25  0.00
  p50  0.00
  p75  15.00
  p90  35.00
  p95  50.00
  p99  65.00

histogram:
      0.0+ | ######################################## 3,640
      8.5+ | ######## 717
     17.0+ | # 73
     25.5+ | ## 162
     34.0+ | ######### 855
     42.5+ | ### 251
     51.0+ | # 5
     59.5+ | # 66
     68.0+ | # 1
     76.5+ | # 20
```
```
urgency_score: n=5,790 min=0 max=100 mean=7.14
  p5   0.00
  p25  0.00
  p50  0.00
  p75  0.00
  p90  40.00
  p95  60.00
  p99  65.00

histogram:
      0.0+ | ######################################## 4,930
     10.0+ | # 148
     20.0+ | # 46
     30.0+ | # 4
     40.0+ | # 130
     50.0+ | ## 235
     60.0+ | ## 244
     70.0+ | # 40
     80.0+ | # 8
     90.0+ | # 5
```
```
contact_score: n=5,790 min=0 max=75 mean=4.19
  p5   0.00
  p25  0.00
  p50  0.00
  p75  0.00
  p90  25.00
  p95  30.00
  p99  43.11

histogram:
      0.0+ | ######################################## 5,014
      7.5+ | # 102
     15.0+ | # 66
     22.5+ | ## 212
     30.0+ | ## 255
     37.5+ | # 87
     45.0+ | # 39
     52.5+ | # 9
     60.0+ | # 2
     67.5+ | # 4
```
Accounts scoring above 0: contact 1,324 (22.87%), urgency 1,324 (22.87%), fit 2,271 (39.22%).

## 3. Bands at contact >= 40, review >= 20 (PROVISIONAL)

| band | accounts | share |
|---|---|---|
| contact | 70 | 1.21% |
| review | 594 | 10.26% |
| skip | 5,125 | 88.51% |
| exclude | 1 | 0.02% |

### Threshold previews against the senior's provisional run (D9.8, ad hoc, T1 plus T2 penalty)

| contact / review thresholds | this stage: contact / review / skip / exclude | senior: same order | difference |
|---|---|---|---|
| 45 / 25 | 43 / 538 / 5,208 / 1 | 43 / 530 / 5,216 / 1 | +0 / +8 / -8 / +0 |
| 40 / 20 | 70 / 594 / 5,125 / 1 | 71 / 593 / 5,125 / 1 | -1 / +1 / +0 / +0 |
| 35 / 15 | 136 / 538 / 5,115 / 1 | 138 / 536 / 5,115 / 1 | -2 / +2 / +0 / +0 |

### Cap effects (at 40 / 20)

Would-be contacts (band_uncapped = contact, not excluded): 111; moved to review by a cap: 41; remain contact: 70.
| cap reason (accounts carrying it; some carry two or three) | accounts |
|---|---|
| operator_name_shape | 17 |
| singleton | 26 |
| low_confidence | 4 |

By exact reason set: singleton = 20; operator_name_shape = 14; operator_name_shape,singleton = 3; low_confidence,singleton = 3; low_confidence = 1.

### Review band composition (at 40 / 20)

| review accounts | value | senior (40 / 20) |
|---|---|---|
| total | 594 | 593 |
| reached by a cap (was contact) | 41 | 37 |
| reached by threshold alone | 553 | 556 |
| singletons | 325 | 325 |
| operator-shaped (T1 or T2) | 187 | 187 |
| low identity confidence | 21 | 21 |
| country US | 125 | 125 |

Exclude band (D9.3 rule, noise_host_count >= 2 AND noise_host_share >= 0.5): 1 account(s): SC Lithuanian Radio and TV Center (2 hosts, 3 noise rows, share 0.60).

## 4. Top 25 accounts by contact_score

| company | cc | hosts | fit | urgency | contact | band | cap_reasons | T1 | T2 | why |
|---|---|---|---|---|---|---|---|---|---|---|
| Strato Rechenzentrum, Berlin | DE | 15 | 50 | 100 | 75 | review | operator_name_shape | False | True | 1 host with a vulnerability on the CISA known-exploited list; an exposed admin or database service (SSH 22, MySQL 3306) on outdated software. Name looks like a network operator. |
| Beijing Jingdong 360 Degree E-commerce Co., Ltd. | CN | 8 | 50 | 90 | 68 | contact |  | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; an exposed admin or database service (SSH 22, MongoDB 27017) on outdated software. |
| Wowrack.com | US | 2 | 50 | 90 | 68 | contact |  | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. |
| NCR Corporation | US | 24 | 80 | 75 | 68 | contact |  | False | False | 1 host with a vulnerability on the CISA known-exploited list; 24 IPs in the footprint. |
| Interserver, Inc | US | 16 | 65 | 80 | 66 | review | operator_name_shape | False | True | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Name looks like a network operator. |
| HEWLETT PACKARD ENTERPRISE COMPANY | US | 4 | 50 | 80 | 60 | contact |  | False | False | Worst vulnerability scores CVSS 9.8; hosts located in US. |
| Leaseweb Deutschland GmbH | DE | 6 | 30 | 90 | 59 | contact |  | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; an exposed admin or database service (SSH 22) on outdated software. |
| CloudRadium L.L.C | US | 16 | 65 | 70 | 58 | review | operator_name_shape | False | True | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Name looks like a network operator. |
| Eonix Corporation | US | 10 | 65 | 70 | 58 | contact |  | False | False | Worst vulnerability scores CVSS 9.8; hosts located in US. |
| Aruba S.p.A. - Cloud Services Farm2 | IT | 11 | 20 | 95 | 57 | review | operator_name_shape | True | True | 3 hosts with a vulnerability on the CISA known-exploited list; an exposed admin or database service (MongoDB 27017) on outdated software. Name looks like a network operator. |
| U.S. Marshals Service in accordance with the Final Order of Forfeiture | US | 5 | 50 | 75 | 56 | contact |  | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. |
| Brander Group Inc | US | 17 | 65 | 65 | 54 | contact |  | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. |
| Register.com, Inc | US | 5 | 50 | 70 | 53 | contact |  | False | False | Worst vulnerability scores CVSS 9.8; hosts located in US. |
| Aventice LLC | US | 5 | 50 | 70 | 53 | contact |  | False | False | Worst vulnerability scores CVSS 9.8; hosts located in US. |
| High Family Technology Co., Limited | US | 2 | 50 | 70 | 53 | contact |  | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. |
| Telia Eesti AS | EE | 13 | 30 | 80 | 52 | contact |  | False | False | Worst vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. |
| Beijing Volcano Engine Technology Co., Ltd. | CN | 11 | 30 | 80 | 52 | contact |  | False | False | Worst vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. |
| SOLLUTIUM EU Sp z.o.o. | UA | 5 | 35 | 75 | 51 | contact |  | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; database, medical or IoT systems in the stack. |
| Office of Info.Tech. Admin. for Educational Development | TH | 26 | 45 | 70 | 51 | contact |  | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; 26 IPs in the footprint. |
| Ziply Fiber | US | 11 | 65 | 60 | 50 | review | operator_name_shape | False | True | 3 hosts with a vulnerability on the CISA known-exploited list; hosts located in US. Name looks like a network operator. |
| P.D.R Solutions FZC | US | 9 | 65 | 60 | 50 | contact |  | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; hosts located in US. |
| PDR | US | 9 | 65 | 60 | 50 | contact |  | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. |
| ReliableSite.Net LLC | US | 8 | 65 | 60 | 50 | contact |  | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. |
| ChinaTelecom Group Beijing Ltd,Co | CN | 9 | 30 | 75 | 49 | review | operator_name_shape | False | True | Worst vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Name looks like a network operator. |
| Nocix, LLC | US | 5 | 50 | 65 | 49 | contact |  | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. |

Of the top 25, 6 carry the operator-name flag (T1 or T2; T1 alone 1). A by-eye read of the names (not a rule, not acted on) follows in section 7.

## 5. Output file

Path: D:/CyberAgents/data/gold/accounts.parquet; rows: 5,790; columns: 17. Previous layer (signals rows): 5,790; difference 0 (asserted: one row per company, account_id unique, no fan-out, no drop).

Columns: account_id VARCHAR, company_name VARCHAR, country_code VARCHAR, host_count INTEGER, identity_source VARCHAR, identity_confidence VARCHAR, fit_score INTEGER, urgency_score INTEGER, contact_score INTEGER, top_signals VARCHAR, band_uncapped VARCHAR, cap_reasons VARCHAR, band VARCHAR, why VARCHAR, decision VARCHAR, prompt_version VARCHAR, final_band VARCHAR.

Asserted in the run: scores within 0 to 100; every account has a band, band_uncapped and a non-empty why; final_band = band; decision and prompt_version all null (LLM adjudication is a later milestone); FLOOR * urgency <= contact_score <= urgency (rounding tolerance 0.5).

Null rates (all columns, worst first):

| column | null rate |
|---|---|
| decision | 100.0% |
| prompt_version | 100.0% |
| cap_reasons | 99.29% |
| top_signals | 77.15% |
| account_id | 0.0% |
| company_name | 0.0% |
| country_code | 0.0% |
| host_count | 0.0% |
| identity_source | 0.0% |
| identity_confidence | 0.0% |
| fit_score | 0.0% |
| urgency_score | 0.0% |
| contact_score | 0.0% |
| band_uncapped | 0.0% |
| band | 0.0% |
| why | 0.0% |
| final_band | 0.0% |

5 random rows:

- [1] account_id=ad01cad645328719, company_name=Gmina Lublin, country_code=PL, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=45, contact_score=23, top_signals=max_cvss_band,legacy_tls, band_uncapped=review, cap_reasons=None, band=review, why=Worst vulnerability scores CVSS 9.8; 1 host still offering old TLS ver, decision=None, prompt_version=None, final_band=review
- [2] account_id=179d9e945ff271c2, company_name=Network Block is for the use of STPI-Bangalore, SOFTNET-IN, country_code=IN, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [3] account_id=353e8bddd2c14749, company_name=EUserv Internet, country_code=DE, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [4] account_id=5160becd2ac5a7b2, company_name=XFone 018 Ltd, country_code=IL, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [5] account_id=8e3e58cb55205cef, company_name=Link Egypt, country_code=EG, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip

## 6. Verification run by the data-engineer (not a validation; data-quality-engineer validates)

- `python scripts/verify_4_score.py` (independent plain-Python recompute written from D9.6/D9.7, own constants, no import of the stage): 200 random companies (seed 2026) + top 25 + all exclude rows = 226 checked, 0 disagreements; `--all` (all 5,790) 0 disagreements; sort order `contact_score DESC, urgency_score DESC, host_count DESC, account_id` holds.
- Checked per company: fit, urgency, contact, band_uncapped, cap_reasons, band, top_signals (stage list must equal the independent top two or its first element when the 40-word fallback applies), why non-empty, at most 40 words, no `=`, no `_`, none of breach/compromised/hacked, final_band = band, decision and prompt_version null, `urgency/2 - 0.5 <= contact <= urgency`, no capped account in contact.
- Longest `why` on the sample: 29 words (limit 40); the one-signal fallback never fired on real data.

## 7. Top 25 read by eye (names only, one reviewer, not a rule, not acted on)

Operators with confidence (15): Strato Rechenzentrum, Wowrack.com, Interserver, Leaseweb Deutschland, CloudRadium, Eonix, Aruba Cloud Services Farm2, Brander Group, Register.com, Telia Eesti, Volcano Engine, Ziply Fiber, ReliableSite.Net, ChinaTelecom Group Beijing, Nocix. Unsure (5): Aventice, High Family Technology, SOLLUTIUM EU, P.D.R Solutions FZC, PDR. Read as real organisations (5): Beijing Jingdong 360 Degree E-commerce, NCR, Hewlett Packard Enterprise, U.S. Marshals Service, the Thai Office of Info.Tech. Admin. for Educational Development.
The operator-name flag (T1 or T2) catches 6 of the 15 (Strato, Interserver, CloudRadium, Aruba, Ziply, ChinaTelecom); 9 of the 15 are in the `contact` band (Wowrack, Leaseweb, Eonix, Brander, Register.com, Telia, Volcano, ReliableSite, Nocix). The D7.2a trigger (more than 5 of the top 50 read as operators) is already exceeded inside the top 25.

## 8. Differences from the senior's provisional run (D9.8) and why

Measured by recomputing with the independent implementation under both penalty rules (ad hoc, scratch):
- Penalty on the T1-or-T2 union (the D9.8 run): 45/25 gives 43 / 530 / 5,216 / 1 (identical to the senior); 40/20 gives 70 / 594 / 5,125 / 1 with 107 would-be contacts and 37 moved by caps (senior 108 and 37); 35/15 gives 136 / 538 / 5,115 / 1 (senior 138 / 536). Residual vs senior: 1 account at 40/20 and 2 at 35/15 sit in review here and in contact there (contact plus review totals are equal: 664 and 674). Not explained; the senior's code is not available, a one-account point-table difference near the threshold is the likely cause. Rounding was ruled out (half-up, half-even, ceil, floor give the same counts at 40/20).
- This stage (penalty on T1 only, as instructed): the band counts differ from the union run only in the review/skip split at 45/25 (538 vs 530: 8 T2-only operators keep their fit, so they score 25 or more) and in the cap counts at 40/20 (111 would-be contacts and 41 moved vs 107 and 37: 4 T2-only operators now reach 40 and the operator cap moves them to review). `contact` stays 70. The cap still uses the T1-or-T2 union, so no T2 operator reaches contact; T1-only only changes who is in review and how many contacts the caps remove.
