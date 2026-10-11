# Accounts stage report (2026-10-11)

**PROVISIONAL CONSTANTS: not calibrated, not owner-approved.** Points, FLOOR, thresholds and the T1-or-T2 operator penalty (D10, T2 gate pending) are the D9.7 starting point, used so the stage can be exercised; read no band here as a decision. Contact form: (b), FLOOR 0.50, X = 40, Y = 20.

## 1. Row counts

signals 5,790 = accounts 5,790 (asserted; account_id unique, equal to company_id). Output: D:/CyberAgents/data/gold/accounts.parquet.

## 2. Score distributions (score_distribution.py)

```
fit_score: n=5,790 min=0 max=85 mean=10.77
  p5   0.00
  p25  0.00
  p50  0.00
  p75  15.00
  p90  35.00
  p95  50.00
  p99  65.00

histogram:
      0.0+ | ######################################## 3,776
      8.5+ | ####### 649
     17.0+ | # 100
     25.5+ | ## 146
     34.0+ | ######### 807
     42.5+ | ## 225
     51.0+ | # 4
     59.5+ | # 62
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
contact_score: n=5,790 min=0 max=68 mean=4.14
  p5   0.00
  p25  0.00
  p50  0.00
  p75  0.00
  p90  23.00
  p95  30.00
  p99  42.00

histogram:
      0.0+ | ######################################## 4,995
      6.8+ | # 111
     13.6+ | # 78
     20.4+ | # 170
     27.2+ | ## 215
     34.0+ | # 120
     40.8+ | # 78
     47.6+ | # 14
     54.4+ | # 6
     61.2+ | # 3
```
Accounts scoring above 0: contact 1,324 (22.87%), urgency 1,324 (22.87%), fit 2,187 (37.77%).

## 3. Bands at contact >= 40, review >= 20 (PROVISIONAL)

| band | accounts | share |
|---|---|---|
| contact | 0 | 0.00% |
| review | 664 | 11.47% |
| skip | 5,125 | 88.51% |
| exclude | 1 | 0.02% |

### Previous run and the senior's D10 expectation (at 40 / 20)

| band | previous run (pre-D10) | senior's D10 expectation | this run |
|---|---|---|---|
| contact | 70 | 0 | 0 |
| review | 594 | about 660 | 664 |
| skip | 5,125 | about 5,125 | 5,125 |
| exclude | 1 | 1 | 1 |

### Threshold previews (every would-be contact is held in review by operator_unverified)

| contact / review thresholds | this stage: contact / review / skip / exclude | would-be contacts (now in review) |
|---|---|---|
| 45 / 25 | 0 / 573 / 5,216 / 1 | 50 |
| 40 / 20 | 0 / 664 / 5,125 / 1 | 107 |
| 35 / 15 | 0 / 674 / 5,115 / 1 | 199 |

### Cap effects (at 40 / 20)

Would-be contacts (band_uncapped = contact, not excluded): 107; moved to review by a cap: 107; remain contact: 0 (D10: none; only adjudication may set final_band = contact).
| cap reason (accounts carrying it; some carry two or three) | accounts |
|---|---|
| operator_name_shape | 13 |
| singleton | 24 |
| low_confidence | 4 |
| operator_unverified | 107 |

By exact reason set: operator_unverified = 70; operator_unverified,singleton = 20; operator_name_shape,operator_unverified = 12; low_confidence,operator_unverified,singleton = 3; low_confidence,operator_unverified = 1; operator_name_shape,operator_unverified,singleton = 1.

### Review band composition (at 40 / 20)

| review accounts | value | D9.8 pre-D10 (40 / 20) |
|---|---|---|
| total | 664 | 593 |
| reached by a cap (was contact) | 107 | 37 |
| reached by threshold alone | 557 | 556 |
| singletons | 325 | 325 |
| operator-shaped (T1 or T2) | 187 | 187 |
| low identity confidence | 21 | 21 |
| country US | 158 | 125 |

Exclude band (D9.3 rule, noise_host_count >= 2 AND noise_host_share >= 0.5): 1 account(s): SC Lithuanian Radio and TV Center (2 hosts, 3 noise rows, share 0.60).

### Effect of the union penalty (D10) versus the previous T1-only penalty

Accounts whose fit_score fell because the penalty now covers T2-only names: 167 (total 3,990 fit points, mean 23.9 per changed account, max 30); accounts whose contact_score changed: 49.
Of the previous top 25 by contact_score, 2 are no longer in the top 25.
Of the previous top 50 by contact_score, 4 are no longer in the top 50.
Accounts with a different overall rank: 872; largest rank shift among accounts in either top 25: 96.

## 4. Top 25 accounts by contact_score

