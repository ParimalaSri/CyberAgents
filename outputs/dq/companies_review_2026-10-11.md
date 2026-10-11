# Companies layer review (data-quality-engineer, 2026-10-11)

Scope: `data/silver/companies.parquet` (5,790 rows) from `pipeline/2_companies.py`, input `data/silver/hosts.parquet` (97,758 rows, spread sample, regenerated after the `huawei` prefix, lineage 354599c). Sample only, not the full file.
Runner report: `outputs/dq/companies_2026-10-11.md` (61 of 61 pass). Extra checks: `check_companies_extra.py` (5 of 5 pass). Tests: 34 pass (27 existing, 7 new with 16 injected-fault cases).

Disclosure on independence: the recomputation follows D8.3 to D8.6; I had read the stage's SQL (`pipeline/2_companies.py`) before writing the checker, because the brief listed it as a file to read. My implementation is plain Python over hosts rows (not SQL), written from the D8 text, but it is not blind. The recompute also uses the same stage 1 `name_norm` and flags, so it proves that stage 2 applied the D8 rules to stage 1 output, not that the rules are right.

## 1. hosts re-validation on the regenerated output

- `check_contract.py context/contracts/hosts.yml --report`: PASS 94/94 (unchanged from the previous recheck; the contract holds no count that moved, so no contract edit was needed; the only count constants are 36 columns, 100,000 raw rows and the dup_count sum).
- `check_hosts_extra.py --narrow <scratch parquet of the raw sample>`: RESULT PASS. Per-row disagreement between my flags (shared matcher plus D4/D6 rules in Python) and the parquet over 97,758 rows: `infra_reason` 0, `is_noise` 0, `identity_source` 0, `name_norm` 0, `cert_date_invalid` 0, missing 0.
- Measured: org 12,757; cert_o 558 (mine 558, stage 558, only mine 0, only stage 0, name differs 0; assertion (a) 0 cert defaults); infrastructure_unresolved 83,110; noise 1,136; null_org 197; infrastructure 84,743 of 97,758 = 86.69%; `org_prefix` 784; denylist on org rows 0 hits over 5,508 distinct (org, name_norm) pairs; cert_date_invalid 46 (mine 46); dup_count differing 0.
- PIPE-005 (159.138.6.93:9000): org `Huawei HongKong Clouds`, `is_infrastructure` true, `infra_reason` org_prefix, `identity_source` cert_o, `name_norm` and cert O both `美的集团股份有限公司` (Midea Group). D4 rule 3 as amended by D6.4(a) says cert_o applies when the row is infrastructure or its org is null and the cert O is usable (not a cert default, no shared rule hit). Midea is not a default and hits no rule, so cert_o is what D4/D6.4 prescribe: CONSISTENT. D8.2 says Huawei cert O values are rejected; that is for cert O strings that are Huawei, not a different company's cert on a Huawei IP. Rule not changed. All `huawei*` org_norm rows: 140 infrastructure_unresolved, 25 noise, 1 cert_o.
- Verdict hosts: PASS.

## 2. Recomputation, author vs mine (all from `hosts.parquet`)

| quantity | author (stage report) | mine | match |
|---|---|---|---|
| companies | 5,790 | 5,790 | yes |
| member rows | 13,315 | 13,315 | yes |
| singletons | 4,169 | 4,169 | yes |
| host_count 2 / 3 to 5 / 6 to 20 / 21 to 100 / over 100 | 687 / 568 / 337 / 22 / 7 | 687 / 568 / 337 / 22 / 7 | yes |
| median / p90 / p99 / max | 1 / 4 / 16 / 330 | 1 / 4 / 16 / 330 | yes |
| identity_confidence high / low | 5,387 / 403 | 5,387 / 403 | yes |
| companies named under both sources | 18 | 18 | yes |
| companies with noise / noise rows / at share >= 0.5 | 24 / 33 / 4 | 24 / 33 / 4 | yes |
| noise-only names (rows) | 94 (1,103) | 94 (1,103) | yes |
| raw spellings org + cert O -> companies | 5,508 + 429 -> 5,790 | 5,508 + 429 | yes |
| distinct host_ip all / members | 84,648 / 12,338 (PIPE-005) | 84,648 / 12,338 | yes |
| cert_o-only singletons | 347 (402 + 1, D8.10 346 + 1) | 347 | yes |

Per-company recompute (host_count, org_host_count, cert_o_host_count, distinct_host_ips, distinct_port_count, country_code with the smallest-code tie-break, country_count, noise_host_count and share through `org_norm`, identity_source, identity_confidence, company_name by the D8.4 rule, company_id by hashlib sha256[:16]): 0 disagreements over 5,790 companies; missing 0, extra 0. Reconciliation: 97,758 = 84,443 never-create (83,110 infrastructure_unresolved + 1,136 noise + 197 null_org) + 13,315 member rows; sum(host_count) 13,315; distinct member name_norm 5,790. Resolved share 13.62%, headline unresolved 86.38%. Denylist on `company_name` and `name_norm`: 0 hits.

## 3. Mutation tests

Synthetic layers in a temp directory; each fault is injected into a copy and the named detector must fail (all 16 caught as expected): duplicate company_id (contract and extra), wrong hash (both), host_count off by one (both), host_count and org_host_count off together (both; only the cross-file sum and the recompute catch it), denylisted name_norm `cloudflare` (both), confidence high with org_host_count 0 (contract), sum(host_count) mismatch by a missing company (both), source label flipped (both), noise attribution dropped with a consistent share (extra only), noise on a no-org company (both), share 1.5 (both), wrong country majority (extra only), wrong company_name tie-break (extra only), phantom company absent from hosts (both), distinct_host_ips above host_count (both), empty company_name (both). Also run on copies of the real companies file in the scratchpad (contract failures / extra failures): duplicate id 2 / 2, wrong hash 1 / 2, host_count +1 2 / 2, denylisted name 3 / 2, high confidence with no org host 1 / 1, missing company 3 / 2, noise dropped 0 / 1. Gap: country and noise attribution errors that keep internal consistency are caught only by the extra recompute (documented in the contract header).

