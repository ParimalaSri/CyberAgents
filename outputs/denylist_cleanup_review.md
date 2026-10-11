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

## 7. D5 follow-up (branch `feat/data-integrator/d5-wording`, 2026-10-11)
Decided by senior-data-engineer under the owner's delegation; the owner may overrule. Same spread sample, read only.

### 7.1 Wording
`DEFAULT_ISP_MATCHING` stays `"ignore"`; `"exclude"` is documented in code as reproducing the old counts only. Text that still said the isp is matched was
fixed (wording only, no behaviour change) in `context/denylist.txt`, `context/denylist_prefixes.txt`, `context/denylist_patterns.txt`,
`context/denylist_keywords.txt`, `context/schema.md` and the comments and docstrings of `scripts/denylist_match.py`. `docs/ARCHITECTURE.md` and
`check_contract.py` were not edited.

### 7.2 Gate: org-scoped keyword `ovh`
Newly matched set (rows surviving every other rule whose normalised org contains the whole word `ovh`): 41 rows, only 6 distinct orgs, so all 6 were reviewed
(fewer than 50 exist). Names only, UNSURE counted REAL: OVH Singapore PTE. LTD 17, OVH Hispano 9, OVH (NWK) 6, OVH BE 5, OVH Australia PTY LTD 2, Dedicated
servers OVH 2. All 6 INFRA, 0 REAL or UNSURE: 6/6 = 100%, gate (90%) PASSED. Caveat: n=6, one reviewer, no external lookup.
Added as `org: ovh`. Whole-word check: `OVHTECH R&D (INDIA) PRIVATE LIMITED` (7 rows) is NOT matched, and neither are `Hovhannes Consulting` or `Novhost Media`;
the isp text `OVH Singapore` does not match. So OVHTECH stays surviving; a name-based rule for it would need a prefix `ovhtech`, which was not asked for or gated.
`ovh` is not added to the prefix list (under 4 characters).

### 7.3 Webflow
`webflow` added to `context/denylist_prefixes.txt` as a D2 website-builder family (like weebly, jimdo, automattic, tumblr). Sample: org `Webflow, Inc`, 10 rows,
1 IP, no tags, no `cloud.provider`, previously surviving; 0 isp rows. Prefix family now 45 entries (40 owner-accepted plus 5 builders).
Tests: `Webflow, Inc` and `Webflow Agency Ltd` match; `Webflowers Florist` does not.

### 7.4 infra_reason value set
`infrastructure_reason()` returns exactly: cloud_provider, tag_rule, ip_pattern, org_exact, org_prefix, org_pattern, org_keyword (plus isp_* values only in the old
`"exclude"` mode, never in the default). `2_companies` is not built yet, so this set (`INFRA_REASONS` in `scripts/denylist_match.py`, pinned by a test) is the
contract it must follow. 106 test cases pass (85 before, 21 new).

### 7.5 Before and after (spread sample, 100,000 rows)
| state | infrastructure | surviving | surviving distinct orgs |
|---|---|---|---|
| A: senior baseline (reproduced exactly) | 85,747 (85.75%) | 14,253 (14.25%) | 5,664 |
| B: + ovh | 85,788 | 14,212 | 5,658 |
| C: + webflow (final) | 85,798 (85.80%) | 14,202 (14.20%) | 5,657 |

Reason mix final: cloud_provider 40,537; tag_rule 22,000; org_exact 21,215; org_keyword 1,809 (was 1,768); org_prefix 174 (was 164); org_pattern 63.
Urgency rows (all rows / surviving A / surviving C): has vulns 3,076 / 1,026 / 1,025; KEV 1,807 / 608 / 607; cert expired 598 / 220 / 219; eol tag 1,582 / 476 / 475;
legacy TLS 1,268 / 221 / 221; risky port (20-port list) 3,335 / 1,110 / 1,104. Surviving share of vulns: 33.4% to 33.3%. Honeypot/c2/tor/compromised survivors 36 to 35.
The 51 rows moved (41 ovh, 10 webflow) carry vulns 1, KEV 1, cert expired 1, eol 1, legacy TLS 0, risky port 6. No row moved the other way.

