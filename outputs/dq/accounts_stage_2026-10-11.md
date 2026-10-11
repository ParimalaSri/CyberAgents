# Accounts stage report (2026-10-11)

**PROVISIONAL CONSTANTS: not calibrated, not owner-approved.** Points, FLOOR, thresholds, N and the T1-or-T2 operator penalty (D10, D11 provisional) are the D9.7 starting point, used so the stage can be exercised; read no band here as a decision. Contact form: (b), FLOOR 0.50, X = 40, Y = 20 (floor of the review band), N = 200, territory points 0 (neutral, D11.5).

## 1. Row counts

signals 5,790 = accounts 5,790 (asserted; account_id unique, equal to company_id). Output: D:/CyberAgents/data/gold/accounts.parquet.

## 2. Score distributions (score_distribution.py)

```
fit_score: n=5,790 min=0 max=65 mean=3.88
  p5   0.00
  p25  0.00
  p50  0.00
  p75  0.00
  p90  15.00
  p95  15.00
  p99  30.00

histogram:
      0.0+ | ######################################## 4,607
     13.0+ | ######## 902
     19.5+ | # 15
     26.0+ | ## 217
     32.5+ | # 17
     39.0+ | # 25
     45.5+ | # 6
     58.5+ | # 1
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
contact_score: n=5,790 min=0 max=68 mean=3.90
  p5   0.00
  p25  0.00
  p50  0.00
  p75  0.00
  p90  23.00
  p95  30.00
  p99  39.00

histogram:
      0.0+ | ######################################## 5,013
      6.8+ | # 98
     13.6+ | # 93
     20.4+ | # 183
     27.2+ | ## 256
     34.0+ | # 106
     40.8+ | # 31
     47.6+ | # 6
     54.4+ | # 3
     61.2+ | # 1
```
Accounts scoring above 0: contact 1,324 (22.87%), urgency 1,324 (22.87%), fit 1,190 (20.55%).

## 3. Bands at contact >= 40, review = would-be contacts plus the top 200 with contact_score >= 20 (PROVISIONAL)

| band | accounts | share |
|---|---|---|
| contact | 0 | 0.00% |
| review | 200 | 3.45% |
| skip | 5,589 | 96.53% |
| exclude | 1 | 0.02% |

### Previous run (D10, threshold-only review) and the senior's D11 expectation (X = 40, Y = 20, N = 200)

| band | previous run (D10) | senior's D11 expectation | this run |
|---|---|---|---|
| contact | 0 | 0 | 0 |
| review | 664 | 200 (N), or the would-be contacts if more | 200 |
| skip | 5,125 | 5,589 (the rest) | 5,589 |
| exclude | 1 | 1 | 1 |

### Review cut (N = 200, floor 20)

The cut falls at contact_score 30: 142 non-excluded accounts are tied at 30, 7 are kept in review and 135 go to skip (tie broken by urgency_score, host_count, account_id; D11 measured score 34 with a tie of 22 before the territory change). Accounts above the cut score: 193.

### Threshold previews (every would-be contact is held in review by operator_unverified; the top-N rule applies at each pair)

| contact / review thresholds | this stage: contact / review / skip / exclude | would-be contacts (now in review) |
|---|---|---|
| 45 / 25 | 0 / 200 / 5,589 / 1 | 21 |
| 40 / 20 | 0 / 200 / 5,589 / 1 | 51 |
| 35 / 15 | 0 / 200 / 5,589 / 1 | 146 |

### Cap effects (at 40 / 20)

Would-be contacts (band_uncapped = contact, not excluded): 51 (D11.5 expected about 51); moved to review by a cap: 51; remain contact: 0 (D10: none; only adjudication may set final_band = contact).

| cap reason (accounts carrying it; some carry two or three) | accounts |
|---|---|
| operator_name_shape | 5 |
| singleton | 1 |
| low_confidence | 0 |
| operator_unverified | 51 |

By exact reason set: operator_unverified = 46; operator_name_shape,operator_unverified = 4; operator_name_shape,operator_unverified,singleton = 1.

### Review band composition (at 40 / 20 / N = 200)

| review accounts | value |
|---|---|
| total | 200 |
| reached by a cap (was contact) | 51 |
| reached by the top-N rule alone | 149 |
| singletons | 22 |
| operator-shaped (T1 or T2) | 42 |
| operator-shaped among the top-N-only rows (get the D11.3 clause) | 37 |
| low identity confidence | 8 |
| country US | 48 |

