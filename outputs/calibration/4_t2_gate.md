# 4. T2 gate (D9.5) and T1 check (D8.2) on fresh seeded samples; names only, one reviewer (the analyst); labels are NOT eval ground truth

Seeds: Python `random.Random(23).sample(...)` over the set ordered by `account_id`. Seed 23 was not used before (5, 7, 10 and 11 are the used ones). The same seed is used for the T2 sample of 40 and the T1 sample of 20 (different sets, so independent draws). Population: T2 only = `operator_shape_t2 = true AND operator_shape_t1 = false`, 392 of 5,790 (matches the expected 392). Full list with the sub-pattern of each name: `4_t2_only_flagged.csv` (also marks the 40 sampled, with position).

Labels. OPERATOR = the name itself says ISP, hosting, telecom, datacentre, fibre or server provider. ORGANISATION = reads as an end-user organisation. UNSURE = a bare `...net` or similar name that could be either; UNSURE counts as ORGANISATION for this gate (against the flag), as instructed.

## T2-only sample of 40 (seed 23)
| # | name | label | | # | name | label |
|---|---|---|---|---|---|---|
| 1 | NiNet Company DOO | UNSURE | | 21 | OJSC Sibirtelecom | OPERATOR |
| 2 | Bellnet Limited | UNSURE | | 22 | NixiHost.com Incorporated | OPERATOR |
| 3 | Rackhost Zrt. | OPERATOR | | 23 | SILFERNET COMERCIO E SERVICOS LTDA | UNSURE |
| 4 | Douglas FastNet | OPERATOR | | 24 | CloudKleyer Frankfurt GmbH | OPERATOR |
| 5 | Libyan Spider Datacenter | OPERATOR | | 25 | Pikara(STNet, Incorporated) | UNSURE |
| 6 | Hostman LTD | OPERATOR | | 26 | VNET a.s. | UNSURE |
| 7 | HostVision SRL | OPERATOR | | 27 | BRACNet Limited | UNSURE |
| 8 | FDCservers.net | OPERATOR | | 28 | TehranServer | OPERATOR |
| 9 | Hawk Host Inc. | OPERATOR | | 29 | TigrisNet | UNSURE |
| 10 | VoloNet Technologies, Inc | UNSURE | | 30 | FORTHNet Noc | OPERATOR |
| 11 | QTnet,Inc. | UNSURE | | 31 | Agronet LLC | UNSURE |
| 12 | ENTE NAZIONALE ELLENICO PER IL TURISMO public subnet | ORGANISATION | | 32 | LiveOak Fiber | OPERATOR |
| 13 | Xtratelecom, S.A. | OPERATOR | | 33 | Accesos Adinet | UNSURE |
| 14 | Mahsum Celik trading as ServerPlusInternet Sunucu Hizmetleri | OPERATOR | | 34 | INTERKVM HOST SRL | OPERATOR |
| 15 | SMARTHOST, LLC | OPERATOR | | 35 | Cablenet Communication Systems plc | OPERATOR |
| 16 | SingNet Pte Ltd | UNSURE | | 36 | GRUPO SYS4NET, S.L. | UNSURE |
| 17 | MYNET S.R.L. | UNSURE | | 37 | Viking Host B.V. | OPERATOR |
| 18 | Galaxynet Connections Private Limited | OPERATOR | | 38 | PebbleHost | OPERATOR |
| 19 | Wired ISP Inc. | OPERATOR | | 39 | PRO ISP AS | OPERATOR |
| 20 | HAIonNet | UNSURE | | 40 | CariNet, Inc. | UNSURE |

Counts: OPERATOR 23, UNSURE 16, ORGANISATION 1. **Precision (strict, UNSURE against the flag) = 23 / 40 = 57.5%. The D9 bar is 32 of 40 (80%). T2 as written FAILS the gate.** Loose reading (operator or unsure) = 39 / 40, but that is not the gate.

False positives (read as real organisations): 1 of 40: ENTE NAZIONALE ELLENICO PER IL TURISMO public subnet (a tourism body; it matched `net` through "subnet"). The 16 UNSURE names are the second kind of risk: bare `...net` names (NiNet, Bellnet, VoloNet, QTnet, SingNet, MYNET, HAIonNet, SILFERNET, Pikara(STNet), VNET, BRACNet, TigrisNet, Agronet, Accesos Adinet, GRUPO SYS4NET, CariNet). Several of these are known ISPs by reputation, but a name does not say so; Agronet and GRUPO SYS4NET could equally be ordinary companies.

