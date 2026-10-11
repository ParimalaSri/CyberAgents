# Profiling checklist

Work through this after running `scripts/profile_table.py`. Record findings in
`context/schema.md` and CLAUDE.md section 11.

## Per column
- Null rate. Above 50% means the column is probably unusable as a signal.
- Distinct count vs row count. Distinct ~ rows means an identifier; distinct <= 50 means categorical.
- Min/max sanity: impossible dates (future or 1970), negative counts, scores outside range.
- Mixed formats in one column (dates as text, numbers with units, "N/A" strings).
- Casing and whitespace variants of the same value ("Acme Inc", "ACME INC.", "acme").

## Entity columns (decide how rows become companies)
- Which column(s) could identify a company: organisation name, domain, hostname, ASN, IP owner.
- What share of rows has a usable organisation value? This is the ceiling for company grouping.
- Most frequent organisation values. Anything that is a cloud provider, CDN, ISP, hosting company
  or registrar is NOT a customer. List these as denylist candidates in CLAUDE.md section 11.

## Fit candidates (does this company look like our buyer)
Industry, size proxies (number of hosts, address space), geography, technology stack,
public-facing footprint.

## Urgency / risk candidates (do they need help now)
Exposed services (remote access, databases, admin panels), outdated software versions,
known vulnerabilities, expired or weak certificates, missing security headers, recent change
or first-seen dates. Note which columns could express "recent" so urgency can be time-aware.

## Data quality issues to log
Anything surprising goes into `docs/ISSUES.md` with symptom and suspected root cause, even if
unresolved. Duplicated rows, skewed distributions and unparseable values all count.

## Sampling
Profile a 100K-row sample first (`--sample 100000`). Re-profile the full file only after the
sample findings are written down, and compare the two.