### 7.6 Not verified
Names only, single reviewer, 100K spread sample only, not the full file. The `ovh` gate rests on 6 orgs. Other OVH spellings that may exist in the full file
(OVHTECH and one-word compounds) are not covered. `check_contract.py` still applies none of the prefix, pattern or keyword rules (RAW-010).

## 8. D6 follow-up (branch `feat/data-integrator/d6-denylist`, 2026-10-11)
Decided by senior-data-engineer under the owner's delegation (D6.4 and D6.7 in `docs/ARCHITECTURE.md` section 15); the owner may overrule. Same 100K spread sample
(`data/sample/spread_100k.jsonl`), read-only, scratch files only. Method as in section 3: newly matched distinct orgs among rows that survive every rule today, up to 50
(largest first, then a seeded sample, seed 7), INFRA versus REAL or UNSURE from the name text only, UNSURE counted REAL, enable at 90% or more. Fewer than 50 orgs matched
in every case, so every newly matched org was reviewed and no random draw was needed. Baseline reproduced exactly: infrastructure 85,798 (85.80%), surviving 14,202, 5,657 distinct orgs.

### 8.1 Cert O defaults (`context/cert_default_names.txt`)
Added (spellings checked against `data/silver/hosts.parquet` `cert_subject_o` / `name_norm`; rows in the 97,758-row hosts file):
huawei 11, huawei technologies 2, huawei software technologies 8, sierra wireless 13, ruckus wireless 3, aruba networks 1, arista networks 1, mitel networks 1, technicolor 4,
rakwireless 1, comcast (`Comcast Corporation`, 5; `comcast corporation` normalises to the same entry), ntt docomo business 6, the China Telecom Cloud name (24): 80 rows. Name guard: meta platforms
(4 rows), apple (1), facebook and netflix (0 cert rows; listed as decided). All 19 listed spellings and 8 real tenants used as controls (Accenture, Okta, Datadog, SAP, Salesforce,
Royal Bank of Scotland, Disney Enterprises, Aruba S.p.A.) are pinned in tests.
`dis` (ADDED): 10 hosts rows carry cert O `Dis`; 7 are `cert_o` rows (DigitalOcean 4, Contabo 1, Vultr 1, one null-org row) and 3 sit on org rows (DIGITAL SNAP, ENCOM, Ethernet Servers).
All 10 are self-signed mail-server certificates (smtp 587, imap 143 and 993, pop3-ssl 995; Postfix smtpd on 4), cert CN `www.example.com` (8) or localhost (`server.localhost.com`,
`localhost.localdomain`), tag `self-signed`, 10 different IPs. It is a template placeholder, not a tenant and not a vendor, so it is listed as a default.
Not added (outside the list): the China Telecom subsidiary name for Tianyi Digital Life (1 row) and `Aruba S.p.A.` (1 row, an Italian hosting provider; not matched by the Aruba Networks entry).

### 8.2 Gates
| rule | newly matched | reviewed | INFRA | result | decision |
|---|---|---|---|---|---|
| (a) prefixes `facebook`, `meta platforms`, `netflix` | 176 rows, 4 orgs | 4 | 0/4 (0%) | FAILED on names; superseded by D7.1 | ADDED under D7.1 (hostname evidence, 2026-10-11) |
| (b) `org: unicom` | 249 rows, 47 orgs | 47 | 46/47 (97.9%) | PASSED | added |
| (b) `org: province network` | 204 rows, 38 orgs | 38 | 38/38 (100%) | PASSED | added (1 row beyond unicom: CNCGROUP Zhejiang Province Network) |
| (c) compound `org: *hosting` | 95 rows, 30 orgs | 30 | 30/30 (100%) | PASSED | added |
| (d) named operators and hosts, 13 prefixes | 440 rows, 40 orgs | 40 | 39/40 (97.5%) | PASSED | added |

