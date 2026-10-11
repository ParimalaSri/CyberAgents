# Org-only keyword review (field-scoped denylist keywords: telecom, telekom and variants)

Date: 2026-10-11. Branch `feat/data-integrator/org-only-keywords`. Data: `data/sample/spread_100k.jsonl` (read only), 100,000 rows.
Status: PROPOSED. The owner approves anything that goes into CLAUDE.md sections 11 and 12. Builds on `outputs/denylist_keyword_review.md`.

Reminder (RAW-010): `.claude/skills/data-quality-check/scripts/check_contract.py` does NOT yet apply prefix, pattern or keyword rules, so none of the
rules below is enforced by the DQ check. Only `scripts/denylist_match.py` implements them.

## 1. What was added
- Syntax in `context/denylist_keywords.txt`: `phrase` = unscoped (org text OR isp text, as before); `org: phrase` = org text only. An unknown scope
  (for example `isp: x`) raises ValueError.
- `scripts/denylist_match.py`: `Keyword` (a str subclass with `.scope`), `parse_keyword_entry`, `load_keywords` (returns Keyword objects, de-duplicated by
  phrase and scope), `matches_keyword(normalised, keywords, field="org")` where field is `org` or `isp` (anything else raises). Plain-string keyword lists
  still work (treated as unscoped).
- Tests: `python scripts/test_denylist_match.py` = 28 cases passed (15 old + 13 new: org-only matches org, does not match isp, unscoped matches both,
  unknown scope rejected, bad field rejected, file loading with duplicates and a bad scope). One OLD assertion was edited because its premise changed on
  purpose: "telecom is not in the loaded keywords" is now "no UNSCOPED telecom keyword is loaded" (telecom is now enabled, org-only).

