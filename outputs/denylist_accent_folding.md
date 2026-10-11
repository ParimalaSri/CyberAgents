# Accent folding in normalise(): effect and keyword re-gate

Date: 2026-10-11. Branch `feat/data-integrator/accent-folding`. Data: `data/sample/spread_100k.jsonl` (read only), 100,000 rows.
Status: PROPOSED. Owner approved accent folding; keyword enablement still needs owner approval before CLAUDE.md sections 11/12.
Builds on `outputs/denylist_orgonly_review.md`.

Reminder (RAW-010): `.claude/skills/data-quality-check/scripts/check_contract.py` still does NOT apply prefix, pattern or keyword rules or any
normalisation. The data-quality-engineer will need to import `scripts/denylist_match.py` so the check and the pipeline share one matcher.

## 1. What changed in the code
- `scripts/denylist_match.py`: new `fold_accents(text)`: `unicodedata.normalize("NFKD")`, drop combining marks ONLY when the base character is a Latin
  letter, then NFC. `normalise()` now calls it first, then lowercases, strips punctuation, collapses spaces, drops trailing legal-suffix words.
  Deterministic, standard library only.
- Non-Latin scripts are left untouched (Chinese, Japanese, Korean, Cyrillic, Arabic): marks on non-Latin bases are kept, so Cyrillic "й" stays "й",
  Arabic vowel signs and Devanagari matras are not stripped, and Hangul is recomposed by NFC. Tested: a CJK org name normalises to itself, not to "".
  Measured on the sample: 183 distinct orgs contain non-ASCII characters, 0 non-null orgs normalise to an empty string.
- Every loader goes through `normalise()` (exact, prefix, keyword, cert defaults, as before) so list entries and data are compared in the same folded form.
  Added: `load_patterns()` and `fold_pattern_text()`; `matches_pattern()` now folds accents and lowercases both the value and the pattern but keeps
  punctuation (CIDR and glob patterns need `/ . * :`). `load_exact()` and `load_cert_defaults()` now drop an entry that normalises to "" (none do today)
  so an empty string can never match everything.
- Not folded (no decomposition exists): ø, ł, đ, ß, æ, œ. They stay as is on both sides of every comparison.
- Quirk seen, not changed: "S.A." normalises to "s a" (two words), so the legal-suffix list does not drop it. Entries and data are treated the same, so
  matching is consistent. A fix would change every list; owner decision.
- `context/denylist_keywords.txt`: removed `org: telefônica` and `org: telefónica` (now identical to `org: telefonica`), and removed `org: telecomunicacoes`
  (failed the gate after merging, section 3). The header comment was updated.
- No non-ASCII characters exist in any of the five list files, so no list entry changes its form.

## 2. Tests
`python scripts/test_denylist_match.py`: 59 cases passed (28 old, unchanged, none edited; 31 new). New cases: TELEFÔNICA BRASIL = Telefónica Brasil = telefonica
brasil; ô ó ç ã ü ñ é examples; decomposed (a + U+0301) equals precomposed; full-width "Ａｃｍｅ" to "acme"; CJK, Japanese, Cyrillic, Korean and Arabic names preserved
and non-empty; a CJK name does not match "telecom"; keyword, prefix and pattern matching across accented spellings; all five loaders fold temp-file entries;
no empty string in the exact or cert-default sets. ruff is not installed here, so lint was not run.

## 3. Keyword gate after merging (spread sample)
Method as before: rows surviving every OTHER rule (all current rules except this keyword), matched on normalised org text, whole-word run. Up to 50 distinct
orgs hand-reviewed (25 largest by rows, then 25 from a seeded shuffle, seed 7; all if 50 or fewer). INFRA vs REAL/UNSURE from names only, UNSURE counts as REAL,
enable at 90% or more. One reviewer, no external lookup.

| keyword | scope | rows | distinct orgs | reviewed | INFRA | % INFRA | decision | change from folding |
|---|---|---|---|---|---|---|---|---|
| telefonica (merged with telefônica, telefónica) | org | 105 | 24 | 24 (all) | 23 | 95.8 | ENABLED | +3 orgs, +12 rows (the accented spellings) |
| telecomunicacoes (merged with telecomunicações) | org | 72 | 42 | 42 (all) | 36 | 85.7 | DISABLED (was enabled at 25/27) | +16 orgs, +23 rows |
| telecom | org | 279 | 136 | 50 | 47 | 94.0 | ENABLED | +1 org (IP TELECOM, SERVICOS DE TELECOMUNICACOES S.A., INFRA); re-sampled |
| telekom | org | 61 | 35 | 35 (all) | 32 | 91.4 | ENABLED | row set identical, stays at 91.4 |
| telecommunication | org | 51 | 19 | 19 | 19 | 100 | ENABLED | row set identical (earlier 20/20 on one more org) |
| telephone, telecoms, telkom, telcom | org | | | | | 100 | ENABLED | row sets identical |
| chinanet | any | | | | | 90.0 | ENABLED | row set identical, stays at 90.0 |
| other 10 unscoped enabled (hosting, vpn, internet service provider, broadband, web hosting, vps, telecommunications, cable, fibre, dedicated) | any | | | | | 90.9 to 100 | ENABLED | row sets identical |
| telecomunicaciones, telecomunicazioni, telekommunikation, telekomunikasi, telco | org | | | | | 68.4, 40.0, 83.3, 66.7, 0.0 | not applied | row sets identical |
| first-round failures (communications, datacenter, data center, cloud hosting, colocation, isp, idc, fiber, wireless, mobile, cloud, servers, internet, network) | any | | | | | | not applied | row sets identical |

