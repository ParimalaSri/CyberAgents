# Data notes

Filled from `outputs/profile_sample_100k.md` and decisions D1-D4 in `docs/ARCHITECTURE.md`. Figures are from a head-of-file 100K sample unless stated; the spread sample (D3) will replace them.

- Source: Shodan-style internet-scan dump, JSON Lines, one row per service banner on one IP:port. Local file `D:\Cyber_DataSet\2026-09-14T10-00-00.json.zst` (12.36 GB compressed, about 84.6 GB decompressed, estimated 7.6M to 8.9M rows, about one hour of scanning). Read in place; never copied into the repo. The brief's link is a different snapshot (2026-10-08).
- Rows / columns: 78 top-level columns; about 25 are common, the rest are sparse protocol structs (over 92% null). Dev sample: `data/sample/` (spread sample, 100K rows). `data/raw/sample_100k.jsonl` is the old head-of-file sample.
- Key columns for FIT signals: normalised `org` (after denylist), `ssl.cert.subject.O`, `location.country_code`, non-infrastructure `domains`/`hostnames`, `product`/`os`/`cpe23`, tags (`database`, `ics`, `medical`, `iot`).
- Key columns for URGENCY / risk signals: `vulns` (max CVSS, KEV), `ssl.cert.expired`/`expires`/`versions`, tags `eol-product`/`eol-os`, risky ports. `timestamp` is NOT usable (whole file is about one hour).
- Known data-quality issues: about 87% of rows belong to cloud, CDN, hosting or ISP organisations; org name variants; 587 IPv6 rows with null `ip_str`; about 4% repeated ip:port rows; CVE lists inferred from banner versions; honeypot and RAT noise; certificate date sentinels; port bursts by file position. Full list: `docs/ISSUES.md`.
- Denylist candidates (most frequent org/ISP/CDN values): `context/denylist.txt` (top: Google LLC, Incapsula Inc, Amazon.com Inc., Aliyun Computing, Cloudflare, Aceville Pte. Ltd., Internet Rimon, Korea Telecom). Decisions D1/D2 keep IBM, Oracle, Microsoft, security vendors and website builders on it.
