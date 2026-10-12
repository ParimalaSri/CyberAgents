# Denylist keyword review (ISP / hosting keywords, Weebly and website builders)

Date: 2026-10-11. Branch `feat/data-integrator/isp-keywords`. Data: `data/sample/spread_100k.jsonl` (read only), 100,000 rows.
Status: PROPOSED. The owner approves anything that goes into CLAUDE.md sections 11 and 12.

## 1. Method (and its limits)
- Baseline "surviving" rows: rows NOT infrastructure under the full existing denylist: exact list + prefix families + patterns (org, isp, cloud.provider,
  ip_str) + D4 tag/cloud rule (`cloud.provider` set, or a `cloud` / `cdn` tag). Reproduced: 87,632 infrastructure rows (matches the profile) and
  12,368 surviving rows. The profile prints 12,336; the 32-row difference is not explained here (87,632 + 12,336 = 99,968). All "before" figures below are the
  12,368 reproduced here. Noise rows (honeypot / c2 / tor / compromised) were NOT removed from the survivors in this report.
- A keyword is a whole-word (word-sequence) match on the NORMALISED org or isp text (`matches_keyword`). Candidates were evaluated independently:
  rows and distinct orgs are what each keyword would newly exclude on its own.
- Review set per keyword: up to 50 distinct org strings, the 25 largest by rows, then 25 from a seeded random shuffle (seed 7) of the rest. Keywords
  with 50 or fewer distinct orgs were reviewed in full.
- Classification was done by me from the org name text alone (the isp text was visible but the unit judged was the org string). INFRA = ISP, telecom,
  hosting, VPN, data centre, network provider. REAL = an organisation that could be a buyer. UNSURE counts as REAL. No external lookup was made, so some
  calls are guesses (for example "Cloud Innovation Ltd", "ANE002", "Arisk Communications" were marked UNSURE).
- Gate: ENABLED only if INFRA >= 90% of reviewed orgs.

## 2. Keyword table
| keyword | status | orgs reviewed | INFRA | % INFRA | rows affected (alone) | distinct orgs affected |
|---|---|---|---|---|---|---|
| chinanet | ENABLED | 50 | 45 | 90.0 | 241 | 51 |
| hosting | ENABLED | 50 | 47 | 94.0 | 207 | 112 |
| vpn | ENABLED | 4 (all) | 4 | 100.0 | 38 | 4 |
| internet service provider | ENABLED | 15 (all) | 15 | 100.0 | 96 | 15 |
| broadband | ENABLED | 50 | 47 | 94.0 | 176 | 78 |
| web hosting | ENABLED | 8 (all) | 8 | 100.0 | 10 | 8 |
| vps | ENABLED | 9 (all) | 9 | 100.0 | 12 | 9 |
| telecommunications | ENABLED | 50 | 46 | 92.0 | 221 | 84 |
| cable | ENABLED | 50 | 46 | 92.0 | 115 | 53 |
| fibre | ENABLED | 11 (all) | 10 | 90.9 | 38 | 11 |
| dedicated | ENABLED | 22 (all) | 20 | 90.9 | 33 | 22 |
| telecom | not applied | 50 | 42 | 84.0 | 494 | 249 |
| telekom | not applied | 50 | 27 | 54.0 | 93 | 64 |
| telecommunication | not applied | 42 (all) | 34 | 81.0 | 102 | 42 |
| telecomunicaciones | not applied | 36 (all) | 24 | 66.7 | 144 | 36 |
| communications | not applied | 50 | 39 | 78.0 | 525 | 231 |
| datacenter | not applied | 26 (all) | 18 | 69.2 | 53 | 26 |
| data center | not applied | 18 (all) | 15 | 83.3 | 33 | 18 |
| cloud hosting | not applied | 5 (all) | 4 | 80.0 | 5 | 5 |
| colocation | not applied | 4 (all) | 1 | 25.0 | 5 | 4 |
| isp | not applied | 46 (all) | 39 | 84.8 | 125 | 46 |
| idc | not applied | 50 | 32 | 64.0 | 155 | 52 |
| fiber | not applied | 36 (all) | 26 | 72.2 | 61 | 36 |
| wireless | not applied | 31 (all) | 25 | 80.6 | 41 | 31 |
| mobile | not applied | 50 | 36 | 72.0 | 103 | 60 |
| cloud | not applied | 50 | 40 | 80.0 | 207 | 100 |
| servers | not applied | 39 (all) | 32 | 82.1 | 90 | 39 |
| internet | not applied | 50 | 43 | 86.0 | 597 | 288 |
| network | not applied | 50 | 39 | 78.0 | 869 | 371 |

