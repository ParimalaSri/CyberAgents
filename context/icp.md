# Ideal customer profile (DRAFT for the owner to edit)

Status: **draft.** `[OWNER]` marks blanks only you can fill; `[ASSUMPTION]` marks my reading of the brief. The signal
lists reflect what the data can show (see `docs/ARCHITECTURE.md` section 3 and `outputs/profile_sample_100k.md`).

## Who is a good account (to be confirmed)
A **real organisation** (not a cloud, CDN, hosting or ISP provider) that:
1. We can name with evidence (owner name of the address block, or certificate organisation), and
2. Has **visible exposure** (known-exploited or high-severity vulnerabilities, expired certificates, end-of-life software, legacy TLS, risky open services), and
3. Sits in a segment and territory we sell to.

## Segments, size and geography
- `[OWNER]` Target industries (in / out). The data has no industry field, so this needs a seed list or an enrichment step.
- `[OWNER]` Target size band. The data has no headcount; host count per company is a weak proxy (66% of organisations appear once in the sample).
- `[OWNER]` Countries in territory. IP country is where the host sits, not where the company is headquartered.

## Bands (what each means to a rep)
| band | meaning | how it is decided |
|---|---|---|
| `contact` | work this account now | rules: strong fit and strong urgency (thresholds calibrated on the real score distribution) |
| `review` | borderline, a model gives a second opinion | rules: scores between the two thresholds; the only band the LLM judges |
| `skip` | not worth a call today | rules: low score |
| `exclude` | never contact | rules: infrastructure providers, attacker or honeypot infrastructure, named accounts you exclude |

## Hard exclusions
- Cloud, CDN, ISP, hosting and website-builder organisations (denylist, `context/denylist.txt`).
- Honeypots, command-and-control and similar attacker infrastructure.
- Security vendors (decision D2, proposed): excluded as infrastructure.
- `[OWNER]` Named accounts to always exclude or always include.

## Signals we expect to matter (proposed, you approve the list)
Fit: territory, a named owner, footprint size, sensitive stack (databases, industrial, medical, IoT).
Urgency: known-exploited vulnerability, severity band, expired or expiring certificate, end-of-life software, legacy TLS, risky service exposed, and exposed-and-outdated combinations.
Not used: scan timestamp (the whole file covers about one hour), EPSS (saturated), CVE count (inflated by banner matching), ASN/ISP (identify the provider, not the customer).

## What a good account reads like
`[OWNER]` Write 3 to 5 examples in the form: *company type, country, what we see, why it is a good account*.
Example format only (not real data): "Mid-size regional bank, US; 4 hosts expose RDP and one runs an end-of-life server; certificate expired 12 days ago."

## Questions for the owner
1. Which industries and size bands do we sell to, and where?
2. How many accounts can a rep work per week?
3. Are there named accounts to always include or exclude?
4. Do you want to add an enrichment source for industry and size, or accept that segment fit comes only from this file?
