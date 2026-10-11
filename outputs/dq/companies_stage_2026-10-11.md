# Companies stage report (2026-10-11)

Input hosts rows: 97,758. Output: D:/CyberAgents/data/silver/companies.parquet.

## 1. Headline

**86.38% of scanned services cannot be attributed to a customer** (84,443 of 97,758 hosts rows are not org or cert_o: infrastructure_unresolved, noise or null_org).
Resolved (org + cert_o): 13,315 of 97,758 = 13.62%. Resolved share range check 5.0% to 20.0%: inside.

## 2. Rows and distinct host_ip per identity_source

| identity_source | rows | row share | distinct IPs (D4 precedence) | IP share | distinct IPs (raw) |
|---|---|---|---|---|---|
| org | 12,757 | 13.05% | 11,775 | 13.91% | 11,782 |
| cert_o | 558 | 0.57% | 553 | 0.65% | 556 |
| noise | 1,136 | 1.16% | 1,001 | 1.18% | 1,001 |
| infrastructure_unresolved | 83,110 | 85.02% | 71,130 | 84.03% | 71,283 |
| null_org | 197 | 0.20% | 189 | 0.22% | 190 |

Row shares sum to 100.00% (asserted); precedence IP shares sum to 100.00% (asserted). Distinct host_ip overall: 84,648. IPs present in more than one identity_source: 164.

## 3. Infrastructure breakdown

Infrastructure rows: 84,743 of 97,758 = 86.69% of all rows.

| infra_reason | rows | share of infrastructure rows |
|---|---|---|
| cloud_provider | 39,572 | 46.70% |
| tag_rule | 21,289 | 25.12% |
| ip_pattern | 0 | 0.00% |
| org_exact | 20,895 | 24.66% |
| org_prefix | 784 | 0.93% |
| org_pattern | 63 | 0.07% |
| org_keyword | 2,140 | 2.53% |

ip_pattern rows: 0 (expected 0). Seven values; set equals the hosts contract set (asserted).

## 4. Companies

Total companies: 5,790 (hosts rows 97,758; companies <= hosts asserted).

| identity_source | identity_confidence | companies | share |
|---|---|---|---|
| cert_o | low | 403 | 6.96% |
| org | high | 5,387 | 93.04% |

Companies named under both sources (merged): 18 (78 org rows + 62 cert_o rows).

## 5. Host-count distribution per company

| host_count bucket | companies | share of companies | member rows | share of member rows |
|---|---|---|---|---|
| 1 (singleton) | 4,169 | 72.00% | 4,169 | 31.31% |
| 2 | 687 | 11.87% | 1,374 | 10.32% |
| 3 to 5 | 568 | 9.81% | 2,085 | 15.66% |
| 6 to 20 | 337 | 5.82% | 3,242 | 24.35% |
| 21 to 100 | 22 | 0.38% | 819 | 6.15% |
| over 100 | 7 | 0.12% | 1,626 | 12.21% |

median 1, p90 4, p99 16, max 330 (quantile_disc, so values are actual host counts).

## 6. Raw spellings

Distinct raw org strings 5,508 + distinct raw cert O strings 429 = 5,937 collapse to 5,790 companies (147 merges by normalisation).

Companies with the most raw spellings (merge review list):

| company_name | raw spellings | host_count | spellings |
|---|---|---|---|
| ZOHO | 5 | 95 | ZOHO | ZOHO Corp | ZOHO Corporation Private Limited | Zoho Corp | Zoho Corporation |
| True Internet Co., Ltd. | 4 | 21 | True Internet Co., Ltd. | True Internet Co.Ltd. | True Internet Corporation Co. Ltd. | True internet Co., Ltd. |
| BHARTI-AIRTEL | 3 | 15 | BHARTI Airtel Ltd. | BHARTI-AIRTEL | Bharti Airtel Limited |
| Blackline Systems, Inc. | 3 | 16 | BLACKLINE SYSTEMS, INC. | BlackLine Systems, Inc. | Blackline Systems, Inc. |
| PT. First Media, Tbk. | 3 | 5 | PT. First Media, Tbk | PT. First Media, Tbk. | PT. First Media,Tbk |
| RADWARE INC. | 3 | 10 | RADWARE INC. | Radware Limited | Radware Ltd |
| SoftBank Corp. | 3 | 13 | SOFTBANK CorP. | SOFTBANK Corp. | SoftBank Corp. |
| TIM S.A. | 3 | 14 | TIM S A | TIM S.A. | TIM S/A |
| xTom GmbH | 3 | 16 | xTom | xTom GmbH | xTom Pty Ltd |
| Zen Internet Ltd | 3 | 9 | Zen Internet | Zen Internet Limited | Zen Internet Ltd |

## 7. Top 20 companies by host_count

