# Data quality: companies (2026-10-11)

**PASS**: 61/61 checks passed

| result | check | evidence |
|---|---|---|
| PASS | column 'company_id' type VARCHAR | actual VARCHAR |
| PASS | column 'company_id' has no nulls | 0 nulls |
| PASS | column 'company_name' type VARCHAR | actual VARCHAR |
| PASS | column 'company_name' has no nulls | 0 nulls |
| PASS | column 'name_norm' type VARCHAR | actual VARCHAR |
| PASS | column 'name_norm' has no nulls | 0 nulls |
| PASS | column 'identity_source' type VARCHAR | actual VARCHAR |
| PASS | column 'identity_source' has no nulls | 0 nulls |
| PASS | column 'identity_confidence' type VARCHAR | actual VARCHAR |
| PASS | column 'identity_confidence' has no nulls | 0 nulls |
| PASS | column 'org_host_count' type INTEGER | actual INTEGER |
| PASS | column 'org_host_count' has no nulls | 0 nulls |
| PASS | column 'org_host_count' min 0 | 0 violations |
| PASS | column 'cert_o_host_count' type INTEGER | actual INTEGER |
| PASS | column 'cert_o_host_count' has no nulls | 0 nulls |
| PASS | column 'cert_o_host_count' min 0 | 0 violations |
| PASS | column 'host_count' type INTEGER | actual INTEGER |
| PASS | column 'host_count' has no nulls | 0 nulls |
| PASS | column 'host_count' min 1 | 0 violations |
| PASS | column 'distinct_host_ips' type INTEGER | actual INTEGER |
| PASS | column 'distinct_host_ips' has no nulls | 0 nulls |
| PASS | column 'distinct_host_ips' min 1 | 0 violations |
| PASS | column 'distinct_port_count' type INTEGER | actual INTEGER |
| PASS | column 'distinct_port_count' has no nulls | 0 nulls |
| PASS | column 'distinct_port_count' min 1 | 0 violations |
| PASS | column 'country_code' type VARCHAR | actual VARCHAR |
| PASS | column 'country_count' type INTEGER | actual INTEGER |
| PASS | column 'country_count' has no nulls | 0 nulls |
| PASS | column 'country_count' min 0 | 0 violations |
| PASS | column 'noise_host_count' type INTEGER | actual INTEGER |
| PASS | column 'noise_host_count' has no nulls | 0 nulls |
| PASS | column 'noise_host_count' min 0 | 0 violations |
| PASS | column 'noise_host_share' type DOUBLE | actual DOUBLE |
| PASS | column 'noise_host_share' has no nulls | 0 nulls |
| PASS | column 'noise_host_share' min 0 | 0 violations |
| PASS | column 'noise_host_share' max 1 | 0 violations |
| PASS | key ['company_id'] is unique | 0 duplicate rows |
| PASS | row count <= data/silver/hosts.parquet | this=5,790 other=97,758 |
| PASS | denylist leakage in 'name_norm' (shared rules) | none |
| PASS | exactly 14 columns (D8.4) | got 14, expected 14 |
| PASS | name_norm is unique (join key for stage 3, D8.5) | got 0, expected 0 |
| PASS | company_id is 16 lowercase hex characters | got 0, expected 0 |
| PASS | company_id equals substr(sha256(name_norm), 1, 16) on every row (D8.3) | got 0, expected 0 |
| PASS | company_name and name_norm are non-empty and trimmed (D8.8 rule 5) | got 0, expected 0 |
| PASS | identity_source in (org, cert_o) | got 0, expected 0 |
| PASS | identity_confidence in (high, low) | got 0, expected 0 |
| PASS | identity_source org exactly when org_host_count > 0 (D8.3) | got 0, expected 0 |
| PASS | identity_confidence high exactly when org_host_count > 0, low exactly when org_host_count = 0 (D8.1) | got 0, expected 0 |
| PASS | host_count equals org_host_count + cert_o_host_count | got 0, expected 0 |
| PASS | distinct_host_ips and distinct_port_count are at most host_count | got 0, expected 0 |
| PASS | country_count = 0 exactly when country_code is null | got 0, expected 0 |
| PASS | country_count at most distinct_host_ips (an IP has one country) | got 0, expected 0 |
| PASS | country_code is two upper-case letters when present | got 0, expected 0 |
| PASS | noise_host_share equals noise_host_count / (noise_host_count + host_count) | got 0, expected 0 |
| PASS | noise_host_count is 0 for a company with no org host (noise is attributed through org_norm, D8.4) | got 0, expected 0 |
| PASS | cross-file, every company name_norm has at least one hosts row with identity_source org or cert_o (no company of only noise or infrastructure hosts) | got 0, expected 0 |
| PASS | cross-file, every member name_norm in hosts exists in companies | got 0, expected 0 |
| PASS | cross-file, sum(host_count) equals hosts rows with identity_source org or cert_o (D8.8 rule 7) | got 0, expected 0 |
| PASS | cross-file, sum(org_host_count) equals hosts rows with identity_source org | got 0, expected 0 |
| PASS | cross-file, sum(cert_o_host_count) equals hosts rows with identity_source cert_o | got 0, expected 0 |
| PASS | resolved share (sum(host_count) / hosts rows) inside 5% to 20% (D4 range; measured 13.62%) | got 0, expected 0 |

## Extra checks (check_companies_extra.py)

**PASS**: 5/5 extra checks passed

| result | check | evidence |
|---|---|---|
| PASS | reconciliation hosts = never-create + member; member rows group into companies | hosts 97,758 = never-create 84,443 + member 13,315; sum(host_count) 13,315; companies 5,790 vs distinct member name_norm 5,790; unexpected identity_source {} |
| PASS | independent recompute of every company column from hosts: 0 disagreements | 5,790 reference companies vs 5,790 rows; missing 0, extra 0, duplicate name_norm 0; column disagreements {}; examples [] [] [] |
| PASS | company_id equals hashlib sha256(name_norm)[:16] on every row | 0 mismatches; e.g. [] |
| PASS | denylist leakage in company_name and name_norm (shared rules, org text) | 0 hits over 5,790 companies; none |
| PASS | resolved share 5.0% to 20.0% | resolved 13,315 of 97,758 = 13.62%; headline unresolved 86.38% |
