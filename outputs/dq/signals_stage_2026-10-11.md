# Signals stage report (2026-10-11)

Input companies rows: 5,790; member host rows aggregated: 13,315. Output: D:/CyberAgents/data/gold/signals.parquet. Signal list per D9.4 (PROVISIONAL until the owner approves).

## 1. Row counts

companies 5,790 = signals 5,790 (asserted; company_id unique).

## 2. Company-level coverage (share of all companies) and comparison with the D9.4 table

| signal | companies firing | share | D9.4 count | difference | flag |
|---|---|---|---|---|---|
| host_signals_blind | 180 | 3.11% | 180 | +0 |  |
| is_singleton | 4,169 | 72.00% | 4,169 | +0 | above 50% |
| in_territory | 1,346 | 23.25% | 1,346 | +0 |  |
| named_registrant | 5,387 | 93.04% | 5,387 | +0 | above 50% |
| sensitive_stack | 55 | 0.95% | 55 | +0 | below 1% |
| operator_shape_t1 | 1,046 | 18.07% | 1,046 | +0 |  |
| operator_shape_t2 | 738 | 12.75% |  |  |  |
| operator_name_shape | 1,438 | 24.84% | 1,438 | +0 |  |
| kev_exposed | 462 | 7.98% | 462 | +0 |  |
| cert_expired_or_soon | 373 | 6.44% | 373 | +0 |  |
| eol_stack | 352 | 6.08% | 352 | +0 |  |
| legacy_tls | 209 | 3.61% | 209 | +0 |  |
| risky_service_exposed | 226 | 3.90% | 226 | +0 |  |
| risky_non_ssh_exposed | 68 | 1.17% | 68 | +0 |  |
| exposed_and_outdated | 48 | 0.83% | 48 | +0 | below 1% |
| max_cvss_band = 3 | 460 | 7.94% | 460 | +0 |  |
| max_cvss_band = 2 | 209 | 3.61% | 209 | +0 |  |
| max_cvss_band = 1 | 70 | 1.21% | 70 | +0 |  |
| footprint_band = 1 | 1,215 | 20.98% | 1,215 | +0 |  |
| footprint_band = 2 | 318 | 5.49% | 318 | +0 |  |
| footprint_band = 3 | 27 | 0.47% | 27 | +0 | below 1% |
| T2 only (T2 and not T1) | 392 | 6.77% | 392 | +0 |  |
| risky_service_exposed SSH only | 158 | 2.73% | 158 | +0 |  |
| any urgency signal | 1,294 | 22.35% | 1,294 | +0 |  |
| strong urgency | 662 | 11.43% | 662 | +0 |  |

Companies with any CVSS value: 739 (D9.4: 739). footprint_band 0 (one IP): 4,230 (D9.4: 4,230). in_territory is a PLACEHOLDER (US only) until the owner supplies the territory list; T2 is computed, not yet part of any penalty.
in_territory null (country_code null): 0.

## 3. Counted-host reconciliation (D6.4)

Member host rows 13,315 = counted 13,067 + non-counted (CDN-tagged cert_o) 248; sum(host_count) = 13,315 equals member host rows (asserted); sum(counted_host_count) equals counted (asserted). Companies with at least one non-counted host: 192 (D9.4: 192); host-blind companies: 180 (D9.4: 180).
Member host rows with the certificate condition by branch: expired boolean 286, expiring within 30 days (boolean false) 150 (D9.4 text: 286 expired and 150 expiring; it did not say whether the 150 are exclusive of the 286).

## 4. Top 15 companies by number of firing urgency signals (kev_exposed, cert_expired_or_soon, eol_stack, legacy_tls, risky_service_exposed, exposed_and_outdated; ties by host_count then company_id)

