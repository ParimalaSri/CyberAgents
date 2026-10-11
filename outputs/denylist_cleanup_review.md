# Denylist cleanup review (website builders, generic keywords, isp-field decision)

Date: 2026-10-11. Branch `feat/data-integrator/denylist-cleanup`. Data: `data/sample/spread_100k.jsonl` (read only), 100,000 rows.
Status: PROPOSED. The owner approves anything that goes into CLAUDE.md sections 11 and 12 and the wording of D4 in `docs/ARCHITECTURE.md`
(not edited here). Builds on `outputs/denylist_orgonly_review.md` and `outputs/denylist_accent_folding.md`.
Reminder (RAW-010): `check_contract.py` still applies none of the prefix, pattern or keyword rules; only `scripts/denylist_match.py` does.

## 1. Website builders (D2, owner-approved)
Spellings in the sample: org `Automattic, Inc` 22 rows (isp `Automattic, Inc` 33 rows), org `TUMBLR, INC.` 5 rows. No other WordPress or Tumblr spelling.
Added to `context/denylist_prefixes.txt` as word-boundary prefix families `automattic` and `tumblr` (both 4+ characters). Effect on its own: 27 rows
(2 distinct orgs) newly excluded; infrastructure 89,398 to 89,425. Tests: `Automattic, Inc`, `Automattic Consulting` and `TUMBLR, INC.` match;
`Tumblrfoo Corp` does not (word boundary).

## 2. Weak generic keywords removed (owner, 2026-10-11)
`telephone`, `cable` and `dedicated` removed from `context/denylist_keywords.txt`; `fibre` kept. A comment in the file records the removal as
"ordinary words" with the date. Effect on its own: 162 rows (85 distinct orgs) move from infrastructure to surviving. Tests added: the three words are not
loaded keywords, and `Telephone Answering Service Inc`, `Cable Car Museum`, `Dedicated Staffing LLC` are not matched, `Acme Fibre Networks` still is.
The old tests did not reference these words, so none had to be edited.

## 3. The isp-field question
### 3.1 Set definition
A row is "isp-only excluded" when: no `cloud.provider`, no `cloud`/`cdn` tag, no CIDR pattern hit on its IP, NO exact/prefix/pattern/keyword match on its
`org` text, but a match on its `isp` text (exact, prefix, pattern, or unscoped keyword; org-scoped keywords never match isp). Evaluated after sections 1 and 2.
Example: org `ABTC IMOVEIS LTDA ME`, isp `TELEFONICA BRASIL S.A` (isp exact match) was excluded.

### 3.2 Size
| item | rows | distinct orgs |
|---|---|---|
| isp-only excluded, all | 3,516 | 798 non-null orgs, plus 50 rows with null org |
| of those, non-null org | 3,466 | 798 |

Rule that matched the isp (first match in order exact, prefix, pattern, keyword; non-null-org rows / distinct orgs; the 50 null-org rows add 46 exact and 4 prefix):
| rule | rows | distinct orgs |
|---|---|---|
| exact | 3,331 | 732 |
| keyword | 120 | 64 |
| prefix | 15 | 4 |
| pattern | 0 | 0 |

Top matched isp entries: google 1,683 rows (58 orgs, for example Egnyte 331, Fiserv 329, Wal-Mart 246, Avago 239, TGS Management 148), china unicom china169
backbone 229, ovh 93, amazon com 88, chinanet backbone 88, cogent communications 68, at and t enterprises 62, deutsche telekom 56. Keyword hits:
telecommunications 54, chinanet 23, hosting 18, internet service provider 14, broadband 8, fibre 3. Prefix hits: contabo 11, rackspace 4.
The 50 null-org rows cannot be judged by org name; they are left out of the review and of the distinct-org counts.

### 3.3 Gate review
Method as before: 50 distinct non-null orgs, the 25 largest by rows, then 25 from a seeded shuffle (seed 7) of the rest. They cover 1,982 of 3,466 rows
(57%). Classified from the ORG name only (the question is whether the org is a potential customer or infrastructure); UNSURE counted as REAL.
Gate: keep isp matching only if INFRA >= 90%.

INFRA (22): GUANGZHOUSHI GUANGBODIANSHIWANGLUO CO.LTD; China Unicom Henan province network; Uninet S.A. de C.V.; Web.com Group, Inc.; RackNerd LLC;
IONOS Inc.; Comcast IP Services, L.L.C.; PSINet, Inc.; China Unicom Shandong province network (2 spellings); CREATE INTERNET LTD; True Internet Co., Ltd.;
Telefonos del Noroeste; Cloud Servers Cell 0001-0003 IAD3; Colocation America Corporation; NHN Techorus Corp.; Rede Nacional de Ensino e Pesquisa;
webservers ASMENET; Easynet Italy Customer Network; Onepage GmbH; MonsterCommerce LLC; Limestone Cable Vision, Inc.

REAL or UNSURE (28): Egnyte Inc.; Fiserv Solutions, LLC; Wal-Mart Stores, Inc.; Avago Technologies U.S. Inc.; TGS Management Company, LLC; Equifax, Inc.;
ULTIMATE SOFTWARE GROUP; NEW YORK MERCANTILE EXCHANGE; HUAWEI INTERNATIONAL PTE. LTD. (UNSURE); Adobe Inc.; GitHub, Inc.; KeyBank National Association;
King (UNSURE); FUNDACAO GETULIO VARGAS; Government of Saskatchewan Communitynet (UNSURE); ZELLIS UK LIMITED; MEDIA (UNSURE); Internet Invest Ltd. Pavel
Blotsky (UNSURE); SURETY BONDS; Evenlink (UNSURE); JIADA WUJIAN CO.,LTD (UNSURE); HONGLIANDIANZI,HANGZHOU,ZHEJIANG (UNSURE); Messe Muenchen; u-shin;
Ribeiro Franck; a street-address string (UNSURE); LivePerson, Inc.; Enlabs AB.