Exclude band (D9.3 rule, noise_host_count >= 2 AND noise_host_share >= 0.5): 1 account(s): SC Lithuanian Radio and TV Center (2 hosts, 3 noise rows, share 0.60).

Skip accounts with urgency_score above 0, split at the floor Y = 20 (all read "Below the review cut-off." and none is routed to review, D11.3):

| where | skip accounts urgency > 0 | non-SSH admin or database port | CVSS 7.0 or more | both | union |
|---|---|---|---|---|---|
| contact_score below 20 (D11.3 measured 659, 42, 32, 0, 74) | 659 | 42 | 32 | 0 | 74 |
| contact_score 20 or more, beyond the top-N cut | 464 | 9 | 441 | 0 | 450 |

### Effect of the union penalty (D10) versus the previous T1-only penalty

Accounts whose fit_score fell because the penalty now covers T2-only names: 66 (total 1,160 fit points, mean 17.6 per changed account, max 30); accounts whose contact_score changed: 29.
Of the previous top 25 by contact_score, 3 are no longer in the top 25.
Of the previous top 50 by contact_score, 2 are no longer in the top 50.
Accounts with a different overall rank: 644; largest rank shift among accounts in either top 25: 69.

## 4. Top 25 accounts by contact_score

| company | cc | hosts | fit | urgency | contact | band | cap_reasons | T1 | T2 | why |
|---|---|---|---|---|---|---|---|---|---|---|
| Beijing Jingdong 360 Degree E-commerce Co., Ltd. | CN | 8 | 50 | 90 | 68 | review | operator_unverified | False | False | 2 hosts running software whose version matches the CISA known-exploited list; an exposed admin or database service (SSH 22, MongoDB 27017) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Strato Rechenzentrum, Berlin | DE | 15 | 20 | 100 | 60 | review | operator_name_shape,operator_unverified | False | True | 1 host running software whose version matches the CISA known-exploited list. Name looks like a network operator. Not yet checked that this is an end-user organisation, not a network operator. |
| Leaseweb Deutschland GmbH | DE | 6 | 30 | 90 | 59 | review | operator_unverified | False | False | 2 hosts running software whose version matches the CISA known-exploited list; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Aruba S.p.A. - Cloud Services Farm2 | IT | 11 | 20 | 95 | 57 | review | operator_name_shape,operator_unverified | True | True | 3 hosts running software whose version matches the CISA known-exploited list. Name looks like a network operator. Not yet checked that this is an end-user organisation, not a network operator. |
| NCR Corporation | US | 24 | 45 | 75 | 54 | review | operator_unverified | False | False | 1 host running software whose version matches the CISA known-exploited list; 24 IPs in the footprint. Not yet checked that this is an end-user organisation, not a network operator. |
| Wowrack.com | US | 2 | 15 | 90 | 52 | review | operator_unverified | False | False | 1 host running software whose version matches the CISA known-exploited list; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Telia Eesti AS | EE | 13 | 30 | 80 | 52 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Beijing Volcano Engine Technology Co., Ltd. | CN | 11 | 30 | 80 | 52 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| SOLLUTIUM EU Sp z.o.o. | UA | 5 | 35 | 75 | 51 | review | operator_unverified | False | False | 2 hosts running software whose version matches the CISA known-exploited list; database, medical or IoT systems in the stack. Not yet checked that this is an end-user organisation, not a network operator. |
| Office of Info.Tech. Admin. for Educational Development | TH | 26 | 45 | 70 | 51 | review | operator_unverified | False | False | 2 hosts running software whose version matches the CISA known-exploited list; 26 IPs in the footprint. Not yet checked that this is an end-user organisation, not a network operator. |
| Fastmos Co Limited | HK | 5 | 35 | 70 | 47 | review | operator_unverified | False | False | An exposed admin or database service (MySQL 3306) on outdated software; worst version-matched vulnerability scores CVSS 7.2. Not yet checked that this is an end-user organisation, not a network operator. |
| ANX Holding GmbH | DE | 2 | 35 | 70 | 47 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 9.8; an exposed admin or database service (MongoDB 27017) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| HEWLETT PACKARD ENTERPRISE COMPANY | US | 4 | 15 | 80 | 46 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Integen, Inc | HK | 3 | 15 | 80 | 46 | review | operator_unverified | False | False | 1 host running software whose version matches the CISA known-exploited list; an exposed admin or database service (SMB 445) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| FEDERAL ONLINE GROUP LLC | HK | 3 | 15 | 80 | 46 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 10.0; an exposed admin or database service (SMB 445) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| OPTAGE Inc. | JP | 19 | 30 | 70 | 46 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| xTom GmbH | DE | 16 | 30 | 70 | 46 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| Digital Core Technology Co., Limited | HK | 15 | 30 | 70 | 46 | review | operator_unverified | False | False | 1 host running software whose version matches the CISA known-exploited list; 15 IPs in the footprint. Not yet checked that this is an end-user organisation, not a network operator. |
| TimeWeb Ltd. | RU | 11 | 30 | 70 | 46 | review | operator_unverified | False | False | 3 hosts running software whose version matches the CISA known-exploited list; 11 IPs in the footprint. Not yet checked that this is an end-user organisation, not a network operator. |
| Eonix Corporation | US | 10 | 30 | 70 | 46 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| TT DOTCOM SDN BHD | MY | 8 | 30 | 70 | 46 | review | operator_unverified | False | False | Worst version-matched vulnerability scores CVSS 9.8; an exposed admin or database service (SSH 22) on outdated software. Not yet checked that this is an end-user organisation, not a network operator. |
| LIWEST Kabelmedien GmbH | AT | 3 | 35 | 65 | 44 | review | operator_unverified | False | False | An exposed admin or database service (MySQL 3306) on outdated software; worst version-matched vulnerability scores CVSS 7.5. Not yet checked that this is an end-user organisation, not a network operator. |
| U.S. Marshals Service in accordance with the Final Order of Forfeiture | US | 5 | 15 | 75 | 43 | review | operator_unverified | False | False | 1 host running software whose version matches the CISA known-exploited list; remote-admin or database services exposed (RDP 3389). Not yet checked that this is an end-user organisation, not a network operator. |
| Cellcom Fixed Line Communication L.P | IL | 4 | 15 | 75 | 43 | review | operator_unverified | False | False | 1 host running software whose version matches the CISA known-exploited list; remote-admin or database services exposed (Telnet 23). Not yet checked that this is an end-user organisation, not a network operator. |
| Dattatec Corp | AR | 19 | 30 | 65 | 42 | review | operator_unverified | False | False | 1 host running software whose version matches the CISA known-exploited list; 19 IPs in the footprint. Not yet checked that this is an end-user organisation, not a network operator. |