| company_name | source | confidence | host_count | distinct IPs | distinct ports | country |
|---|---|---|---|---|---|---|
| Egnyte Inc. | org | high | 330 | 136 | 121 | US |
| Fiserv Solutions, LLC | org | high | 328 | 83 | 106 | US |
| Wal-Mart Stores, Inc. | org | high | 248 | 157 | 63 | US |
| Avago Technologies U.S. Inc. | org | high | 236 | 166 | 190 | US |
| Salesforce.com, Inc. | org | high | 181 | 180 | 4 | US |
| ServiceNow, Inc. | org | high | 155 | 155 | 3 | US |
| TGS Management Company, LLC | org | high | 148 | 87 | 62 | US |
| ZOHO | org | high | 95 | 95 | 5 | US |
| Los Angeles Municipal Court | org | high | 86 | 85 | 78 | US |
| Equifax, Inc. | org | high | 70 | 70 | 70 | US |
| GUANGZHOUSHI GUANGBODIANSHIWANGLUO CO.LTD | org | high | 64 | 53 | 19 | CN |
| The Prudential Insurance Company of America | org | high | 58 | 58 | 55 | US |
| ULTIMATE SOFTWARE GROUP | org | high | 53 | 35 | 32 | US |
| NEW YORK MERCANTILE EXCHANGE | org | high | 42 | 41 | 42 | US |
| Adobe Inc. | org | high | 27 | 22 | 2 | US |
| DIGITAL SNAP | org | high | 26 | 25 | 9 | IN |
| Office of Info.Tech. Admin. for Educational Development | org | high | 26 | 26 | 10 | TH |
| Accenture LLP | org | high | 25 | 24 | 3 | US |
| KeyBank National Association | org | high | 25 | 24 | 25 | US |
| NCR Corporation | org | high | 24 | 24 | 20 | US |

## 8. Noise

Noise rows in hosts: 1,136. Attributed to a company through org_norm: 33 rows over 24 companies; 4 companies have noise_host_share >= 0.5.
org_norm values with noise rows but no company: 94 names, 1,103 rows (includes infrastructure names; noise on infrastructure never creates a company).

| company_name | host_count | noise_host_count | noise_host_share |
|---|---|---|---|
| SC Lithuanian Radio and TV Center | 2 | 3 | 0.6 |
| Civo LTD | 1 | 1 | 0.5 |
| Jummah-Mosque-Str | 1 | 1 | 0.5 |
| WebSP - Comercio e Prestacao de Servicos Informaticos, Lda | 1 | 1 | 0.5 |
| ipNX NIGERIA LIMITED | 2 | 1 | 0.333 |
| JSC "RU-CENTER" | 2 | 1 | 0.333 |
| Randers Kommune | 2 | 1 | 0.333 |
| GlobalConnect A/S | 4 | 1 | 0.2 |
| Cityfibre Limited | 5 | 1 | 0.167 |
| Cloud Web Manage | 5 | 1 | 0.167 |

## 9. Row-count reconciliation hosts to companies

97,758 hosts rows = 83,110 infrastructure_unresolved + 1,136 noise + 197 null_org (84,443 rows that never create a company) + 13,315 member rows (12,757 org + 558 cert_o).
The 13,315 member rows group into 5,790 companies; 7,525 rows are absorbed into an existing company by exact name_norm. sum(host_count) = 13,315 equals member rows (asserted). Nothing else differs: companies 5,790 <= hosts 97,758.

## 10. Output file

Path: D:/CyberAgents/data/silver/companies.parquet; rows: 5,790. Previous layer (hosts rows): 97,758.

Null rates:

| column | null rate |
|---|---|
| company_id | 0.0% |
| company_name | 0.0% |
| name_norm | 0.0% |
| identity_source | 0.0% |
| identity_confidence | 0.0% |
| org_host_count | 0.0% |
| cert_o_host_count | 0.0% |
| host_count | 0.0% |
| distinct_host_ips | 0.0% |
| distinct_port_count | 0.0% |
| country_code | 0.0% |
| country_count | 0.0% |
| noise_host_count | 0.0% |
| noise_host_share | 0.0% |

5 random company rows:

- [1] company_id=1925fe7f36aed68d, company_name=NETWISE INFORMATICA LTDA, name_norm=netwise informatica ltda, identity_source=org, identity_confidence=high, org_host_count=1, cert_o_host_count=0, host_count=1, distinct_host_ips=1, distinct_port_count=1, country_code=BR, country_count=1, noise_host_count=0, noise_host_share=0.0
- [2] company_id=73b2f19b04c4b98a, company_name=2degrees, name_norm=2degrees, identity_source=org, identity_confidence=high, org_host_count=4, cert_o_host_count=0, host_count=4, distinct_host_ips=4, distinct_port_count=1, country_code=NZ, country_count=1, noise_host_count=0, noise_host_share=0.0
- [3] company_id=832323039f1c8895, company_name=Mena WiMAX Core, name_norm=mena wimax core, identity_source=org, identity_confidence=high, org_host_count=1, cert_o_host_count=0, host_count=1, distinct_host_ips=1, distinct_port_count=1, country_code=BH, country_count=1, noise_host_count=0, noise_host_share=0.0
- [4] company_id=9348e30986160144, company_name=GetMegaFlip SRL, name_norm=getmegaflip, identity_source=org, identity_confidence=high, org_host_count=1, cert_o_host_count=0, host_count=1, distinct_host_ips=1, distinct_port_count=1, country_code=DE, country_count=1, noise_host_count=0, noise_host_share=0.0
- [5] company_id=bc02f7ea3fb79532, company_name=AutoZone, Inc., name_norm=autozone, identity_source=cert_o, identity_confidence=low, org_host_count=0, cert_o_host_count=1, host_count=1, distinct_host_ips=1, distinct_port_count=1, country_code=FR, country_count=1, noise_host_count=0, noise_host_share=0.0
