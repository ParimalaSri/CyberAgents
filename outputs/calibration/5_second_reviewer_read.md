# 5. Second-reviewer read of the 107 would-be contacts (band_uncapped = contact, contact_score >= 40); names only, one reviewer; NOT eval ground truth

Method. I read each of the 107 names in order of contact_score (ties by urgency, host count, account id, the stage order) and labelled OPERATOR / ORGANISATION / UNSURE without looking at earlier labels. Names only: host counts and country were printed beside the names but I did not use them, and I did not read ports, tags or other columns. I did use general knowledge of well-known brands (for example Leaseweb, Wowrack, TimeWeb, Telia as hosting or telecom brands; Volcano Engine, Sonic.net, Cruzio as cloud or ISP brands), which is more than the name alone says; a strict names-only read would move some OPERATOR labels to UNSURE and would raise the UNSURE count, not lower it. UNSURE counts as operator for the D7.2a trigger. These labels are my judgement, one reviewer, and are not eval ground truth; nobody should score a classifier against them.

## Counts
| set | n | OPERATOR | UNSURE | ORGANISATION | operator or unsure | share |
|---|---|---|---|---|---|---|
| top 25 by contact_score | 25 | 11 | 9 | 5 | 20 | 80% |
| top 50 | 50 | 21 | 20 | 9 | 41 | 82% |
| all would-be contacts | 107 | 48 | 37 | 22 | 85 | 79% |