| company | cc | hosts | fit | urgency | contact | band | cap_reasons | T1 | T2 | why |
|---|---|---|---|---|---|---|---|---|---|---|
| Beijing Jingdong 360 Degree E-commerce Co., Ltd. | CN | 8 | 50 | 90 | 68 | review | operator_unverified | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; an exposed admin or database service (SSH 22, MongoDB 27017) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Wowrack.com | US | 2 | 50 | 90 | 68 | review | operator_unverified | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| NCR Corporation | US | 24 | 80 | 75 | 68 | review | operator_unverified | False | False | 1 host with a vulnerability on the CISA known-exploited list; 24 IPs in the footprint. Not yet checked that this is an end-user organisation, not a network operator. |
| Strato Rechenzentrum, Berlin | DE | 15 | 20 | 100 | 60 | review | operator_name_shape,operator_unverified | False | True | 1 host with a vulnerability on the CISA known-exploited list. Name looks like a network operator. Not yet checked that this is an end-user organisation, not a network operator. |
| HEWLETT PACKARD ENTERPRISE COMPANY | US | 4 | 50 | 80 | 60 | review | operator_unverified | False | False | Worst vulnerability scores CVSS 9.8; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| Leaseweb Deutschland GmbH | DE | 6 | 30 | 90 | 59 | review | operator_unverified | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Eonix Corporation | US | 10 | 65 | 70 | 58 | review | operator_unverified | False | False | Worst vulnerability scores CVSS 9.8; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| Aruba S.p.A. - Cloud Services Farm2 | IT | 11 | 20 | 95 | 57 | review | operator_name_shape,operator_unverified | True | True | 3 hosts with a vulnerability on the CISA known-exploited list; an exposed admin or database service (MongoDB 27017) on outdated software. Name looks like a network operator. Not yet checked that this is an end-user organisation, not a network operator. |
| U.S. Marshals Service in accordance with the Final Order of Forfeiture | US | 5 | 50 | 75 | 56 | review | operator_unverified | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| Interserver, Inc | US | 16 | 35 | 80 | 54 | review | operator_name_shape,operator_unverified | False | True | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Name looks like a network operator. Not yet checked that this is an end-user organisation, not a network operator. |
| Brander Group Inc | US | 17 | 65 | 65 | 54 | review | operator_unverified | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| Register.com, Inc | US | 5 | 50 | 70 | 53 | review | operator_unverified | False | False | Worst vulnerability scores CVSS 9.8; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| Aventice LLC | US | 5 | 50 | 70 | 53 | review | operator_unverified | False | False | Worst vulnerability scores CVSS 9.8; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| High Family Technology Co., Limited | US | 2 | 50 | 70 | 53 | review | operator_unverified | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| Telia Eesti AS | EE | 13 | 30 | 80 | 52 | review | operator_unverified | False | False | Worst vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Beijing Volcano Engine Technology Co., Ltd. | CN | 11 | 30 | 80 | 52 | review | operator_unverified | False | False | Worst vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| SOLLUTIUM EU Sp z.o.o. | UA | 5 | 35 | 75 | 51 | review | operator_unverified | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; database, medical or IoT systems in the stack. Not yet checked that this is an end-user organisation, not a network operator. |
| Office of Info.Tech. Admin. for Educational Development | TH | 26 | 45 | 70 | 51 | review | operator_unverified | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; 26 IPs in the footprint. Not yet checked that this is an end-user organisation, not a network operator. |
| P.D.R Solutions FZC | US | 9 | 65 | 60 | 50 | review | operator_unverified | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| PDR | US | 9 | 65 | 60 | 50 | review | operator_unverified | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| ReliableSite.Net LLC | US | 8 | 65 | 60 | 50 | review | operator_unverified | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| Nocix, LLC | US | 5 | 50 | 65 | 49 | review | operator_unverified | False | False | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| Webzilla Inc. | US | 3 | 50 | 65 | 49 | review | operator_unverified | False | False | 2 hosts with a vulnerability on the CISA known-exploited list; hosts located in US. Not yet checked that this is an end-user organisation, not a network operator. |
| CloudRadium L.L.C | US | 16 | 35 | 70 | 47 | review | operator_name_shape,operator_unverified | False | True | 1 host with a vulnerability on the CISA known-exploited list; hosts located in US. Name looks like a network operator. Not yet checked that this is an end-user organisation, not a network operator. |
| Fastmos Co Limited | HK | 5 | 35 | 70 | 47 | review | operator_unverified | False | False | An exposed admin or database service (MySQL 3306) on outdated software; worst vulnerability scores CVSS 7.2. Not yet checked that this is an end-user organisation, not a network operator. |

Of the top 25, 4 carry the operator-name flag (T1 or T2; T1 alone 1). A by-eye read of the names (not a rule, not acted on) follows in section 7.

## 5. Output file

Path: D:/CyberAgents/data/gold/accounts.parquet; rows: 5,790; columns: 17. Previous layer (signals rows): 5,790; difference 0 (asserted: one row per company, account_id unique, no fan-out, no drop).

Columns: account_id VARCHAR, company_name VARCHAR, country_code VARCHAR, host_count INTEGER, identity_source VARCHAR, identity_confidence VARCHAR, fit_score INTEGER, urgency_score INTEGER, contact_score INTEGER, top_signals VARCHAR, band_uncapped VARCHAR, cap_reasons VARCHAR, band VARCHAR, why VARCHAR, decision VARCHAR, prompt_version VARCHAR, final_band VARCHAR.