Of the top 25, 2 carry the operator-name flag (T1 or T2; T1 alone 1). A by-eye read of the names (not a rule, not acted on) follows in section 7.

## 5. Output file

Path: D:/CyberAgents/data/gold/accounts.parquet; rows: 5,790; columns: 17. Previous layer (signals rows): 5,790; difference 0 (asserted: one row per company, account_id unique, no fan-out, no drop).

Columns: account_id VARCHAR, company_name VARCHAR, country_code VARCHAR, host_count INTEGER, identity_source VARCHAR, identity_confidence VARCHAR, fit_score INTEGER, urgency_score INTEGER, contact_score INTEGER, top_signals VARCHAR, band_uncapped VARCHAR, cap_reasons VARCHAR, band VARCHAR, why VARCHAR, decision VARCHAR, prompt_version VARCHAR, final_band VARCHAR.

Asserted in the run: scores within 0 to 100; every account has a band, band_uncapped and a non-empty why; final_band = band; decision and prompt_version all null and no account in band contact (D10: only LLM adjudication may set final_band = contact); FLOOR * urgency <= contact_score <= urgency (rounding tolerance 0.5).

Null rates (all columns, worst first):

| column | null rate |
|---|---|
| decision | 100.0% |
| prompt_version | 100.0% |
| cap_reasons | 99.12% |
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