(a) Names only, the orgs are Netflix Streaming Services Inc. 144 rows, Meta Platforms Ireland Limited 20, Facebook, Inc. 10, Netflix Luxembourg S.a.r.l. 2: real, named companies, so 0 of 4
read as infrastructure and the 90% gate fails. Supplementary evidence that is NOT part of the gate (hosts.parquet): Netflix 141 rows are on port 179 with hostnames
`ipv4-cNNN-...-ix.1.oca.nflxvideo.net` (Open Connect cache nodes, 141 distinct IPs, 0 vulnerable); Meta Platforms Ireland 20 rows and Facebook 10 rows are on ports 80 and 443 with
`edge-*.facebook.com` or `fbcdn.net` names, 3 of them noise rows (RAT banner artefacts). So the rows look like cache or edge nodes of the organisation itself, the reading in D6.4, but the name-only
gate as defined cannot show it. A hostname-domain rule (`nflxvideo.net`, `fbcdn.net`) would be a new rule type and was not built. The cert O side is guarded (8.1); the org side stays open for the
senior to rule on, and the 176 rows still survive as companies (Netflix Streaming Services is the 7th largest surviving org).
(a) Superseded by D7.1 (senior-data-engineer decision, 2026-10-11): the three prefixes `netflix`, `meta platforms`, `facebook` are now in `context/denylist_prefixes.txt` as a closed list of
content-delivery operators, excluded on hostname evidence rather than the name-only gate: Netflix 143/143 rows on `nflxvideo.net` (Open Connect cache nodes), Meta Platforms Ireland and Facebook
27/27 rows on facebook.com or fbcdn.net edge names. `Apple Inc.` is deliberately NOT excluded. The prefixes also match any future org that starts with those words (pinned in tests).
Re-measure on `data/silver/hosts.parquet` (97,758 rows, matcher only, stage not rerun): 173 rows change status (170 `org` rows plus 3 noise rows; Netflix Streaming Services 141, Netflix Luxembourg 2,
Meta Platforms Ireland 20, Facebook 10); matcher-infrastructure 84,523 to 84,696 rows (86.46% to 86.64%).

