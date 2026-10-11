"""Independent recompute of 4_score from D9, D10, D11 and D12 in plain Python (own constants, no import of the stage); compares scores, bands, caps, top_signals and why phrases."""
import argparse
import random
import sys
from fractions import Fraction
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SIGNALS = ROOT / "data" / "gold" / "signals.parquet"
ACCOUNTS = ROOT / "data" / "gold" / "accounts.parquet"
FORBIDDEN_WORDS = ("breach", "compromised", "hacked")
CLAUSE = "Not yet checked that this is an end-user organisation, not a network operator."  # D10 text
OPERATOR_CLAUSE = "Name looks like a network operator."  # D10 cap clause, D11.3 also on operator-shaped review rows
SKIP_CLAUSE = "Below the review cut-off."  # D11.3
SKIP_CLAUSE_SIGNAL = "Ranked below this run's review list; a rank, not a judgement of risk."  # D12.2
EXPOSED_NEW = "on software that is end-of-life or whose version matches a CVSS 7+ vulnerability"  # D12.3
EXPOSED_OLD = "on outdated software"  # D12.3 replaced it
KEV_PHRASE = "running software whose version matches the CISA known-exploited list"  # D11.3
CVSS_PHRASE = "worst version-matched vulnerability scores CVSS"  # D11.3
OLD_PHRASES = ("Exposure is limited.", "with a vulnerability on the CISA", "worst vulnerability scores", "Hosts located in", "known-exploited host", "is vulnerable")  # must not appear after D11
TERRITORY_POINTS = 0  # D11.5


def urgency_of(s):
    """Return the D9.7 provisional urgency: larger of KEV and CVSS points, plus highest exposure, plus summed hygiene, clipped to 100."""
    cvss = {0: 0, 1: 10, 2: 25, 3: 40}[s["max_cvss_band"]]
    vuln = max(50 if s["kev_exposed"] else 0, cvss)
    if s["exposed_and_outdated"]:
        expo = 30
    elif s["risky_non_ssh_exposed"]:
        expo = 15
    elif s["risky_service_exposed"]:
        expo = 5
    else:
        expo = 0
    hyg = (10 if s["eol_stack"] else 0) + (5 if s["cert_expired_or_soon"] else 0) + (5 if s["legacy_tls"] else 0)
    return min(100, vuln + expo + hyg)


def fit_of(s):
    """Return the D9.7 provisional fit with territory points 0 (D11.5): footprint band x 15, sensitive 20, minus 30 for the T1-or-T2 union flag (D10), clipped to 0..100."""
    pts = (TERRITORY_POINTS if s["in_territory"] else 0) + 15 * s["footprint_band"] + (20 if s["sensitive_stack"] else 0) - (30 if (s["operator_shape_t1"] or s["operator_shape_t2"]) else 0)
    return max(0, min(100, pts))


