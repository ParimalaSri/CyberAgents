# Business context (DRAFT for the owner to edit)

Status: **draft.** Lines marked `[OWNER]` are blanks only you can fill. Lines marked `[ASSUMPTION]` are my
reading of the brief and should be corrected. Nothing here comes from a real company.

## Who we are selling for
- A **cybersecurity software company** (from the brief). The brief does not name the product.
- `[OWNER]` Product category (for example attack-surface management, vulnerability management, WAF, endpoint, managed detection).
- `[OWNER]` Deployment and price band (self-serve, mid-market, enterprise).

## What the sales team needs from this tool
Answer three questions about the businesses in the scan data:
1. Which ones need our software **right now**?
2. **Why** (one readable sentence, no column names)?
3. **How do we reach them first** (a short, factual first touch)?

## Who buys
- `[OWNER]` Buyer titles (for example head of security, IT director, CISO) and the team they sit in.
- `[ASSUMPTION]` Outreach goes to a security or IT lead, with an executive variant. The `outreach-draft` skill supports personas `security`, `it`, `exec`.

## What the data can and cannot say about a buyer
- The data is an internet scan (open ports, certificates, software versions, known vulnerabilities, owner name of the address block).
- It has **no** headcount, revenue, industry or contact details. Segment and size must come from `icp.md` or a seed list.
- About 87% of the scanned rows belong to cloud, CDN, hosting or ISP organisations and cannot be attributed to a customer.
  Sales should expect a **short, high-confidence list**, not coverage of the market.

## Sales motion and capacity
- `[OWNER]` Accounts a rep can work per week (this sets the size of the `contact` band).
- `[OWNER]` Territories sold into (countries or regions).
- `[ASSUMPTION]` Outreach is a human-sent first email or LinkedIn message; the tool only drafts.

## Outreach tone (applies to every draft)
- Calm, specific, short. Mention one or two observed facts from the account's data. One call to action.
- Soft framing ("we noticed ... publicly visible"), never alarmist.

## Claims we never make
- We never say a breach, attack or compromise **happened**.
- We never use facts that are not in the account's data, and we never pressure ("act now", "before it is too late").
- Banned phrases live in `.claude/skills/outreach-draft/references/banned_phrases.txt` (edit it to personalise).

## Competitors and channel
- `[OWNER]` Competitors to avoid contacting or to treat specially.
- Decision D2 (proposed, see `docs/ARCHITECTURE.md`): security vendors and website builders are treated as infrastructure and excluded, not contacted as accounts.