Not evaluated: `server` (63 rows, 18 orgs), `networks`, `net`, `data`, `online`, `ip` (generic words, not reviewed). "Rows affected" overlap between
keywords (for example hosting and web hosting), so the column does not sum to the effect in section 5.

Weak spots in the enabled set (still above the gate):
- `chinanet` is exactly 90.0% (5 of 50 blocked, all matched through the isp text, not the org text).
- `cable`, `dedicated`, `fibre` are generic English words. They passed on this sample, but a cable manufacturer or a firm named "Dedicated ..." would be
  excluded. `dedicated` was reviewed on 22 orgs, `fibre` on 11.
- `telecommunications` is enabled while `telecommunication` (singular, 81%) and `telecom` (84%) are not; this is the gate's result, not a design choice.

## 3. REAL (or UNSURE) examples that blocked or weakened a keyword
Most REAL examples were matched only through the isp text: a real customer whose carrier is a telecom or ISP. Matching on the org text alone is cleaner.
- telecom (8 of 50): Chengdu west dimension digital technology Co., LTD; SAN JOSE; Beijing Jingdong 360 Degree E-commerce Co., Ltd.; Tieto Estonia Services OY;
  HZONE SRL; Fastnet Net 211; Awesome Projects S.R.L.; OKC Computer Service, Inc.
- telekom (23 of 50): ANECT a.s.; Datalogic GmbH; Amt der Niederoesterreichischen Landesregierung; BMD SYSTEMHAUS GesmbH; Caritas Socialis GmbH; VAMED Management und
  Service GmbH; Schaufler GmbH; Wuestenrot Datenservice GmbH; Index.hu Inc.; www.slovnaft.sk; MATEMATICKI FAKULTET, Beograd.
- telecommunication (8 of 42): Reliable Software, Ltd.; Larestan School Of Medical Sciences; Balaji Infra Ray Private Limited; SAMA GROUP LLC; Iran Information
  Technology Company PJSC.
