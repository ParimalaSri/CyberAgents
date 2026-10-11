# CyberIntel architecture

Owner: senior-data-engineer. Decision records use the format
`Context | Decision | Alternatives considered | Consequences`. A decision here is a recommendation
until the project owner approves it.

## Data decisions (D1-D4)

Decided 2026-10-11 on branch `feat/senior-data-engineer/data-decisions`. Status: proposed, awaiting owner approval.

### Evidence base
- `outputs/profile_sample_100k.md`: the first 100,000 lines of the dump (1.11 GB). This is the "head sample".
- A seek-based probe of the full file `D:/Cyber_DataSet/2026-09-14T10-00-00.json` (84.61 GB, outside the repo),
  run by senior-data-engineer. It read 21 windows of 4 MB at evenly spaced offsets from 0% to 100%, about 88 MB in total.
  It parsed 9,239 complete lines, with 0 parse errors. Only that one file was opened. The script is kept outside
  the repo, in the session scratchpad, so it is not a pipeline artefact.

| metric | head sample (100K) | full-file probe (9,239 rows, 21 windows) |
|---|---|---|
| timestamp range | 09:54:28 to 10:06:32 | 09:59:10 to 11:00:12 (about 61 min) |
| org on denylist (exact) | 86.8% | 85.7% |
| rows kept (org, isp, cloud.provider all off the list) | 9.5% | 10.5% (per-window range 3.6% to 20.2%) |
| Google LLC as org | 33.1% | 27.5% |
| port 12304 | 10.6% | 1.7% (22.6% in the 0% window, absent from the other top-3s) |
| has ssl.cert / cert subject O | 7.9% / 1.7% | 8.6% / 2.0% |
| has vulns | 3.2% | 3.0% (per-window range 1.2% to 7.2%) |
| cloud or cdn tag | 42.0% cloud, 26.1% cdn | 66.3% either |

Ordering: across offsets, each window's timestamps move forward. Inside a window, 50.2% of adjacent pairs go
backwards, so rows are interleaved locally rather than sorted. Every window covers first IP octets of about 1 to 223,
so the file is not sorted by IP. Each 4 MB window has its own dominant high port: 12304, 44333, 12225, 3051, 9988,
7001 and 18065 all appear. That pattern is what a scanner sweeping one port at a time produces.
Estimated size: 7.6M to 8.9M rows, from 11.1 KB per row in the head sample and 9.5 KB per row in the probe.

### D1. IBM, Oracle and Microsoft stay on the denylist
- **Context.** These three names belong to real enterprises. However, the `org` field holds the owner of the IP
  block, not the tenant. Microsoft Corporation has 722 rows in the head sample. In the probe, 57 of 61 Microsoft rows
  (93%) and 10 of 10 Oracle rows carry a `cloud`/`cdn` tag or a `cloud.provider` value. That makes them Azure and OCI
  tenant ranges. IBM had 11 rows in the probe, none cloud-tagged, which is negligible volume. All three also sell
  security products (Defender/Sentinel, IBM Security, OCI security), so they are not realistic buyers for a
  cybersecurity software vendor.
- **Decision.** Keep all three on the denylist. Treat their rows as infrastructure: no company is created from
  their `org` value. Change matching from exact to a normalised prefix family (`microsoft*`, `oracle*`, `ibm`,
  `ibm cloud`, `softlayer*`) so that variant spellings are caught.
- **Alternatives considered.** (a) Remove them and let them score as accounts. Rejected: at least 93% of the rows
  are cloud tenants, so the score would rate Microsoft on its customers' exposure and give a false `why`.
  (b) Keep only the rows without a cloud tag. Rejected for now: it gains at most one account (IBM, 11 rows) and
  adds a special case.
- **Consequences.** At most three real enterprise accounts are lost, which fits the rule of precision over recall.
  If the owner wants them as named accounts, add them by hand to a seed list, not through scan data.

### D2. Security vendors and website builders are excluded, not kept as channel or competitor accounts
- **Context.** Zscaler (513 head rows), Incapsula/Imperva (18,538 head rows, and 2,452 of 2,452 probe rows
  cloud/cdn-tagged), Palo Alto, Fastly, Cloudflare and Akamai operate proxy, edge or egress networks for their
  customers. Shopify, Squarespace, Wix, Vercel and Bitly host other people's sites and links (Bitly has 49 probe
  rows). Their `org` rows describe their customers' traffic, not their own estate. The output is a ranked list of
  **buyers**. A competitor or channel partner is a different list with a different `why`, and scan data provides
  no evidence for a partnership.