def contact_of(urgency, fit):
    """Return round-half-up of urgency * (0.5 + 0.5 * fit / 100) using exact fractions."""
    x = Fraction(urgency) * (Fraction(1, 2) + Fraction(1, 2) * Fraction(fit, 100))
    return int((x + Fraction(1, 2)) // 1)


def band_of(s, contact, contact_x, review_y, rank, review_n):
    """Return (band_uncapped, cap_reasons, band) per D9.6 item 5, D10 and D11.2 (rank is the 1-based position among non-excluded accounts in the stage order)."""
    if s["noise_host_count"] >= 2 and s["noise_host_share"] >= 0.5:
        return "exclude", None, "exclude"
    unc = "contact" if contact >= contact_x else "review" if contact >= review_y else "skip"
    reasons = []
    if unc == "contact":
        reasons.append("operator_unverified")  # D10: every would-be contact
        if s["identity_confidence"] == "low":
            reasons.append("low_confidence")
        if s["operator_name_shape"]:
            reasons.append("operator_name_shape")
        if s["host_count"] == 1:
            reasons.append("singleton")
    band = "review" if reasons or (rank <= review_n and contact >= review_y) else "skip"
    return unc, (",".join(sorted(reasons)) or None), band


def top_signals_of(s, urgency):
    """Return the expected top_signals string: the two highest-point signals, ties broken vulnerability, exposure, hygiene, fit; None if urgency is 0."""
    if urgency == 0:
        return None
    cvss = {0: 0, 1: 10, 2: 25, 3: 40}[s["max_cvss_band"]]
    cands = []
    if s["kev_exposed"] and 50 >= cvss:
        cands.append((50, 0, 0, "kev_exposed"))
    elif cvss > 0:
        cands.append((cvss, 0, 0, "max_cvss_band"))
    for pts, name in ((30, "exposed_and_outdated"), (15, "risky_non_ssh_exposed"), (5, "risky_service_exposed")):
        if s[name]:
            cands.append((pts, 1, 0, name))
            break
    for i, (pts, name) in enumerate(((10, "eol_stack"), (5, "cert_expired_or_soon"), (5, "legacy_tls"))):
        if s[name]:
            cands.append((pts, 2, i, name))
    for i, (pts, name) in enumerate(((15 * s["footprint_band"], "footprint_band"), (TERRITORY_POINTS if s["in_territory"] else 0, "in_territory"),
                                     (20 if s["sensitive_stack"] else 0, "sensitive_stack"))):
        if pts > 0:
            cands.append((pts, 3, i, name))
    cands.sort(key=lambda c: (-c[0], c[1], c[2]))
    return [c[3] for c in cands[:2]]


def load(con, path):
    """Return a list of row dicts from a parquet file."""
    cur = con.execute(f"SELECT * FROM read_parquet('{Path(path).as_posix()}')")
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def check_account(sig, acc, contact_x, review_y, rank, review_n):
    """Return a list of disagreement strings for one company between the independent recompute and the stage output."""
    problems = []
    u, f = urgency_of(sig), fit_of(sig)
    c = contact_of(u, f)
    unc, reasons, band = band_of(sig, c, contact_x, review_y, rank, review_n)
    for label, mine, theirs in (("urgency", u, acc["urgency_score"]), ("fit", f, acc["fit_score"]), ("contact", c, acc["contact_score"]),
                                ("band_uncapped", unc, acc["band_uncapped"]), ("cap_reasons", reasons, acc["cap_reasons"]), ("band", band, acc["band"])):
        if mine != theirs:
            problems.append(f"{label}: independent {mine!r} vs stage {theirs!r}")
    if band != "exclude":
        expected = top_signals_of(sig, u)
        got = acc["top_signals"].split(",") if acc["top_signals"] else None
        # the stage may keep one signal when two do not fit in 40 words; it must then be a prefix of the independent list
        if expected is None and got is not None or expected is not None and (got is None or got != expected[:len(got)]):
            problems.append(f"top_signals: independent {expected!r} vs stage {got!r}")
    why = acc["why"] or ""
    if (unc == "contact") != why.endswith(CLAUSE) or (unc != "contact" and CLAUSE in why):
        problems.append(f"D10 clause wrong for band_uncapped {unc}: {why!r}")
    kept = (acc["top_signals"] or "").split(",")
    if band == "skip" and u > 0:
        want = SKIP_CLAUSE_SIGNAL if ("kev_exposed" in kept or "max_cvss_band" in kept) else SKIP_CLAUSE  # D12.2: judged on the signals kept
        other = SKIP_CLAUSE if want == SKIP_CLAUSE_SIGNAL else SKIP_CLAUSE_SIGNAL
        if not why.endswith(want) or other in why:
            problems.append(f"skip why should end with {want!r}: {why!r}")
    if band != "skip" and (SKIP_CLAUSE in why or SKIP_CLAUSE_SIGNAL in why):
        problems.append(f"skip clause on a {band} row: {why!r}")
    if EXPOSED_OLD in why or ("exposed_and_outdated" in kept) != (EXPOSED_NEW in why):
        problems.append(f"D12.3 exposure phrase wrong for top_signals {kept}: {why!r}")
    if band == "review" and sig["operator_name_shape"] and OPERATOR_CLAUSE not in why:
        problems.append(f"operator-shaped review row without the operator clause: {why!r}")
    if band != "review" and OPERATOR_CLAUSE in why:
        problems.append(f"operator clause on a {band} row: {why!r}")
    if sig["kev_exposed"] and "kev_exposed" in (acc["top_signals"] or "") and KEV_PHRASE.lower() not in why.lower():
        problems.append(f"KEV top signal without the D11.3 phrase: {why!r}")
    if "max_cvss_band" in (acc["top_signals"] or "") and CVSS_PHRASE.lower() not in why.lower():
        problems.append(f"CVSS top signal without the D11.3 phrase: {why!r}")
    if any(old in why for old in OLD_PHRASES):
        problems.append(f"pre-D11 phrase in why: {why!r}")
    words = len(why.split())
    if not why.strip() or words > 40 or "=" in why or "_" in why or any(w in why.lower() for w in FORBIDDEN_WORDS):
        problems.append(f"why fails shape rules ({words} words): {why!r}")
    if acc["final_band"] != acc["band"] or acc["decision"] is not None or acc["prompt_version"] is not None:
        problems.append("final_band/decision/prompt_version not as at stage 4")
    if not (0 <= f <= 100 and 0 <= u <= 100 and 0 <= c <= 100 and u / 2 - 0.5 <= c <= u):
        problems.append(f"invariant broken: fit {f}, urgency {u}, contact {c}")
    if acc["band"] == "contact":
        problems.append("account in contact (D10: only adjudication may promote)")
    return problems


def order_key(s, urgency, contact, cid):
    """Return the D12.1 sort key: contact desc, urgency desc, operator flag false first, KEV hosts desc (null as 0), host_count desc, id asc."""
    return (-contact, -urgency, bool(s["operator_name_shape"]), -(s["kev_host_count"] or 0), -s["host_count"], cid)


def rank_accounts(sigs):
    """Return {company_id: 1-based rank} over non-excluded companies in the D12.1 order, recomputed from the signals."""
    keyed = []
    for cid, s in sigs.items():
        if s["noise_host_count"] >= 2 and s["noise_host_share"] >= 0.5:
            continue
        u = urgency_of(s)
        keyed.append(order_key(s, u, contact_of(u, fit_of(s)), cid))
    return {k[-1]: i for i, k in enumerate(sorted(keyed), 1)}


def main():
    """Verify 200 random companies plus the top 25 and every exclude row (or all with --all); print disagreements and return 1 if any."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", default=str(SIGNALS))
    parser.add_argument("--accounts", default=str(ACCOUNTS))
    parser.add_argument("--contact", type=int, default=40)
    parser.add_argument("--review", type=int, default=20)
    parser.add_argument("--review-n", type=int, default=200)
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--all", action="store_true", help="check every company")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # company names are not ASCII; the Windows console default (cp1252) crashed on printing a disagreement
    con = duckdb.connect()
    sigs = {r["company_id"]: r for r in load(con, args.signals)}
    accs = load(con, args.accounts)
    assert len(accs) == len(sigs) and {a["account_id"] for a in accs} == set(sigs), "account ids differ from signal company ids"
    picked = set(random.Random(args.seed).sample(sorted(sigs), min(args.sample, len(sigs))))
    picked |= {a["account_id"] for a in accs[:25]} | {a["account_id"] for a in accs if a["band"] == "exclude"}
    if args.all:
        picked = set(sigs)
    ranks = rank_accounts(sigs)
    bad = 0
    for acc in accs:
        if acc["account_id"] in picked:
            for p in check_account(sigs[acc["account_id"]], acc, args.contact, args.review, ranks.get(acc["account_id"], 10**9), args.review_n):
                bad += 1
                print(f"DISAGREE {acc['account_id']} {acc['company_name']}: {p}")
    keys = [order_key(sigs[a["account_id"]], a["urgency_score"], a["contact_score"], a["account_id"]) for a in accs]
    order_ok = all(keys[i] < keys[i + 1] for i in range(len(keys) - 1))  # strictly increasing: the file is in the D12.1 total order
    print(f"checked {len(picked)} companies ({'all' if args.all else f'{args.sample} random + top 25 + exclude rows'}); disagreements: {bad}; sort order ok: {order_ok}")
    return 0 if bad == 0 and order_ok else 1


if __name__ == "__main__":
    sys.exit(main())