- telecomunicaciones (12 of 36): Junta de Andalucia; HOSPICIO Y MANICOMIO SAN LAZARO; MEDICINA LEGAL; INDRA COLOMBIA; JSCONTADORESPORACCIONES13.
- communications (11 of 50): CSL Behring, LLC; DNC Holdings, Inc.; Genious Communications; Farhang Azma Communications Company LTD; O.M.C. Computers & Communications.
- datacenter (8 of 26): Posix Systems (Pty) Ltd; CloudRadium L.L.C; Digital Core Technology Co., Limited (15 rows, all through the isp "POWER LINE DATACENTER").
- data center (3 of 18): Schuff International, Inc.; Ministry of Information & Communications; Chengdu west dimension digital technology.
- cloud hosting (1 of 5): WestConnect Communications.
- colocation (3 of 4): code200 UAB; Elastic Email, Inc.; Varner Security (all behind the isp "Colocation America").
- isp (7 of 46): Boromarajonani College Of Nursing Chon Buri; Banyan Tree Phuket; Kenya electricity Transmission; Boolmat.
- idc (18 of 50): Beijing Jingdong 360 Degree E-commerce; Inspur Software Group; GMO GlobalSign Holdings K.K.; LINK, Inc.; RIDE Co.,Ltd.
- fiber (10 of 36): New York City Campaign Finance Board; Nassau BOCES; PureFormulas, Inc.; Professional Software for Nurses Inc; Surfside on the Lake.
- wireless (6 of 31): Zest 4 Group Ltd; M3 Wireless Inc.; Kurlec Wireless; Natural Wireless, LLC (last three UNSURE).
- mobile (14 of 50): UNIQA pojistovna, a.s.; GHO Clinic Praha; Mesto Bystrice; Turnovska pivnice s.r.o.; VP AGRO, spol. s r.o.; MYREAL Immobilien GmbH.
- cloud (10 of 50): Accenture Cloud GlobalSwitch; GUANGZHOU HOTWON COMPUTER TECHNOLOGY; NITA-U Government Cloud (UNSURE); Cloud Innovation Ltd (UNSURE).
- servers (7 of 39): Silicon House; Ooma, Inc.; PingPipe Internet Corporation; Sheimo Scorpion Data AB.
- internet (7 of 50): Comtech Telecommunications Corp.; SUPREMO ORIENTAL CO LTD; Suan Sunandha Rajabhat University; Chengdu west dimension digital technology.
- network (11 of 50): Ministry of Education Computer Center (Taiwan); Dedan Kimathi University of Technology; Office of Info.Tech. Admin. for Educational Development.

Also visible inside ENABLED keywords (the REAL ones counted against them):
- chinanet: Chengdu west dimension digital technology; ChangZhou Bitcomm Software Technology; Shijiazhuang fangneng Communication technology; CloudVsp.Inc and
  Jiangsu Dongyun Cloud computing (UNSURE).
- hosting: Webguru VOF; American Education Group; sellysolutions Servicegesellschaft mbH.
- broadband: TFN MEDIA CO., LTD.; Broadband Systems Corporation and THE SPEEDNET (UNSURE).
- telecommunications: Comtech Telecommunications Corp.; AIR ARABIA; TOYO ELECTRIC CORPORATION; ATHENS (UNSURE).
- cable: A Coruna; EMC Square Teleinfra Pvt Ltd; New Century InfoComm Tech. Co., Ltd.; Cable i Televisio de Catalunya (UNSURE).
- dedicated: Sheimo Scorpion Data AB; ANE002 (UNSURE).

### Option for the owner (not applied, not gated)
The REAL examples above are mostly rows where only the isp text matched. If a keyword were applied to the org text only, the reviewed org-matched subsets
were nearly all INFRA (telecom: 0 REAL among about 31 org-matched orgs in the review set; telekom: 1 UNSURE among 27; datacenter, data center, isp, idc,
fiber: 0 REAL among the org-matched orgs seen). Org-only rows on the 12,368 survivors: telecom 301 rows / 145 orgs, telekom 61 / 35, communications 315 / 132 (but
communications had REAL even among org matches, 7 UNSURE of about 36), datacenter 24 / 18, data center 13 / 10, isp 39 / 29, idc 38 / 7, fiber 46 / 24,
telecommunication 55 / 23. These are subsets of the review sample, not a gate pass; a scoped rule needs a code change (a per-keyword field scope) and its own
50-org review. Not implemented.

## 4. Weebly and website builders (decision D2: website builders are infrastructure)
Survivors were scanned for: weebly, duda, jimdo, webflow, ghost, strikingly, wordpress, automattic, tumblr, tilda, webnode, yola, bigcommerce, wix, squarespace,
godaddy, site123, homestead, netlify, bluehost, wpengine, hubspot (word or prefix match on org and isp).
Added to `context/denylist_prefixes.txt` (exact brand family, word-boundary prefix):
| addition | surviving rows (org or isp) | org seen |
|---|---|---|
| weebly | 49 rows (98 org-plus-isp hits) | Weebly, Inc. |
| jimdo | 3 rows | Jimdo GmbH Web Delivery Services |
Not added, and why:
- duda, webflow, strikingly, tilda, webnode, yola, site123, homestead, netlify, bluehost, wpengine: no surviving rows (nothing to add; absence is only for this sample).
- squarespace, wix, godaddy, shopify: already covered by the exact or prefix lists.
- ghost: only "GHOSTnet" (a VPS host, GHOSTnet GmbH) appears, not the Ghost CMS brand. Adding `ghost` would have been wrong as a brand family; GHOSTnet is
  already caught by `hosting`/`vps` when the org text says so.