Result: 22 / 50 = 44% INFRA. The 90% gate FAILED. Weighted by rows it is worse: of the 25 largest orgs (about 1,890 rows) only 10 are infrastructure by name
(the China Unicom entries, Uninet, Web.com, RackNerd, IONOS, Comcast, PSINet, CREATE INTERNET, True Internet, the Guangzhou broadcast network), and the largest
five (Egnyte, Fiserv, Wal-Mart, Avago, TGS Management; 1,293 rows) are real companies.

### 3.4 Decision
isp-field matching no longer excludes a row by itself: exact, prefix, pattern and keyword matching are org-only. `cloud.provider` non-null, the
`cloud`/`cdn` tag rule and the CIDR rule on the host IP are unchanged. Implementation: `scripts/denylist_match.py`
`infrastructure_reason(row, rules, isp_matching=DEFAULT_ISP_MATCHING)` with `DEFAULT_ISP_MATCHING = "ignore"`; `isp_matching="exclude"` reproduces the old
behaviour (checked: it gives the same excluded set as the independent measurement script that applied the isp rule). Also added: `load_rules`,
`match_name`. 85 test cases pass (59 before, 26 new).

Caveat for the owner: the biggest group (isp Google, 1,683 rows, 58 orgs: Egnyte, Fiserv, Wal-Mart, ...) are organisations whose address space is
announced through Google. They are not tagged cloud and have a null `cloud.provider`. If the owner decides these are really Google Cloud tenancy rather
than the customer's own estate, an isp-only rule restricted to hyperscaler/CDN isp names (google, amazon com, cloudflare, ovh, fastly) could be restored
alone. That was NOT measured separately (the gate ran on the whole isp-only set).

## 4. Effect on the spread sample (100,000 rows)
| state | infrastructure rows | surviving rows | surviving distinct orgs (non-null) |
|---|---|---|---|
| E: start (reproduced exactly) | 89,398 (89.40%) | 10,602 | 4,863 |
| + automattic, tumblr | 89,425 | 10,575 | 4,861 |
| + remove telephone, cable, dedicated | 89,263 | 10,737 | 4,942 |
| + isp field ignored (final) | 85,747 (85.75%) | 14,253 (14.25%) | 5,664 |

Final reason mix (cloud.provider first, then tags, IP pattern, org rules): cloud_provider 40,537; tag_rule 22,000; org_exact 21,215; org_keyword 1,768;
org_prefix 164; org_pattern 63. The last step releases 3,516 rows and 798 orgs (plus the 50 null-org rows). Null-org rows: 204 in the sample, all surviving
now; 50 of them had been excluded through isp text before (an earlier note said 154 survive in every state; that was wrong by those 50).

Urgency rows:
| signal | all rows | E surviving | after sections 1-2 surviving | final excluded | final surviving | final surviving share |
|---|---|---|---|---|---|---|
| has vulns | 3,076 | 895 | 906 | 2,050 | 1,026 | 33.4% |
| KEV | 1,807 | 537 | 543 | 1,199 | 608 | 33.6% |
| cert expired | 598 | 194 | 195 | 378 | 220 | 36.8% |
| eol tag | 1,582 | 412 | 416 | 1,106 | 476 | 30.1% |
| legacy TLS | 1,268 | 200 | 202 | 1,047 | 221 | 17.4% |
| risky port (20-port list) | 3,335 | 979 | 997 | 2,225 | 1,110 | 33.3% |

The 3,516 released rows carry vulns 120, KEV 65, cert expired 25, eol 60, legacy TLS 19, risky port 113. Honeypot/c2/tor/compromised rows among survivors:
31 before, 36 after (D4 rule 1 removes noise before identity, so these never become companies). The eol count in state E is 412 here; an earlier note had 411
for the previous state (counting detail of one row).

## 5. REAL false positives still excluded (org-field rules)
Operators and operator IT arms counted INFRA by the gate: Deutsche Telekom Global Business Solutions GmbH; DEUTSCHE TELEKOM GLOBAL BUS. SOL. TEL. LTD. STI.;
TELEFONICA GLOBAL TECHNOLOGY S.A.; Instituto Costarricense de Electricidad y Telecom. Large operators (Etisalat Group, Telecom Italia, Telekom Srbija) could
in principle buy security software; they are excluded by design. In a 76-name seeded sample of org-keyword and org-prefix exclusions (40 + 36) I saw no
other real-looking non-operator company.

## 6. Not verified
- Names only, one reviewer, UNSURE counted REAL, no external lookup. The 22/50 result is far below 90%, so a few misclassified orgs do not change the decision.
- 100K spread sample only, not the full file. Distinct orgs are raw org strings.
- The review covers 50 of 798 isp-only orgs (57% of their rows).
- Whether rows with isp Google and a customer org are the customer's own estate or Google Cloud tenancy is not established.
- The rules are not enforced by `check_contract.py` (RAW-010); `docs/ARCHITECTURE.md` D4 wording was not edited.