- **Decision.** Exclude both groups as infrastructure in the same way as D1, with
  `infra_reason = security_edge` or `website_platform`. Do not create channel or competitor accounts.
  In a later version, the fact that a *resolved* tenant sits behind a WAF/CDN (`http.waf` is set on 11,495 head rows)
  may be used as a fit or maturity signal. It is not an account.
- **Alternatives considered.** (a) Keep them as `exclude`-band accounts labelled "competitor". Rejected: their
  scores would be built from tenant exposure and would mislead anyone reading the list. (b) Keep them as channel
  accounts. Rejected: nothing in the data supports a channel motion, and it is outside the stated output.
- **Consequences.** The `exclude` band is reserved for resolved companies that fail an ICP or noise rule (honeypot,
  C2, RAT modules). Infrastructure never becomes a company, so it never appears in the account list. It is counted
  in the D4 report instead.

### D3. The head sample is not acceptable for development; switch to a seek-spread sample
- **Context.** The full file is a single hourly export of about 61 minutes on 2026-09-14. It is not a multi-day
  crawl. It moves forward in time by offset, is interleaved locally, and has port-sweep bursts of a few MB each.
  Org mix and infrastructure share are stable between the head sample and the probe (86.8% vs 85.7% denylisted).
  Port mix is not: port 12304 is 10.6% of the head sample but 1.7% of the probe. The head sample is the first 1.3%
  of the file and covers about 12 of the 61 minutes.
- **Decision.** Replace the dev sample with a **seek-spread sample**: 1,000 evenly spaced byte offsets with a
  fixed seed for jitter, taking 100 complete lines after each one, for 100,000 rows and about 1 GB read.
  This breaks up the port bursts (about 400 lines per 4 MB) and covers the whole hour. A data-integrator utility in
  `scripts/` builds it and writes a new file. The existing `sample_100k.jsonl` must not be modified. Only the owner
  places files under `data/raw/`, or must approve the target path, because CLAUDE.md says nothing writes to
  `data/raw/`. Keep the head sample for reproducing the existing profile.
  **Recency: the timestamp is dropped as an urgency signal for the whole dataset**, not only for the sample.
  Sixty-one minutes carries no "right now" information. Urgency comes from cert expiry, KEV/CVSS, EOL tags,
  legacy TLS and risky ports.
- **Alternatives considered.** (a) Keep the head sample. Rejected: it over-weights one port sweep and would bias
  every port-based signal and the score calibration. (b) A true uniform random sample (reservoir over about 8M rows).
  Rejected for dev because it scans all 84 GB. It is acceptable later as a one-off validation if the owner wants one.
  (c) Contiguous chunks of 10,000 lines. Rejected because each chunk inherits a burst.
- **Consequences.** Re-run the profile on the spread sample before `1_clean` is written, and confirm that the
  denylist share is about 86% and port 12304 is about 2%. Signals that depend on port must be calibrated only on the
  spread sample. The prod run uses the full file. The 100K-row cost and DQ ceilings are unchanged.

### D4. Company identity: non-infrastructure `org` first, then cert subject O; hostnames are evidence only in v1
- **Context.** `org` is 99.83% populated, but about 86% of it is infrastructure. Tenant identity is scarce. Cert
  subject O is on 1.7% to 2.0% of rows, and on infrastructure rows it appears on only 105 of 9,239 probe rows (1.1%).
  Its top values there are defaults or vendor names: Google Inc 13, Huawei 7, Microsoft 6, Plesk 3, Acme Co 2,
  Default Company Ltd 2. Real tenants are rare (Bayerische Motoren Werke AG, 2 rows). Non-provider domains appear on
  up to 14% of infrastructure rows (1,292 probe rows). That figure is an upper bound because the provider-domain
  filter used had only 10 entries, and the precision of a domain as a company key is unmeasured. Reverse DNS on
  shared hosting names the host, not the owner.
- **Decision.** A row's identity is resolved in this order. The first rule that matches wins, and the source is
  recorded in `identity_source`.
  1. `noise`: tag honeypot/c2/tor/compromised, or a RAT/C2 `_shodan.module`. Never a company.
  2. `org`: normalised `org` (case, punctuation, legal suffix) that is not infrastructure. Infrastructure means a
     denylist family match on org, isp or cloud.provider, OR a non-null `cloud.provider`, OR a `cloud`/`cdn` tag.
  3. `cert_o`: the row is infrastructure, and `ssl.cert.subject.O`, after normalisation, is not a default or vendor
     value. A default-value list is needed: acme co, default company ltd, internet widgits pty ltd, plesk, plus the
     denylisted vendors.
  4. `infrastructure_unresolved`: the row is infrastructure with no usable tenant evidence. Kept in hosts, never a company.
  5. `null_org`: org is null (0.17%) and there is no cert O. Unresolved.
  When a non-infrastructure `org` and a cert O disagree, `org` wins and the cert O is stored as evidence.
  `company_id` is a stable hash of the normalised name, whichever source it came from, so `Fiserv` from org and from
  a cert merge into one company. Hostnames and domains are attached as evidence only in v1. Promoting them to rule 3b
  requires a check by data-quality-engineer: hand-review 50 random domain-derived tenants, with at least 90% being
  real, distinct companies.