## 4. Hand review (names and numbers only; one reviewer)

**10 random companies** (seeded random order over companies): Zinzia Zorggroep (1 host, NL), Zoom Video Communications, Inc (5, US), PT. Gajah Tunggal Tbk (cert_o, low, 1, SG), ISP Alliance a.s. (2, CZ; reads as an operator), PAI Mondragon (1, ES), Cable and Wireless Jamaica (1, JM; an operator), IBL Istituto Bancario del Lavoro S.p.A. (1, IT), Stadtwerke Schorndorf GmbH (1, DE; a utility), UL (1, DE), InfoSphere (NTTPC Communications, Inc.) (2, JP; a telecom brand). 3 of 10 read as network operators, consistent with DQ-005; the rest read as real organisations. No empty or malformed rows.

**Top 20 by host_count**: Egnyte 330, Fiserv Solutions 328, Wal-Mart Stores 248, Avago Technologies 236, Salesforce.com 181, ServiceNow 155, TGS Management 148, ZOHO 95, Los Angeles Municipal Court 86, Equifax 70, GUANGZHOUSHI GUANGBODIANSHIWANGLUO 64 (a broadcast network; operator-like), The Prudential Insurance Company of America 58, ULTIMATE SOFTWARE GROUP 53, NEW YORK MERCANTILE EXCHANGE 42, Adobe 27, DIGITAL SNAP 26, Office of Info.Tech. Admin. for Educational Development 26, Accenture LLP 25, KeyBank 25, NCR 24. All `org`, all `high`; 19 of 20 read as real organisations. Order and numbers equal D8.10 after the Huawei change (Huawei International is gone). Egnyte 330 rows on 136 IPs and 121 ports, Fiserv 328 on 83 IPs, as D8.10 notes (host rows are ip:port, not IPs).

**Over-merge: the 20 companies with the most distinct raw spellings** (spellings, names only): zoho 5 (ZOHO, ZOHO Corp, ZOHO Corporation Private Limited, Zoho Corp, Zoho Corporation), true internet 4, blackline systems 3, xtom 3 (xTom, xTom GmbH, xTom Pty Ltd), bharti airtel 3, tim s a 3, softbank 3, radware 3 (RADWARE INC., Radware Limited, Radware Ltd), zen internet 3, pt first media tbk 3, salesforce com 2, servicenow 2, tpg internet 2, arteria networks 2, brander group 2, ewe tel 2, mittwald cm service gmbh und co kg 2, spark new zealand trading 2, digital core technology 2, telia network services 2. All 20 are case, punctuation and legal-suffix variants of one trade name; none merges unrelated names. `xTom` is the author's flagged case: 16 hosts across US, DE, JP, HK, SG, NL, GB and AU under one hosting group (xTom GmbH DE, xTom Pty Ltd AU); merged into one company, which is the same corporate group and a hosting operator by nature. Judged acceptable, but it is an operator that is not on the denylist (DQ-005 class).
Beyond the top 20, over all 123 companies with 2 or more spellings, a stem test finds none that fail to share a common stem. A legal-suffix jurisdiction scan flags 12; 2 are likely false merges: `intercom` (Intercom SRL, AR, one host on port 8291, merged with `Intercom, Inc` via cert O on Amazon, the US SaaS firm) and `data room` (Data Room SRL, RO, with Data Room, Inc, US). Both are cross-source merges, 2 of 18. Logged as DQ-006. Recall splits (Salesforce 12 + Salesforce.com 181, Fiserv 1 + 328, Dattatec x3) logged as DQ-007.

**The 4 companies with noise_host_share >= 0.5**: Civo LTD (1 host, 1 honeypot row; a cloud host), Jummah-Mosque-Str (1, 1), WebSP - Comercio e Prestacao de Servicos Informaticos, Lda (1, 1), SC Lithuanian Radio and TV Center (2 hosts, 3 honeypot rows; the honeypot rows are in LT, the org hosts in US). 3 of 4 are a singleton with one noise row, so the share is 0.5 by arithmetic. Logged as DQ-008 (threshold design for M2, not a data defect). The ratio is what D8.4 prescribes and the stage matches my recompute.

## 5. Findings and verdict

- No contract rule fails; no stage defect found. Findings are judgement items: DQ-006 (2 likely false merges by legal suffix), DQ-007 (split spelling variants, by design), DQ-008 (0.5 threshold on singletons). Status of PIPE-005 set to consistent; PIPE-004 and DQ-005 cross-referenced to D8.1 and D8.2.
- Verdict companies: PASS (sample).

## 6. Not verified

- The full file (a sample PASS does not authorise prod; replace the paths and constants in the contract on the full run).
- Identity judgements are names only, one reviewer, no external lookup; the 10 random and top 20 reads are small.
- The recompute uses the same stage 1 `name_norm` and the shared matcher, so it shows the rules were applied, not that the rules are right; it was not blind to the stage's SQL.
- `--full` flag, stage 3 and 4, and M2 rules (operator_name_shape, singleton cap, noise exclusion) are out of scope.
- The contract checks the display name only through the recompute; the byte-order tie-break rests on DuckDB and Python agreeing (they agree on all 5,790 companies).