- [1] account_id=e3df186084237423, company_name=Strad Solutions, country_code=IN, host_count=2, identity_source=org, identity_confidence=high, fit_score=15, urgency_score=40, contact_score=23, top_signals=max_cvss_band,footprint_band, band_uncapped=review, cap_reasons=None, band=skip, why=Worst version-matched vulnerability scores CVSS 9.8; 2 IPs in the foot, decision=None, prompt_version=None, final_band=skip
- [2] account_id=179d9e945ff271c2, company_name=Network Block is for the use of STPI-Bangalore, SOFTNET-IN, country_code=IN, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [3] account_id=353e8bddd2c14749, company_name=EUserv Internet, country_code=DE, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [4] account_id=5160becd2ac5a7b2, company_name=XFone 018 Ltd, country_code=IL, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip
- [5] account_id=8e3e58cb55205cef, company_name=Link Egypt, country_code=EG, host_count=1, identity_source=org, identity_confidence=high, fit_score=0, urgency_score=0, contact_score=0, top_signals=None, band_uncapped=skip, cap_reasons=None, band=skip, why=No exposure signal found in the scan (1 host seen)., decision=None, prompt_version=None, final_band=skip

## 6. Verification run by the data-engineer after D11 (not a validation; data-quality-engineer validates)

- `python scripts/verify_4_score.py --all` (independent plain-Python recompute written from D9, D10 and D11, own constants, no import of the stage): 5,790 companies checked, 0 disagreements; the default run (200 random with seed 2026, top 25, exclude rows) also 0; sort order holds. It recomputes fit with territory 0, the rank over non-excluded accounts in the stage order, band (would-be contacts kept, top N = 200 with floor 20), cap_reasons, top_signals, the skip clause, the operator clause on review rows, the KEV and CVSS phrases, and the absence of every pre-D11 phrase.
- Unit tests: `python -m unittest scripts.test_1_clean scripts.test_2_companies scripts.test_3_signals scripts.test_4_score`: 93 tests, OK.
- Every `why`: at most 37 words (limit 40), none with `=`, `_`, "located in", "Exposure is limited" or a breach word. Operator-shaped review rows: 42, all 42 end with "Name looks like a network operator." (5 through the cap clause, 37 through D11.3).
- The report was regenerated by the stage; this section and sections 7 and 8 are hand-added.

## 7. Top 25 read by eye (names only, one reviewer, not a rule, not acted on)

Organisations (5): Beijing Jingdong 360 Degree E-commerce, NCR, Hewlett Packard Enterprise, U.S. Marshals Service, the Thai Office of Info.Tech. Admin. for Educational Development. Operators (14): Strato Rechenzentrum, Leaseweb, Aruba Cloud Services Farm2, Wowrack, Telia Eesti, Volcano Engine, OPTAGE, xTom, TimeWeb, Eonix, TT DOTCOM, LIWEST Kabelmedien, Cellcom Fixed Line, Dattatec. Unsure (6): SOLLUTIUM EU, Fastmos, ANX Holding, Integen, Federal Online Group, Digital Core Technology. The operator-name flag marks 2 of the 25 (Strato, Aruba). All 25 are `review` with `operator_unverified`; none is `contact`. The KEV and CVSS phrases now say "version matches" and "version-matched"; the exposure phrase "on outdated software" is unchanged by D11 and still states "outdated" without "version-matched" (flagged to the senior engineer, not changed).

## 8. Differences from the previous run and from the senior's D11 expectation, and why

- Bands: previous (D10) 0 / 664 / 5,125 / 1; this run 0 / 200 / 5,589 / 1 (contact / review / skip / exclude), as D11.2 expects (N = 200; 664 - 200 = 464 accounts moved from review to skip, which is the 464 accounts at contact_score 20 or more beyond the cut).
- Would-be contacts: 51 (D11.5 expected about 51; was 107 with territory 35).
- Cut: contact_score 30, 142 non-excluded accounts tied at 30, 7 kept, 135 to skip. D11.2 measured score 34 with a tie of 22 before the territory change; the cut score fell by 4 because territory points are now 0 (every in-territory account lost 35 fit points). The tie at the cut is much larger (142, not 22; the cause beyond the territory change was not investigated), so the 7 kept at 30 are chosen by urgency, host count and account id.
- Skip with urgency above 0: 1,123 (659 below the floor, 464 at or above it beyond the cut). Below the floor the D11.3 figures reproduce exactly: 42 with a non-SSH admin or database port, 32 with CVSS 7.0 or more, overlap 0, union 74. The 464 beyond the cut hold 9 + 441 = 450 more such accounts (CVSS 7.0 or more is common among them); they read "Below the review cut-off." and are not routed (D11.3 item 2).