- **Unresolved reporting.** `2_companies` prints, and writes to `outputs/dq/companies_<date>.md`, the row share and
  distinct host_ip share for each `identity_source`, plus the `infra_reason` breakdown (hyperscaler, security_edge,
  website_platform, hosting, isp, tag_rule). The shares must sum to 100%. The companies contract flags a resolved
  row share outside 5% to 20% (expected about 10% to 12%). The same headline number ("about 88% of scanned services
  sit on shared infrastructure and cannot be attributed to a customer") goes into the README and the app footer.
- **Alternatives considered.** (a) `org` only. Rejected: it drops the few tenants we can prove from certs at no
  cost. (b) Tenant identity first (cert or hostname over org). Rejected: cert O is 98% null and polluted by
  defaults, and domain precision is unmeasured. Ranking it above a clean registry org lowers precision.
  (c) Treat domains as equal to cert O now. Rejected until the 50-row precision check passes.
- **Consequences.** Recall is low by design. About 10% of rows yield companies, spread over about 4,600 orgs in
  100K rows. 66% of distinct orgs have a single row, so banner counts are a weak size proxy. The largest loss is
  the vulnerable estate on hosting providers (Aliyun 426, Amazon 255, DigitalOcean 97 vulnerable head rows): the
  exposure is real but cannot be attributed to an owner.

### Denylist changes implied (for data-integrator / owner to apply to `context/denylist.txt`)
1. Keep: microsoft*, oracle*, ibm, ibm cloud, softlayer*, zscaler*, palo alto networks*, imperva*, incapsula*,
   fastly*, shopify*, squarespace*, wix*, vercel*, bitly*. No removals.
2. Change the matching mode from exact lowercase to normalised name plus prefix families, so that spellings like
   `palo alto networks, inc.` with a trailing period, `fastly`, `microsoft azure`, or any further
   `amazon data services <region>` are caught. The families are google, amazon/aws, microsoft, oracle, ibm/softlayer,
   aliyun/alibaba, tencent, huawei cloud, incapsula/imperva, cloudflare, akamai, fastly, zscaler, palo alto networks,
   ovh, scaleway, hetzner, linode, digitalocean, vultr, fly.io, shopify, squarespace, wix, vercel, bitly.
3. Add a rule on top of the list: a non-null `cloud.provider`, or a `cloud`/`cdn` tag, marks the row as infrastructure
   whatever the org says. This covers the long tail that exact names miss.
4. Fix malformed entries before prefix matching is turned on. `ace` would prefix-match any org starting with "ace"
   and must stay exact-only. `139.162.0.0/16`, `*se5-ptk*` and `*se3-ptk*` are not org names; move them to a
   separate CIDR/pattern rule or drop them.
5. Add a cert-subject default-value list (acme co, default company ltd, internet widgits pty ltd, plesk) for D4 rule 3.

### Consequences for the next stages
- **Before `1_clean`:** build the seek-spread sample (D3) and re-profile it. That is data-integrator work, with
  approval for the target path.
- **`1_clean`:** keep every row except exact duplicates. Dedupe RAW-004 on (host_ip, port, transport), keeping the
  latest timestamp. Set `host_ip = coalesce(ip_str, ipv6)` and parse cert dates with sentinels nulled (RAW-007).
  Add the flags `is_infrastructure`, `infra_reason`, `is_noise` and `identity_source`. Do **not** drop
  infrastructure rows in stage 1, so that stage 2 can report shares that sum to 100%.
- **`2_companies`:** apply the D4 precedence and the unresolved report. Contract checks: companies <= hosts, no
  denylist family in company names, shares sum to 100%, and a resolved share between 5% and 20%.
- **Scoring:** no recency signal. Port signals are calibrated only on the spread sample.

### Known weaknesses of these decisions
- The probe covered 9,239 rows from 21 contiguous windows. It is not a random sample, and rows within a window are
  correlated. Per-window kept share ranged from 3.6% to 20.2%.
- `context/business.md` and `context/icp.md` are empty on this branch. The D1 and D2 buyer reasoning relies on the
  task brief ("cybersecurity software company"), not on a written ICP.
- The domain-based tenant share (up to 14%) is an upper bound with an unknown precision. If it is mostly real,
  D4 under-resolves by about that much.