- Automattic, Inc (WordPress.com, 44 rows, plus TUMBLR, INC. 5 rows via isp Automattic): a blogging / website platform. NOT added: the owner named a list of
  builders and this one was not on it. Open question for the owner (49 rows, 2 orgs).
- hubspot (1 row): a marketing SaaS vendor, not a website builder. Not added.
The two additions are outside the 40 families the owner accepted; the header of the prefix file says so.

## 5. Effect with the enabled keywords plus weebly and jimdo
Spread sample, 100,000 rows. "Before" is the reproduced baseline (see section 1).
| measure | profile (`outputs/profile_spread_100k.md`) | baseline reproduced | after |
|---|---|---|---|
| infrastructure rows (share) | 87,632 (87.63%) | 87,632 (87.63%) | 88,802 (88.80%) |
| surviving rows (share) | 12,336 (12.34%) | 12,368 (12.37%) | 11,198 (11.20%) |
| surviving distinct orgs | 5,507 | 5,519 | 5,113 |
| rows newly excluded | | | 1,170 (1,118 by keywords, 52 by weebly/jimdo) |
The brief's expectations were "about 86%" infrastructure and "about 10%" surviving; after the change the gap to them is 2.8 and 1.2 points
(it was 1.6 and 2.3 before the change on the profile figures).

Urgency signals, excluded vs surviving (all 100,000 rows; cert expired is the boolean flag, not "within 30 days"):
| signal | all rows | surviving before | newly excluded | surviving after | share of signal rows surviving, before then after |
|---|---|---|---|---|---|
| has vulns | 3,076 | 1,011 | 82 | 929 | 32.9% then 30.2% |
| KEV (vulns[*].kev) | 1,807 | 617 | 56 | 561 | 34.1% then 31.0% |
| cert expired | 598 | 216 | 16 | 200 | 36.1% then 33.4% |
| eol-product / eol-os tag | 1,582 | 457 | 33 | 424 | 28.9% then 26.8% |
| legacy TLS offered | 1,268 | 228 | 23 | 205 | 18.0% then 16.2% |
| risky port (20 ports in the profile) | 3,335 | 1,114 | 101 | 1,013 | 33.4% then 30.4% |
The 1,170 newly excluded rows carry 82 vulnerable rows (7.0%) and 56 KEV rows (4.8%), against 8.2% and 5.0% in the 12,368 baseline survivors. Excluded
rows are slightly less exposed than the survivors they leave, so the filter does not remove a disproportionate share of urgency signals.

## 6. Not verified
- All INFRA / REAL calls come from the org name text, by one reviewer (me), with no web lookup or second opinion. A different reviewer could move a
  keyword across 90%: `chinanet` is exactly at the line (one more REAL call fails it), and `fibre` / `dedicated` sit at 90.9% on 11 and 22 orgs.
- Only 25 of each 50 reviewed orgs were drawn at random (seed 7); the other 25 are the largest by rows, so large operators dominate the reviewed sample.
- The effect numbers use a 100K spread sample; the full file is untested. Noise rows were not dropped from the survivors.
- `check_contract.py` (`.claude/skills/data-quality-check/scripts/check_contract.py`) still understands only the exact list (RAW-010). It does not
  apply prefix, pattern or keyword rules, so the keyword and weebly/jimdo additions are not yet enforced by the data-quality check.