Earlier single-reviewer read for the 70 pre-D10 contacts (D10): 20 operator, 37 unsure, 13 organisation. My read of the same kind of set (the 71 would-be contacts that are neither singleton nor operator-shape; the stage's 70 minus one low-confidence difference, so not identical): see below. Counts differ in operator versus unsure because I used brand knowledge for the OPERATOR label; the organisation count is of the same size (13).

- Would-be contacts with no cap besides operator_unverified (not singleton, not operator-shape): 71: OPERATOR 31, UNSURE 27, ORGANISATION 13.
- Singletons (24): OPERATOR 6, UNSURE 9, ORGANISATION 9 (9 of 24 = 38% read as organisations). Non-singletons (83): OPERATOR 42, UNSURE 28, ORGANISATION 13 (13 of 83 = 16%). On names, the singletons are not worse than the multi-host accounts, which is evidence (small n) that the singleton cap does not protect against operators; it protects against one-banner evidence.
- The 13 accounts with the T1 or T2 flag: OPERATOR 12, UNSURE 1, ORGANISATION 0 (flag precision on this set: 12 of 13 operators, 0 organisations). Of my 48 OPERATOR labels the flag catches 12 (25%); the other 36 carry no flagged word.

## D7.2a trigger
Top 50 by contact_score: 41 operator or unsure (limit 5): **trips** (41 of 50 = 82%). Same measure on all 107: 85 of 107 (79%). Earlier reads: 43 of 50 (86%) in D10; mine 41 of 50 (82%). The trigger is far beyond the limit under either read, so the operator gate (D10) is justified and the metric must be measured on the adjudicated list, not on this one.

## Names classed ORGANISATION (22 of 107; rank, name, score)
- 1. Beijing Jingdong 360 Degree E-commerce Co., Ltd. (68; 8 hosts, CN)
- 3. NCR Corporation (68; 24 hosts, US)
- 5. HEWLETT PACKARD ENTERPRISE COMPANY (60; 4 hosts, US)
- 9. U.S. Marshals Service in accordance with the Final Order of Forfeiture (56; 5 hosts, US)
- 18. Office of Info.Tech. Admin. for Educational Development (51; 26 hosts, TH)
- 38. University of California at Berkeley (45; 5 hosts, US)
- 47. University of Utah (45; 10 hosts, US)
- 49. University of Florida (45; 8 hosts, US)
- 50. The Prudential Insurance Company of America (45; 58 hosts, US)
- 54. Comodo Group Inc. (44; 1 hosts, US)
- 66. Martin-Luther-Universitaet Halle-Wittenberg (42; 11 hosts, DE)
- 79. Community of Hope - Health Clinic (41; 1 hosts, US)
- 81. BitTorrent, Inc (41; 1 hosts, US)
- 83. TRILLIUM STAFFING (41; 1 hosts, US)
- 85. Compass Group USA, Inc. (41; 1 hosts, US)
- 86. Amazing Creations and More LLC (41; 1 hosts, US)
- 87. Fujitsu Microelectronics (41; 1 hosts, US)
- 89. University of Colorado (41; 1 hosts, US)
- 90. Dream Entertainment LLC (41; 1 hosts, US)
- 96. ASSETWORKS (41; 5 hosts, US)
- 97. Georgia-Pacific LLC (41; 5 hosts, US)
- 100. Digital Watchdog (41; 2 hosts, US)

Of these, 9 are in the top 50 (ranks 1, 3, 5, 9, 18, 38, 47, 49, 50). Caveats: UC Berkeley, University of Utah, University of Florida and University of Colorado may be network or hosting address blocks of a university (the owner's ICP says whether education is a segment; context/icp.md is still blank). Comodo Group is a security vendor (D2 says security vendors are excluded, not kept; the denylist did not catch it). BitTorrent, Inc is a peer-to-peer company whose hosts may be a network. NCR, HPE, Fujitsu and JD.com are very large firms whose estate on a scan may be partly infrastructure.

## Duplicates among top accounts (D9.2)
- Top 50: PDR (rank 20) and P.D.R Solutions FZC (rank 19), both US, both 9 hosts, score 50: one company under two names (a duplicate pair). Leaseweb Deutschland GmbH (rank 6) and Leaseweb USA, Inc. (rank 46): same group, two accounts. Also in the top 107: LeaseWeb Netherlands B.V. (rank 61), so Leaseweb appears 3 times. Further possible same-group pairs: Aruba S.p.A. (rank 8) is a single account; Beijing Jingdong and Beijing Volcano Engine are different companies; Atlantic.Net, Tier.Net are separate. Duplicates in the top 50: 2 pairs (4 accounts for 2 companies). That is the D9.2 reopen condition ('reopen only if the hand read of the top 50 shows duplicate accounts'); I report it, the owner and senior engineer decide.

## Full list with my labels (ordered; name, score, hosts, country, flag, label)
| # | name | score | hosts | cc | op-shape flag | label |
|---|---|---|---|---|---|---|
| 1 | Beijing Jingdong 360 Degree E-commerce Co., Ltd. | 68 | 8 | CN |  | ORGANISATION |
| 2 | Wowrack.com | 68 | 2 | US |  | OPERATOR |
| 3 | NCR Corporation | 68 | 24 | US |  | ORGANISATION |
| 4 | Strato Rechenzentrum, Berlin | 60 | 15 | DE | T | OPERATOR |
| 5 | HEWLETT PACKARD ENTERPRISE COMPANY | 60 | 4 | US |  | ORGANISATION |
| 6 | Leaseweb Deutschland GmbH | 59 | 6 | DE |  | OPERATOR |
| 7 | Eonix Corporation | 58 | 10 | US |  | UNSURE |
| 8 | Aruba S.p.A. - Cloud Services Farm2 | 57 | 11 | IT | T | OPERATOR |
| 9 | U.S. Marshals Service in accordance with the Final Order of  | 56 | 5 | US |  | ORGANISATION |
| 10 | Interserver, Inc | 54 | 16 | US | T | OPERATOR |
| 11 | Brander Group Inc | 54 | 17 | US |  | UNSURE |
| 12 | Register.com, Inc | 53 | 5 | US |  | UNSURE |
| 13 | Aventice LLC | 53 | 5 | US |  | UNSURE |
| 14 | High Family Technology Co., Limited | 53 | 2 | US |  | UNSURE |
| 15 | Telia Eesti AS | 52 | 13 | EE |  | OPERATOR |
| 16 | Beijing Volcano Engine Technology Co., Ltd. | 52 | 11 | CN |  | OPERATOR |
| 17 | SOLLUTIUM EU Sp z.o.o. | 51 | 5 | UA |  | UNSURE |
| 18 | Office of Info.Tech. Admin. for Educational Development | 51 | 26 | TH |  | ORGANISATION |
| 19 | P.D.R Solutions FZC | 50 | 9 | US |  | UNSURE |
| 20 | PDR | 50 | 9 | US |  | UNSURE |
| 21 | ReliableSite.Net LLC | 50 | 8 | US |  | OPERATOR |
| 22 | Nocix, LLC | 49 | 5 | US |  | OPERATOR |
| 23 | Webzilla Inc. | 49 | 3 | US |  | OPERATOR |
| 24 | CloudRadium L.L.C | 47 | 16 | US | T | OPERATOR |
| 25 | Fastmos Co Limited | 47 | 5 | HK |  | UNSURE |
| 26 | ANX Holding GmbH | 47 | 2 | DE |  | UNSURE |
| 27 | ServerHub Phoenix | 47 | 1 | US |  | OPERATOR |
| 28 | CLOSE UP S.A. | 47 | 1 | US |  | UNSURE |
| 29 | WholeSale Internet, Inc. | 47 | 7 | US | T | OPERATOR |
| 30 | Integen, Inc | 46 | 3 | HK |  | UNSURE |
| 31 | FEDERAL ONLINE GROUP LLC | 46 | 3 | HK |  | UNSURE |
| 32 | OPTAGE Inc. | 46 | 19 | JP |  | OPERATOR |
| 33 | xTom GmbH | 46 | 16 | DE |  | OPERATOR |
| 34 | Digital Core Technology Co., Limited | 46 | 15 | HK |  | UNSURE |
| 35 | TimeWeb Ltd. | 46 | 11 | RU |  | OPERATOR |
| 36 | TT DOTCOM SDN BHD | 46 | 8 | MY |  | UNSURE |
| 37 | computer company | 45 | 5 | US |  | UNSURE |
| 38 | University of California at Berkeley | 45 | 5 | US |  | ORGANISATION |
| 39 | DataWeb Global Group B.V. | 45 | 4 | US |  | UNSURE |
| 40 | Atlantic.Net - New York, NY | 45 | 4 | US |  | OPERATOR |
| 41 | Mohammed Jassim bin Jassim Al-Abd Rab Al-Nabi trading as Vis | 45 | 3 | US |  | UNSURE |
| 42 | Gameserverkings | 45 | 3 | US |  | OPERATOR |
| 43 | Cruzio | 45 | 3 | US |  | OPERATOR |
| 44 | Nexeon Technologies, Inc. | 45 | 2 | US |  | UNSURE |
| 45 | Sharktech | 45 | 2 | US |  | OPERATOR |
| 46 | Leaseweb USA, Inc. | 45 | 19 | US |  | OPERATOR |
| 47 | University of Utah | 45 | 10 | US |  | ORGANISATION |
| 48 | Tier.Net Technologies LLC | 45 | 8 | US |  | UNSURE |
| 49 | University of Florida | 45 | 8 | US |  | ORGANISATION |
| 50 | The Prudential Insurance Company of America | 45 | 58 | US |  | ORGANISATION |
| 51 | Private Customer - AT&T Internet Services | 44 | 16 | US | T | OPERATOR |
| 52 | IT7 Networks Inc | 44 | 9 | US | T | OPERATOR |
| 53 | LIWEST Kabelmedien GmbH | 44 | 3 | AT |  | OPERATOR |
| 54 | Comodo Group Inc. | 44 | 1 | US |  | ORGANISATION |
| 55 | Cellcom Fixed Line Communication L.P | 43 | 4 | IL |  | OPERATOR |
| 56 | Hotwire Communications | 42 | 4 | US | T | OPERATOR |
| 57 | HopOne Internet Corporation | 42 | 2 | US | T | OPERATOR |
| 58 | Dattatec Corp | 42 | 19 | AR |  | OPERATOR |
| 59 | WorldStream B.V. | 42 | 17 | NL |  | OPERATOR |
| 60 | Beget LLC | 42 | 17 | RU |  | OPERATOR |
| 61 | LeaseWeb Netherlands B.V. | 42 | 17 | NL |  | OPERATOR |
| 62 | TIM S.A. | 42 | 14 | BR |  | OPERATOR |
| 63 | ONO_HFC | 42 | 13 | ES |  | OPERATOR |
| 64 | 3NT SOLUTIONS LLP | 42 | 13 | AT |  | UNSURE |
| 65 | Green Floid LLC | 42 | 12 | CH |  | UNSURE |
| 66 | Martin-Luther-Universitaet Halle-Wittenberg | 42 | 11 | DE |  | ORGANISATION |
| 67 | Aeza International LTD | 42 | 8 | DE |  | OPERATOR |
| 68 | Future Spirits Co.,Ltd. | 42 | 7 | JP |  | UNSURE |
| 69 | DIX Co., Ltd. | 42 | 6 | JP |  | UNSURE |
| 70 | TransIP B.V. | 42 | 6 | NL |  | OPERATOR |
| 71 | ANS ACADEMY LIMITED | 42 | 6 | GB |  | UNSURE |
| 72 | Zillion Network Inc | 41 | 12 | US | T | UNSURE |
| 73 | Ziply Fiber | 41 | 11 | US | T | OPERATOR |
| 74 | SQUARK SARL | 41 | 4 | FR |  | UNSURE |
| 75 | Tata Teleservices Maharashtra Ltd | 41 | 3 | IN |  | OPERATOR |
| 76 | IPX Tech Holding LLC | 41 | 1 | US |  | UNSURE |
| 77 | MINIUM NET LLC | 41 | 1 | US |  | UNSURE |
| 78 | ITGLOBAL.COM NL B.V. | 41 | 1 | US |  | UNSURE |
| 79 | Community of Hope - Health Clinic | 41 | 1 | US |  | ORGANISATION |
| 80 | SnTHostings | 41 | 1 | US |  | OPERATOR |
| 81 | BitTorrent, Inc | 41 | 1 | US |  | ORGANISATION |
| 82 | New Metrics | 41 | 1 | US |  | UNSURE |
| 83 | TRILLIUM STAFFING | 41 | 1 | US |  | ORGANISATION |
| 84 | INTERJ LLC | 41 | 1 | US |  | UNSURE |
| 85 | Compass Group USA, Inc. | 41 | 1 | US |  | ORGANISATION |
| 86 | Amazing Creations and More LLC | 41 | 1 | US |  | ORGANISATION |
| 87 | Fujitsu Microelectronics | 41 | 1 | US |  | ORGANISATION |
| 88 | West Technology Group, LLC | 41 | 1 | US |  | UNSURE |
| 89 | University of Colorado | 41 | 1 | US |  | ORGANISATION |
| 90 | Dream Entertainment LLC | 41 | 1 | US |  | ORGANISATION |
| 91 | DataSpindle | 41 | 1 | US |  | UNSURE |
| 92 | WideOpenWest Finance LLC | 41 | 1 | US |  | OPERATOR |
| 93 | Voxility LLP | 41 | 1 | US |  | OPERATOR |
| 94 | Sonic.net, Inc. | 41 | 1 | US |  | OPERATOR |
| 95 | CHL | 41 | 1 | US |  | UNSURE |
| 96 | ASSETWORKS | 41 | 5 | US |  | ORGANISATION |
| 97 | Georgia-Pacific LLC | 41 | 5 | US |  | ORGANISATION |
| 98 | Cyber Wurx LLC | 41 | 2 | US |  | UNSURE |
| 99 | New York Connect | 41 | 2 | US |  | UNSURE |
| 100 | Digital Watchdog | 41 | 2 | US |  | ORGANISATION |
| 101 | WEBSITEWELCOME.COM | 41 | 11 | US |  | OPERATOR |
| 102 | Mega Cable, S.A. de C.V. | 40 | 17 | MX | T | OPERATOR |
| 103 | Virtuo Networks France SAS | 40 | 1 | FR | T | OPERATOR |
| 104 | Beanfield Technologies Inc. | 40 | 3 | CA |  | OPERATOR |
| 105 | G-Core Labs S.A. | 40 | 3 | LU |  | OPERATOR |
| 106 | Keliweb S.R.L | 40 | 2 | IT |  | OPERATOR |
| 107 | CtrlS | 40 | 2 | IN |  | OPERATOR |