| company_name | urgency signals firing | host_count | counted | kev hosts | max_cvss | risky_ports | operator shape |
|---|---|---|---|---|---|---|---|
| Strato Rechenzentrum, Berlin | 6 | 15 | 15 | 1 | 9.8 | [22, 3306] | True |
| Aruba S.p.A. - Cloud Services Farm2 | 5 | 11 | 11 | 3 | 9.8 | [27017] | True |
| Office of Info.Tech. Admin. for Educational Development | 4 | 26 | 26 | 2 | 10.0 | [] | False |
| CloudRadium L.L.C | 4 | 16 | 16 | 1 | 9.8 | [22] | True |
| Interserver, Inc | 4 | 16 | 16 | 1 | 9.8 | [445] | True |
| Digital Core Technology Co., Limited | 4 | 15 | 15 | 1 | 7.5 | [] | False |
| UK Next Generation Cloud Server (NGCS) | 4 | 14 | 14 | 1 | 7.7 | [] | True |
| Telia Eesti AS | 4 | 13 | 13 | 0 | 9.8 | [22] | False |
| TimeWeb Ltd. | 4 | 11 | 11 | 3 | 9.8 | [] | False |
| Beijing Volcano Engine Technology Co., Ltd. | 4 | 11 | 11 | 0 | 9.8 | [22] | False |
| Leaseweb Canada Inc. | 4 | 9 | 9 | 0 | None | [6379] | False |
| Beijing Jingdong 360 Degree E-commerce Co., Ltd. | 4 | 8 | 8 | 2 | 9.8 | [22, 27017] | False |
| Leaseweb Deutschland GmbH | 4 | 6 | 6 | 2 | 9.8 | [22] | False |
| Fastmos Co Limited | 4 | 5 | 5 | 0 | 7.2 | [3306] | False |
| SERVERS TECH FZCO | 4 | 5 | 5 | 2 | 7.7 | [22] | True |

## 5. Output file

Path: D:/CyberAgents/data/gold/signals.parquet; rows: 5,790; columns: 36. Previous layer (companies rows): 5,790; difference 0 (asserted: one row per company, company_id unique, no fan-out).

Null rates (all columns, worst first):

| column | null rate |
|---|---|
| max_cvss | 87.24% |
| company_id | 0.0% |
| company_name | 0.0% |
| name_norm | 0.0% |
| identity_source | 0.0% |
| identity_confidence | 0.0% |
| host_count | 0.0% |
| distinct_host_ips | 0.0% |
| country_code | 0.0% |
| noise_host_count | 0.0% |
| noise_host_share | 0.0% |
| counted_host_count | 0.0% |
| host_signals_blind | 0.0% |
| is_singleton | 0.0% |
| in_territory | 0.0% |
| named_registrant | 0.0% |
| footprint_size | 0.0% |
| footprint_band | 0.0% |
| sensitive_stack | 0.0% |
| operator_shape_t1 | 0.0% |
| operator_shape_t2 | 0.0% |
| operator_name_shape | 0.0% |
| kev_exposed | 0.0% |
| kev_host_count | 0.0% |
| max_cvss_band | 0.0% |
| cert_expired_or_soon | 0.0% |
| cert_issue_host_count | 0.0% |
| eol_stack | 0.0% |
| eol_host_count | 0.0% |
| legacy_tls | 0.0% |
| legacy_tls_host_count | 0.0% |
| risky_service_exposed | 0.0% |
| risky_non_ssh_exposed | 0.0% |
| risky_service_host_count | 0.0% |
| risky_ports | 0.0% |
| exposed_and_outdated | 0.0% |

5 random rows:

- [1] company_id=1925fe7f36aed68d, company_name=NETWISE INFORMATICA LTDA, name_norm=netwise informatica ltda, identity_source=org, identity_confidence=high, host_count=1, distinct_host_ips=1, country_code=BR, noise_host_count=0, noise_host_share=0.0, counted_host_count=1, host_signals_blind=False, is_singleton=True, in_territory=False, named_registrant=True, footprint_size=1, footprint_band=0, sensitive_stack=False, operator_shape_t1=False, operator_shape_t2=False, operator_name_shape=False, kev_exposed=False, kev_host_count=0, max_cvss=None, max_cvss_band=0, cert_expired_or_soon=False, cert_issue_host_count=0, eol_stack=False, eol_host_count=0, legacy_tls=False, legacy_tls_host_count=0, risky_service_exposed=False, risky_non_ssh_exposed=False, risky_service_host_count=0, risky_ports=[], exposed_and_outdated=False
- [2] company_id=73b2f19b04c4b98a, company_name=2degrees, name_norm=2degrees, identity_source=org, identity_confidence=high, host_count=4, distinct_host_ips=4, country_code=NZ, noise_host_count=0, noise_host_share=0.0, counted_host_count=4, host_signals_blind=False, is_singleton=False, in_territory=False, named_registrant=True, footprint_size=4, footprint_band=1, sensitive_stack=False, operator_shape_t1=False, operator_shape_t2=False, operator_name_shape=False, kev_exposed=False, kev_host_count=0, max_cvss=None, max_cvss_band=0, cert_expired_or_soon=False, cert_issue_host_count=0, eol_stack=False, eol_host_count=0, legacy_tls=False, legacy_tls_host_count=0, risky_service_exposed=False, risky_non_ssh_exposed=False, risky_service_host_count=0, risky_ports=[], exposed_and_outdated=False
- [3] company_id=832323039f1c8895, company_name=Mena WiMAX Core, name_norm=mena wimax core, identity_source=org, identity_confidence=high, host_count=1, distinct_host_ips=1, country_code=BH, noise_host_count=0, noise_host_share=0.0, counted_host_count=1, host_signals_blind=False, is_singleton=True, in_territory=False, named_registrant=True, footprint_size=1, footprint_band=0, sensitive_stack=False, operator_shape_t1=False, operator_shape_t2=False, operator_name_shape=False, kev_exposed=False, kev_host_count=0, max_cvss=None, max_cvss_band=0, cert_expired_or_soon=False, cert_issue_host_count=0, eol_stack=False, eol_host_count=0, legacy_tls=False, legacy_tls_host_count=0, risky_service_exposed=False, risky_non_ssh_exposed=False, risky_service_host_count=0, risky_ports=[], exposed_and_outdated=False
- [4] company_id=9348e30986160144, company_name=GetMegaFlip SRL, name_norm=getmegaflip, identity_source=org, identity_confidence=high, host_count=1, distinct_host_ips=1, country_code=DE, noise_host_count=0, noise_host_share=0.0, counted_host_count=1, host_signals_blind=False, is_singleton=True, in_territory=False, named_registrant=True, footprint_size=1, footprint_band=0, sensitive_stack=False, operator_shape_t1=False, operator_shape_t2=False, operator_name_shape=False, kev_exposed=False, kev_host_count=0, max_cvss=None, max_cvss_band=0, cert_expired_or_soon=False, cert_issue_host_count=0, eol_stack=False, eol_host_count=0, legacy_tls=False, legacy_tls_host_count=0, risky_service_exposed=False, risky_non_ssh_exposed=False, risky_service_host_count=0, risky_ports=[], exposed_and_outdated=False
- [5] company_id=bc02f7ea3fb79532, company_name=AutoZone, Inc., name_norm=autozone, identity_source=cert_o, identity_confidence=low, host_count=1, distinct_host_ips=1, country_code=FR, noise_host_count=0, noise_host_share=0.0, counted_host_count=0, host_signals_blind=True, is_singleton=True, in_territory=False, named_registrant=False, footprint_size=1, footprint_band=0, sensitive_stack=False, operator_shape_t1=False, operator_shape_t2=False, operator_name_shape=False, kev_exposed=False, kev_host_count=0, max_cvss=None, max_cvss_band=0, cert_expired_or_soon=False, cert_issue_host_count=0, eol_stack=False, eol_host_count=0, legacy_tls=False, legacy_tls_host_count=0, risky_service_exposed=False, risky_non_ssh_exposed=False, risky_service_host_count=0, risky_ports=[], exposed_and_outdated=False