Asserted in the run: scores within 0 to 100; every account has a band, band_uncapped and a non-empty why; final_band = band; decision and prompt_version all null and no account in band contact (D10: only LLM adjudication may set final_band = contact); FLOOR * urgency <= contact_score <= urgency (rounding tolerance 0.5).

Null rates (all columns, worst first):

| column | null rate |
|---|---|
| decision | 100.0% |
| prompt_version | 100.0% |
| cap_reasons | 98.15% |
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

- [1] account_id=04d16b45865522c7, company_name=Aruba S.p.A., country_code=CZ, host_count=3, identity_source=org, identity_confidence=high, fit_score=15, urgency_score=40, contact_score=23, top_signals=max_cvss_band,footprint_band, band_uncapped=review, cap_reasons=None, band=review, why=Worst vulnerability scores CVSS 9.8; 3 IPs in the footprint., decision=None, prompt_version=None, final_band=review
- [2] account_id=179d9e945ff271c2, company_name=Network Block is for the use of STPI-Bangalore, SOFTNET-IN, country_code=IN, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [3] account_id=353e8bddd2c14749, company_name=EUserv Internet, country_code=DE, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [4] account_id=5160becd2ac5a7b2, company_name=XFone 018 Ltd, country_code=IL, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [5] account_id=8e3e58cb55205cef, company_name=Link Egypt, country_code=EG, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip

## 6. Verification run by the data-engineer (not a validation; data-quality-engineer validates)

- `python scripts/verify_4_score.py --all` (independent plain-Python recompute written from D9.6, D9.7 and D10, own constants, no import of the stage): 5,790 companies checked, 0 disagreements; the default run (200 random with seed 2026, top 25, all exclude rows = 226) also 0 disagreements; sort order `contact_score DESC, urgency_score DESC, host_count DESC, account_id` holds.
- Checked per company: fit (union penalty), urgency, contact, band_uncapped, cap_reasons (including `operator_unverified` for every would-be contact, sorted), band, top_signals, why non-empty, at most 40 words, no `=`, no `_`, none of breach/compromised/hacked, the D10 clause present exactly when band_uncapped is contact, final_band = band, decision and prompt_version null, `urgency/2 - 0.5 <= contact <= urgency`, no account in contact.
- Longest `why` on the sample: 40 words (limit 40); the one-signal fallback fired for 1 of the 107 would-be contacts (the D10 clause is always kept).
- Unit tests: `python -m unittest scripts.test_1_clean scripts.test_2_companies scripts.test_3_signals scripts.test_4_score`: 83 tests, OK.

## 7. Top 25 read by eye (names only, one reviewer, not a rule, not acted on)

The top 25 holds the same names as before D10 except 2 (the union penalty lowered Ziply Fiber and ChinaTelecom out of it; 2 of the previous top 25 and 4 of the previous top 50 left). Read as real organisations: Beijing Jingdong 360 Degree E-commerce, NCR, Hewlett Packard Enterprise, U.S. Marshals Service, the Thai Office of Info.Tech. Admin. for Educational Development (5). Operators with confidence: Wowrack, Strato Rechenzentrum, Leaseweb, Eonix, Aruba Cloud Services Farm2, Interserver, Brander Group, Register.com, Telia Eesti, Volcano Engine, ReliableSite.Net, Nocix, Webzilla, CloudRadium (14). Unsure: Aventice, High Family Technology, SOLLUTIUM EU, P.D.R Solutions FZC, PDR, Fastmos (6). The operator-name flag now marks 4 of the 25. All 25 are in `review` with `operator_unverified`; none is `contact`, which is the D10 intent.

## 8. Differences from the previous run and from the senior's D10 expectation, and why

- Previous run (T1-only penalty): 70 / 594 / 5,125 / 1 (contact / review / skip / exclude) with 111 would-be contacts. This run (union penalty plus `operator_unverified`): 0 / 664 / 5,125 / 1 with 107 would-be contacts. Review rose by exactly the 70 contacts (594 + 70 = 664); skip and exclude unchanged; the 4 would-be contacts that dropped below 40 (T2-only operators that now lose 30 fit) are still at or above 20, so they sit in review without the cap.
- Senior's expectation: contact 0 (met), review about 660 (664, +4 on an explicitly approximate figure), skip about 5,125 (5,125), exclude 1 (1). The 4 above are the only difference.
- Union penalty: 167 accounts lost fit (15 to 30 points, 3,990 in total, mean 23.9), but 107 of them have urgency 0 so their contact_score stays 0; 49 accounts changed contact_score. Of the previous top 25, 2 left; of the top 50, 4 left.
- Previews: 45 / 25 gives 0 / 573 / 5,216 / 1 (the senior's D9.8 run is 43 + 530 = 573 for contact plus review); 35 / 15 gives 0 / 674 / 5,115 / 1 (138 + 536 = 674, equal); 40 / 20 gives 664 (71 + 593 = 664, equal). The residual of one account between the senior's would-be count (108) and this stage (107) noted before D10 persists and is unexplained.
- Review accounts that reached review by threshold alone (557) carry no operator clause by D10 (the clause is only for would-be contacts); several of them also read as operators (for example MxFiber, KujtesaNET Cable, FDCservers.net).