(b) The one UNSURE is `Unicom (Jiangsu) Industry Internet Co. LTD` (4 rows, counted REAL). The other 46 are China Unicom provincial or city networks, `CHINA UNICOM CLOUD DATA COMPANY LIMITED`,
`China UNICOM, Beijing Branch` and fujian provincial network of UNICOM entries. Whole word: `Unicomer Group` is not matched. `province network` and `unicom` are carrier words; no non-carrier name
containing them is in this sample, which says nothing about the full file.
(c) Approach chosen: a compound keyword, written `org: *hosting` in `context/denylist_keywords.txt`. A leading `*` means: ONE token of the normalised name must END with the word and
have a non-empty stem (webhosting, egihosting, bisecthosting, swhosting, ahosting). It is not a substring match. Excluded by design: `ghosting` (explicit `COMPOUND_EXCLUDE`),
tokens that merely start with the word (`hostingbazis`) or carry a plural (`snthostings`); two of the 32 substring candidates (HostingBazis Bt., SnTHostings) therefore stay surviving.
The whole-word `hosting` keyword is unchanged. A plain substring would have matched 32 orgs (all INFRA by name); the compound form matches 30. The 30 orgs: EGIHosting 20, webhosting servers 20,
BisectHosting 15, FREAKHOSTING 4, Webhosting UK com LTD 4, RoyaleHosting BV 4, RimuHosting 3, Friendhosting LTD 2, swhosting.com 2 and 21 single-row hosting names. Tests pin the matches and the non-matches.
(d) Prefix entries (rows added each): racknerd 28, ntt america 33 (NTT America, Inc. and NTT America; NTT DATA, NTT DOCOMO and NTT PC Communications are NOT matched), ionos 26 (1&1 IONOS SE, 3 rows,
is not matched), telstra 25 (3 orgs), vodafone 90 (22 orgs; the one UNSURE is Vodafone Labs, 2 rows), fastweb 23, uninet 38 (Uninet S.A. de C.V. 37 and Uninet DSL access network 1; the bare name is the weakest
call of the set, counted INFRA on DQ-002's reading; the org `Gestion de direccionamiento UniNet`, 15 rows, is NOT matched), cliente antel 33, administracion nacional de telecomunicaciones 36
(ANTEL itself), web com 31 (Web.com Group), psinet 27, comcast 27 (Comcast IP Services 24 and two Comcast Cable Communications orgs), cloudfly 23. Total 440 rows. Seen but not added: Orange (18 orgs,
no org above 7 rows), Rogers (largest 16 rows), Optus 14, AT&T 16, Cogent 9, Lumen 10, 1&1 Versatel 12 (below 20 rows per name), True Internet 21 and Taiwan Fixed Network 21 (not on the DQ-002 list;
`internet` and `network` are generic words). No generic word (network, internet, net, cloud, communications) was added.

### 8.3 Before and after (spread sample, 100,000 rows)
| state | infrastructure | surviving | surviving distinct orgs |
|---|---|---|---|
| before (D5 follow-up, reproduced exactly) | 85,798 (85.80%) | 14,202 (14.20%) | 5,657 |
| after (this branch) | 86,583 (86.58%) | 13,417 (13.42%) | 5,539 |

Reason mix after: cloud_provider 40,537; tag_rule 22,000; org_exact 21,215; org_keyword 2,150 (was 1,809); org_prefix 618 (was 174); org_pattern 63 (4 rows that were keyword hits now report prefix, because
prefix is tested first). 785 rows moved to infrastructure, 0 the other way. Rows moved by rule: unicom 249, province network 1, *hosting 95, named prefixes 440.
Urgency rows (all rows / surviving before / surviving after / the 785 moved): has vulns 3,076 / 1,025 / 963 / 62; KEV 1,807 / 607 / 573 / 34; cert expired 598 / 219 / 202 / 17;
eol tag 1,582 / 475 / 454 / 21; legacy TLS 1,268 / 221 / 210 / 11; risky port (20-port list) 3,335 / 1,104 / 1,035 / 69. Surviving share of vulnerable rows 33.3% to 31.3%. Noise-tag survivors 35 to 35.
The moved rows are 7.9% vulnerable (62 of 785) against 7.2% of surviving before (1,025 of 14,202): the gain is not urgency-poor; hosting names carry 16 of the 62.

Top-50 surviving orgs residual (the DQ-002 metric; names only; strict: the name itself says ISP, telecom, hosting or data centre; UNSURE names such as Cloud Innovation, DIGITAL SNAP,
HUAWEI INTERNATIONAL, Sichuan Yihu Data Technology and the Guangzhou broadcast network are not counted):
- before: 20 of 50 orgs, 538 rows (DQ-002 had 20 of 50, 537 rows; the 1-row gap is dedupe, this scratch set is not deduplicated).
- after: 9 of 50 orgs, 171 rows: True Internet 21, Taiwan Fixed Network 21, IDC Frontier 20, CTG Server 19, Societe Francaise Du Radiotelephone - SFR 19, Leaseweb USA 19, CREATE INTERNET 18,
  Claro NXT Telecomunicacoes 17, Mega Cable 17. Counting the hosting-looking UNSURE names (Dattatec, WorldStream, OPTAGE, Neue Medien Muennich, New Dream Network, Bunny Communications, GOLD IP) it is 16 of 50.
  The list refills from rank 51 with the same kind of name, so the long tail is not fixed by this: 18% strict (32% loose) is above the 10% reopen threshold of D6.7, which is meant for the full run.
  Apple Inc. (20 rows) and Meta Platforms Ireland Limited (20) are now in the top 50 as org companies (see 8.2 (a)).

### 8.4 REAL false positives and limits
REAL organisations that are newly excluded (names only; none is certain): Vodafone Labs 2 rows (an R&D arm), Unicom (Jiangsu) Industry Internet Co. 4 rows (unclear), Uninet (the bare name, 37 rows; may be a company
name outside Mexico), NTT America, Telstra and Comcast (operators that also sell managed security). Large operators are excluded by design, as in section 5.
Not verified: names only, one reviewer, UNSURE counted REAL, no external lookup; 100K sample only, not the full file; the full-file residual of the operator long tail is not measured; the compound rule is gated on
30 orgs; the (d) prefixes are an explicit hand list and do not scale; the gate (a) call rests on 4 orgs and a names-only reading. The shared matcher is applied by `check_contract.py` (RAW-010 closed), so
the new rules are enforced for names, but a contract cannot catch an unlisted name.