## 2. Method
- Evaluation set: rows that survive the FULL current denylist: exact + prefix (including weebly, jimdo) + pattern + the 11 unscoped keywords + D4 tag/cloud
  rule = 11,198 rows (the task text quoted 12,368; that is the count before last round's keywords and the weebly/jimdo prefixes).
- Each candidate is matched on the normalised ORG text only (whole-word run). Rows and distinct raw org strings are what the keyword newly excludes on its own.
- Review set: up to 50 distinct org strings: the 25 largest by rows, then 25 from a seeded shuffle (seed 7) of the rest; all orgs if 50 or fewer.
  I classified from the org text alone (isp text not shown). INFRA = ISP, telecom operator, hosting, VPN, data centre, network provider. UNSURE counts as REAL.
  No external lookup; one reviewer. Gate: enable only if INFRA >= 90%.
- Candidate list: telecom, telekom, telecommunication, telecomunicaciones, telefonica, telco, telephone, plus variants found by scanning surviving org tokens
  (telecomunicacoes, telecomunicazioni, telekommunikation, telekomunikasi, telecoms, telkom, telcom) and the accented spellings (section 5).

## 3. Gate results
| keyword (org-only) | rows | distinct orgs | reviewed | INFRA | % INFRA | decision | rows matched only via isp (not excluded now) |
|---|---|---|---|---|---|---|---|
| telecom | 280 | 137 | 50 | 49 | 98.0 | ENABLED | 130 |
| telekom | 61 | 35 | 35 (all) | 32 | 91.4 | ENABLED (barely) | 32 |
| telecommunication | 52 | 20 | 20 (all) | 20 | 100.0 | ENABLED | 47 |
| telefonica | 93 | 21 | 21 (all) | 20 | 95.2 | ENABLED | 90 |
| telephone | 27 | 20 | 20 (all) | 20 | 100.0 | ENABLED | 21 |
| telecomunicacoes | 50 | 27 | 27 (all) | 25 | 92.6 | ENABLED (barely) | 7 |
| telecoms | 3 | 3 | 3 (all) | 3 | 100.0 | ENABLED (tiny n) | 10 |
| telkom | 12 | 5 | 5 (all) | 5 | 100.0 | ENABLED (tiny n) | 0 |
| telcom | 17 | 4 | 4 (all) | 4 | 100.0 | ENABLED (tiny n) | 0 |
| telefônica (o circumflex) | 39 | 1 | 1 | 1 | 100.0 | ENABLED (n = 1 org) | not measured |
| telefónica (o acute) | 12 | 3 | 3 | 3 | 100.0 | ENABLED (tiny n) | not measured |
| telecomunicaciones | 86 | 19 | 19 (all) | 13 | 68.4 | not applied | 56 |
| telecomunicações (accented) | 22 | 15 | 15 (all) | 13 | 86.7 | not applied | not measured |
| telecomunicazioni | 5 | 5 | 5 (all) | 2 | 40.0 | not applied | 0 |
| telekommunikation | 14 | 6 | 6 (all) | 5 | 83.3 | not applied | 8 |
| telekomunikasi | 16 | 3 | 3 (all) | 2 | 66.7 | not applied | 10 |
| telco | 1 | 1 | 1 | 0 | 0.0 | not applied | 19 |

The "only via isp" column is the point of the change: those rows are customers behind a telecom carrier and are now KEPT (unscoped matching would have
excluded them). Spot check: Jingdong (7 of 8 rows survive), Tieto Estonia, Fastnet, HZONE, Datalogic, ANECT and Caritas all still survive.

## 4. REAL / UNSURE examples
- telecom (1 of 50): Instituto Costarricense de Electricidad y Telecom. (state electricity and telecom company, UNSURE).
- telekom (3 of 35, barely passes): Deutsche Telekom Global Business Solutions GmbH; DEUTSCHE TELEKOM GLOBAL BUS. SOL. TEL. LTD. STI. (IT services arm);
  FACE_TELEKOM_TICARET (trading company, UNSURE).
- telefonica (1 of 21): TELEFONICA GLOBAL TECHNOLOGY S.A. (IT arm).
- telecomunicacoes (2 of 27, barely passes): Jupiter Telecomunicacoes e Informatica Ltda; PT Prime Solucoes Empresariais de Telecomunicacoes e Sistemas.
- telecomunicaciones (6 of 19, FAIL): Sociedad Andaluza para el Desarrollo de las Telecomunicaciones S.A. Medio Propio (public body); CONSULTORA NAVARRA DE
  TELECOMUNICACIONES S.L; I.T.M. Instalaciones y Mantenimiento de Telecomunicaciones S.L.; Ingeniería Tecnología y Telecomunicaciones Ltda.;
  TECNOLOGIA EN TELECOMUNICACIONES ABIERTAS S.A.; Anmaguzcer Telecomunicaciones S.L.U.
- telecomunicações accented (2 of 15, FAIL): Chapeco Tecnologia em Telecomunicações Ltda.; Criare Telecomunicações e Consultoria Ltda. - EPP.
- telecomunicazioni (3 of 5, FAIL): Jcom Telecomunicazioni; T.C.E. Telecomunicazioni; Unica Telecomunicazioni s.r.l. (names only; may be small operators).
- telekommunikation (1 of 6, FAIL): SALZBURG AG fur Energie, Verkehr und Telekommunikation (utility).
- telekomunikasi (1 of 3, FAIL): PT Solusi Media Telekomunikasi.
- telco (1 of 1, FAIL): Telco Wiring, Inc. (cabling contractor).

Judgement calls for the owner: (a) telecom operators themselves (A1 Telekom Austria, Telefonica, Bouygues Telecom, SK Telecom, US rural "Telephone
Cooperative" companies) are counted INFRA because the gate defines INFRA as including telecom and network providers; they are large organisations that could
in principle buy security software. (b) `telephone` matched 20 orgs, all local telephone companies; a firm such as "Telephone Answering Service Inc" would
be excluded.

## 5. Accented spellings
`normalise()` keeps accents, so TELEFÔNICA BRASIL S.A (39 rows), Telefónica Celular de Bolivia and TELEFÓNICA CHILE are NOT matched by the ASCII keyword
`telefonica`. They are enabled as separate org-only keywords. `telecomunicações` failed (13/15). Alternative not done: fold accents in `normalise()`; that
changes every list and needs an owner decision.
Not covered: one-word compound brands (kazakhtelecom, rostelecom, chinatelecom, meditelecom: 2 to 13 rows each) and operator brands without the word
(Telenet, Tele2, Telenor).

## 6. Effect on the 100,000-row spread sample
State A = start of last round (no keywords, no weebly/jimdo prefixes), B = end of last round, C = now.
| state | infrastructure rows | surviving rows | surviving distinct orgs (non-null org) |
|---|---|---|---|
| A: start of last round | 87,632 (87.63%) | 12,368 (12.37%) | 5,518 |
| B: end of last round | 88,802 (88.80%) | 11,198 (11.20%) | 5,112 |
| C: now (+11 org-only keywords) | 89,446 (89.45%) | 10,554 (10.55%) | 4,838 |

A and B reproduce last round's 87,632 / 12,368 and 88,802 / 11,198 exactly (the earlier report gave 5,519 and 5,113 orgs; a 1-org difference from
counting method). B to C: 644 rows and 274 distinct orgs newly excluded. The 154 null-org rows survive in every state.

Urgency signals (all rows in the sample, then surviving rows by state, then the split in C):
| signal | total | A surviving | B surviving | C excluded | C surviving | C surviving share |
|---|---|---|---|---|---|---|
| has vulns | 3,076 | 1,011 | 929 | 2,181 | 895 | 29.1% |
| KEV | 1,807 | 617 | 561 | 1,270 | 537 | 29.7% |
| cert expired (boolean) | 598 | 216 | 200 | 404 | 194 | 32.4% |
| eol tag (eol-product or eol-os) | 1,582 | 457 | 424 | 1,171 | 411 | 26.0% |
| legacy TLS offered | 1,268 | 228 | 205 | 1,068 | 200 | 15.8% |
| risky port (profile list of 20 ports) | 3,335 | 1,114 | 1,013 | 2,356 | 979 | 29.4% |

The 644 rows newly excluded B to C carry: vulns 34, KEV 24, cert expired 6, eol 13, legacy TLS 5, risky port 34. Noise rows (honeypot / c2 / tor /
compromised tags) were not removed from survivors: 31 survive in state C.

## 7. The 32-row gap (profile 12,336 vs reproduced 12,368)
Cause found (strongly supported; the original query was not kept so it is not proven): exactly 32 of the 12,368 survivors have `ip_str` null (IPv6 rows).
The profile's survivor query evaluates the CIDR pattern on `ip_str`; a null address gives NULL, NOT(NULL) is NULL, and the row drops out of the survivor
count. Checks: those 32 rows hold 1 vuln row and 0 KEV, 0 eol, 0 legacy-TLS and 0 risky-port rows, and the profile's survivor counts differ from mine by exactly
that (vulns 1,010 vs 1,011; KEV 617 = 617; eol 457 = 457; legacy TLS 228 = 228; risky port 1,114 = 1,114).
Separately: re-running today's files gives 87,684 infrastructure, 52 more than 87,632; those are the weebly/jimdo prefix rows added after the profile.

## 8. What was NOT verified
- Classification is from org names only, by one reviewer (me), with no external lookup; UNSURE counted as REAL. Several calls (small "Telecomunicaciones"
  or "Telecomunicacoes" firms) are guesses. Small keywords (telecoms, telkom, telcom, accented telefonica: 1 to 5 orgs) pass on very few orgs.
- 100K spread sample only; not run on the full file. Distinct-org counts are raw org strings (spelling variants count separately).
- The rules are not enforced by `check_contract.py` (RAW-010).
- Survivors still contain telco names outside these keywords (Telenet, Tele2, Telenor, compound brands).