"Row set identical" = the set of rows each keyword newly excludes is the same before and after folding (checked row by row), so its earlier gate figure stands;
only telefonica, telecomunicacoes and telecom had different sets. The marginal row counts here use a slightly different definition from last round (all other
rules active, including the other keywords), so they differ by a few rows from the last report: telecom 279 vs 280, telecommunication 51 vs 52.

Flipped: telecomunicacoes. Merging adds the Brazilian "X Telecomunicações Ltda" names, which are mostly small ISPs but also contain firms that are not.
REAL/UNSURE (6 of 42): Chapeco Tecnologia em Telecomunicações Ltda; Jupiter Telecomunicacoes e Informatica Ltda; PT Prime Solucoes Empresariais de Telecomunicacoes
e Sistemas; Criare Telecomunicações e Consultoria Ltda. - EPP; CLICKNET BRASIL INFORMATICA E TELECOMUNICACOES LT; Pombonet Telecomunicações e Informática.
Disabling it returns 49 rows (26 distinct orgs, including Claro NXT 17 rows, UNIFIQUE 6) to the surviving set; it was a pass on ASCII spellings alone (25/27) and
cannot be kept ASCII-only after folding. The owner could reinstate a narrower rule (for example exact names for the large operators); not done.
telecom review of 50: REAL/UNSURE were Instituto Costarricense de Electricidad y Telecom., Beijing Teletron Telecom Engineering Co., Research Institution of Telecom.
Last round scored 49/50 on a different draw (the shuffle depends on the set); both are above 90%.
telefonica REAL: TELEFONICA GLOBAL TECHNOLOGY S.A. (IT arm). Telephone cooperatives (Coop. Telefónica ... Villa Flandria, Cooperativa Telefonica Del Viso, Coop.
Telefonica de Capitán Bermúdez) counted INFRA, as in last round.

## 4. Effect on the spread sample
State C reproduced exactly from last round's files (git HEAD) and the old normaliser. D = new normaliser, otherwise the old list and keyword files (folding alone).
E = final: new normaliser, merged keywords, telecomunicacoes disabled.

| state | infrastructure rows | surviving rows | surviving distinct orgs (non-null org) |
|---|---|---|---|
| C: before (last report) | 89,446 (89.45%) | 10,554 (10.55%) | 4,838 |
| D: folding alone | 89,470 (89.47%) | 10,530 (10.53%) | 4,821 |
| E: final (folding + merged keywords, telecomunicacoes off) | 89,398 (89.40%) | 10,602 (10.60%) | 4,863 |

Null-org rows (154) survive in every state.

## 5. Rows that change status
Folding alone (C to D): 24 rows, all newly infrastructure, 0 the other way.

| rows | org | cause |
|---|---|---|
| 4 | ACESSOLINE TELECOMUNICAÇÕES LTDA | keyword telecomunicacoes now matches the accented spelling |
| 3 | Chapeco Tecnologia em Telecomunicações Ltda. | same |
| 2 | Redfox Telecomunicações Ltda. | same |
| 2 | Ascenty Data Centers e Telecomunicações S/A | same |
| 1 each | 12 more "Telecomunicações" orgs (Vianna Mehl, TASCOM, BS CONECT, LINK NET, Telium, Portao Net, Pombonet, Click.com, Linca, REDE MINEIRA, Ampernet, Criare) | same |
| 1 | ABTC IMOVEIS LTDA ME | its isp "TELEFÔNICA BRASIL S.A" now matches the exact-list entry (a customer behind Telefônica Brasil; the exact list is applied to isp as well as org) |

The telefônica and telefónica spellings were already excluded by their own accented keywords, so they do not move in C to D.

Final versus before (C to E): 50 rows, 1 to infrastructure (ABTC IMOVEIS) and 49 back to surviving: all the telecomunicacoes rows, top Claro NXT Telecomunicacoes Ltda 17,
UNIFIQUE TELECOMUNICACOES S/A 6, CIA DE TELECOMUNICACOES DO BRASIL CENTRAL 2, SOBRALNET SERVICOS E TELECOMUNICACOES 2, then 1 each. The 23 accented telecomunicacoes
rows from section 5 also stay surviving because the merged keyword is off.
84 distinct raw org strings change their normalised form because of folding; 183 orgs contain any non-ASCII character.

## 6. What was NOT verified
- Classification is from names only by one reviewer; the telecomunicacoes fail (85.7%) rests on 6 judgement calls, and a more lenient reviewer could land on
  either side of 90%.
- 100K spread sample only, not the full file. ruff not run (not installed).
- `check_contract.py` does not apply any of this (RAW-010); the contract check can disagree with the matcher until it imports `scripts/denylist_match.py`.
- Folding handles Latin accents only; ø, ł, ß and non-Latin look-alikes (for example Cyrillic "о" vs Latin "o") are different strings by design.
- Urgency-signal shares were not recomputed for this change (only 50 rows move).