## Where the failure sits: by sub-pattern (the 40 and the 392)
Branches of the T2 regex, assigned in the order stem, then suffix (telecom, host, hosting, server), then suffix `net` only:

| branch | T2-only names (of 392) | in the 40 sample | OPERATOR | UNSURE | ORGANISATION |
|---|---|---|---|---|---|
| stem: `cloud*`, `host*`, `datacent*`, `rechenzentrum`, `fiber`, `fibre`, `isp`, `colo`, `vps`, `dedicated` | 138 | 10 | 10 | 0 | 0 |
| suffix `telecom`, `host`, `hosting`, `server(s)` | 64 | 8 | 8 | 0 | 0 |
| suffix `net` only | 190 | 22 | 5 | 16 | 1 |

(The D9.4 count of 196 for `*net` overlaps the others; my partition is by first matching branch, total 392.) Without the `net` suffix branch the sample reads 18 of 18 operators. With n = 18 the lower one-sided 95% bound on the rate is about 85% (0.05 to the power 1/18), so a clean pass of that part is supported but thin. The `net` suffix branch reads 5 of 22 operators (23%) strict; it fails by itself.

## Cost to real companies
- Among the 4 would-be contacts that carry only T2: Ziply Fiber (telecom, operator), CloudRadium L.L.C (cloud host), Interserver, Inc (hosting), Strato Rechenzentrum, Berlin (datacentre). All four read as operators; none is a real organisation. None came through the `net` suffix.
- In the top 50 by `contact_score`: 3 are T2-only (Strato Rechenzentrum, Interserver, CloudRadium), all operators; 2 carry T1 (Aruba S.p.A. - Cloud Services Farm2, WholeSale Internet, Inc.), both operators by name. So the flag demotes no real organisation in the top 50. The cost of the `net` branch lies in the tail (single-host names), where it would demote the 1 organisation and the UNSURE names into `review` (D8.2: the safe error), not in the top of the list.

## T1 check, fresh seed 23, 20 of 1,046 (D8.2)
Operators: Student City Prepaid Internet, shost-cloud, PERN-Pakistan Education & Research Network, Shenzhen Qianhai bird cloud computing, CIA DE TELECOMUNICACOES DO BRASIL CENTRAL, PingPipe Internet Corporation, Scala Data Centers, Oneprovider.com - Lagos Infrastructure, Giganet Internet, Century Communications - CableHigh Speed Data Division, Planeetta Internet Oy, Padi Internet PT, Servers Australia Pty Ltd (13). Unsure: BEST INTERNET SOLUTION XK, Midcontinent Communications, BG-NETWORK, Brinkster Communications Corporation, BENCHMARK INTERNET GROUP, Evolving Networks Limited, Genious Communications (7). Organisation: 0.
Result: OPERATOR 13 / 20 = 65% strict; operator or unsure 20 / 20; 0 real organisations. There is no D9 bar for T1 at 32/40 scale; D8.2 reported the earlier seed read 9 of 20 operators. 65% is higher than that, and the flag has no false positive here (the unsure names are `communications`, `network`, `internet` names that the D7.2 gate already said cannot pass 90% strict; kept as a cap for that reason).

## Verdict
- **T2 as written does NOT pass the gate** (23 of 40 strict; bar 32).
- D9.5's own fallback applies: keep only the sub-patterns whose own read is clean. Proposal: T2 without the `net` suffix branch (the `[a-z0-9]+net` alternative). That version flags 202 of the 392 names, read 18 of 18 operators in this sample (small sample; one seed; one reviewer). The `net` branch (190 names) should be dropped from the penalty and the cap, or kept as a cap only with an explicit reason (it did flag 5 of 22 operators, 16 unsure, 1 organisation).
- This change needs no stage 3 rerun (D9.5: the columns `operator_shape_t1` and `operator_shape_t2` exist separately for this; the rebuilt T2 would need a column or a regex in stage 4, a data-engineer decision).
- Not verified: the proposed T2-without-net regex has not been run as code; the branch partition above was done in Python with the D9.5 regexes. T1 and T2 shape rarely matter for the top of the list because the leaking operators carry no flagged word (see step 5).
