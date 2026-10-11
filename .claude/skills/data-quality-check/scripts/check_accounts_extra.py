"""Independent accounts-layer checks: recompute fit, urgency, contact, bands (D11.2 top-N), caps and top_signals from signals (D9.6 to D9.9, D10, D11), why phrases, sort order."""
import argparse
import re
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[4]
ACCOUNTS_PATH = REPO_ROOT / "data" / "gold" / "accounts.parquet"
SIGNALS_PATH = REPO_ROOT / "data" / "gold" / "signals.parquet"
COMPANIES_PATH = REPO_ROOT / "data" / "silver" / "companies.parquet"

# PROVISIONAL constants (D9.7, D10, D11): the starting point only, not calibrated, not owner approved. Written here from the decision text,
# not copied from pipeline/4_score.py. Change them together with context/contracts/accounts.yml when scoring-calibration decides.
# D11.5: territory carries 0 points until the owner supplies the list (35 when it exists).
KEV_POINTS = 50
CVSS_POINTS = {3: 40, 2: 25, 1: 10}
EXPOSURE_POINTS = (("exposed_and_outdated", 30), ("risky_non_ssh_exposed", 15), ("risky_service_exposed", 5))  # highest applicable
HYGIENE_POINTS = (("eol_stack", 10), ("cert_expired_or_soon", 5), ("legacy_tls", 5))  # summed
TERRITORY_POINTS, FOOTPRINT_POINTS_PER_BAND, SENSITIVE_POINTS, OPERATOR_PENALTY = 0, 15, 20, 30
FLOOR = Fraction(1, 2)  # contact form (b), PROVISIONAL
CONTACT_MIN, REVIEW_MIN = 40, 20  # X, and Y which is the FLOOR of the top-N review band (D11.2, D11.7), PROVISIONAL
REVIEW_N = 200  # D11.2 total review accounts, PROVISIONAL (N = ceil(C / r) with placeholder C = 50, r = 0.25; scales with the owner capacity)
NOISE_MIN_HOSTS, NOISE_MIN_SHARE = 2, 0.5  # D9.3, decided
WHY_MAX_WORDS = 40  # D9.6 item 7 and D9.8
CLAUSE = "Not yet checked that this is an end-user organisation, not a network operator."  # D10
SKIP_CLAUSE = "Below the review cut-off."  # D11.3 replaces "Exposure is limited."
OPERATOR_CLAUSE = "Name looks like a network operator."  # D9.6 item 7, D11.3 (any review row with the operator name shape)
OLD_WORDING = ("Exposure is limited", "with a vulnerability on the CISA known-exploited list", "worst vulnerability scores", "located in", "based in", "is vulnerable",
               "known-exploited host", "has been exploited")  # pre-D11 phrases and the words D11.3 and D11.5 forbid
CAP_ORDER = ("low_confidence", "operator_name_shape", "operator_unverified", "singleton")  # alphabetical, the contract rule (DQ-012)
BANDS = ("contact", "review", "skip", "exclude")
FORBIDDEN_WORDS = ("breach", "compromised", "hacked")  # D9.9 rule 3
ALARM_WORDS = ("safe", "secure", "attack", "infect", "leak", "stolen", "ransom", "urgent", "critical", "immediately")  # report only
CATEGORY_RANK = {"vulnerability": 0, "exposure": 1, "hygiene": 2, "fit": 3}  # D9.6 item 7 tie preference
ACCOUNT_COLUMNS = ("account_id", "company_name", "country_code", "host_count", "identity_source", "identity_confidence", "fit_score", "urgency_score",
                   "contact_score", "top_signals", "band_uncapped", "cap_reasons", "band", "why", "decision", "prompt_version", "final_band")
SIGNAL_COLUMNS = ("company_id", "company_name", "country_code", "host_count", "distinct_host_ips", "identity_source", "identity_confidence", "noise_host_count",
                  "noise_host_share", "is_singleton", "in_territory", "footprint_band", "sensitive_stack", "operator_shape_t1", "operator_shape_t2",
                  "kev_exposed", "kev_host_count", "max_cvss", "max_cvss_band", "cert_expired_or_soon", "cert_issue_host_count", "eol_stack", "eol_host_count",
                  "legacy_tls", "legacy_tls_host_count", "risky_service_exposed", "risky_non_ssh_exposed", "risky_service_host_count", "risky_ports",
                  "exposed_and_outdated")
# The numbers the stage author reported after D11 (accounts_stage_2026-10-11.md and the hand-off), compared with my own recomputation.
AUTHOR = {"rows": 5790, "contact": 0, "review": 200, "skip": 5589, "exclude": 1, "would_be_contacts": 51, "urgency_above_0": 1324, "fit_above_0": 1190,
          "max_fit": 65, "cut_score": 30, "tie_size": 142, "tie_kept": 7, "tie_to_skip": 135, "accounts_above_cut": 193, "top_n_only": 149, "review_operator_shaped": 42,
          "review_operator_via_cap": 5, "review_operator_via_top_n": 37, "skip_urgency_above_0": 1123, "skip_below_floor": 659, "skip_below_floor_non_ssh": 42,
          "skip_below_floor_cvss7": 32, "skip_below_floor_overlap": 0, "skip_below_floor_union": 74, "skip_beyond_cut": 464, "longest_why_words": 37,
          "union_fit_lost": 66, "union_contact_changed": 29,
          "cap_sets": {"operator_unverified": 46, "operator_name_shape,operator_unverified": 4, "operator_name_shape,operator_unverified,singleton": 1}}
# Phrase table, written from D9.6 item 7 (the wording the stage uses is matched here by pattern; the signal each phrase names must be true).
PHRASES = (
    ("kev_exposed", re.compile(r"(\d+) hosts? running software whose version matches the CISA known-exploited list", re.I)),  # D11.3, RAW-006
    ("max_cvss_band", re.compile(r"worst version-matched vulnerability scores CVSS (\d+(?:\.\d+)?)", re.I)),  # D11.3, RAW-006
    ("exposed_and_outdated", re.compile(r"an exposed admin or database service \(([^)]*)\) on outdated software", re.I)),
    ("risky_non_ssh_exposed", re.compile(r"remote-admin or database services exposed \(([^)]*)\)", re.I)),
    ("risky_service_exposed", re.compile(r"SSH \(port 22\) open to the internet", re.I)),
    ("eol_stack", re.compile(r"(\d+) hosts? on end-of-life software", re.I)),
    ("cert_expired_or_soon", re.compile(r"(\d+) hosts? with expired or soon-expiring certificates", re.I)),
    ("legacy_tls", re.compile(r"(\d+) hosts? still offering old TLS versions", re.I)),
    ("footprint_band", re.compile(r"(\d+) IPs in the footprint")),
    ("sensitive_stack", re.compile(r"database, medical or IoT systems in the stack", re.I)),
)
# name -> truth test of one phrase against its signals row: (signals row, captured text, risky ports of the company) -> bool
PHRASE_TRUTH = {
    "kev_exposed": lambda sig, g, ports: bool(sig["kev_exposed"]) and int(g) == sig["kev_host_count"],
    "max_cvss_band": lambda sig, g, ports: sig["max_cvss_band"] >= 1 and sig["max_cvss"] is not None and abs(float(g) - round(sig["max_cvss"], 1)) < 1e-9,
    "exposed_and_outdated": lambda sig, g, ports: bool(sig["exposed_and_outdated"]) and {int(p) for p in re.findall(r"\d+", g)} <= ports,
    "risky_non_ssh_exposed": lambda sig, g, ports: bool(sig["risky_non_ssh_exposed"]) and {int(p) for p in re.findall(r"\d+", g)} <= ports,
    "risky_service_exposed": lambda sig, g, ports: bool(sig["risky_service_exposed"]) and 22 in ports and not sig["risky_non_ssh_exposed"],
    "eol_stack": lambda sig, g, ports: bool(sig["eol_stack"]) and int(g) == sig["eol_host_count"],
    "cert_expired_or_soon": lambda sig, g, ports: bool(sig["cert_expired_or_soon"]) and int(g) == sig["cert_issue_host_count"],
    "legacy_tls": lambda sig, g, ports: bool(sig["legacy_tls"]) and int(g) == sig["legacy_tls_host_count"],
    "footprint_band": lambda sig, g, ports: sig["footprint_band"] >= 1 and int(g) == sig["distinct_host_ips"],
    "sensitive_stack": lambda sig, g, ports: bool(sig["sensitive_stack"]),
}
CAP_CLAUSES = (("operator_name_shape", "Name looks like a network operator."), ("singleton", "Only one host seen."),
               ("low_confidence", "Named only by a TLS certificate."))
NO_SIGNAL = re.compile(r"No exposure signal found in the scan \((\d+) hosts? seen\)\.")
EXCLUDED = re.compile(r"Mostly honeypot or attacker-infrastructure hosts \((\d+) of (\d+)\)\.")


def fetch_dicts(con, sql):
    """Run a query and return its rows as a list of dicts keyed by column name."""
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def load_matcher():
    """Import the shared denylist matcher from scripts/ and return the module."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import denylist_match
    return denylist_match


def round_half_up(value):
    """Return the integer nearest to a Fraction, halves rounded up."""
    return int((value + Fraction(1, 2)) // 1)


def scored_candidates(sig):
    """Return (signal, points, category) for every scored signal that fires: the larger vulnerability item, the top exposure item, hygiene items, fit items."""
    out = []
    kev, cvss = (KEV_POINTS if sig["kev_exposed"] else 0), CVSS_POINTS.get(sig["max_cvss_band"], 0)
    if kev or cvss:
        out.append(("kev_exposed", kev, "vulnerability") if kev >= cvss else ("max_cvss_band", cvss, "vulnerability"))
    for name, points in EXPOSURE_POINTS:
        if sig[name]:
            out.append((name, points, "exposure"))
            break
    out += [(name, points, "hygiene") for name, points in HYGIENE_POINTS if sig[name]]
    if sig["in_territory"] and TERRITORY_POINTS:
        out.append(("in_territory", TERRITORY_POINTS, "fit"))  # D11.5: a 0-point territory is neither scored nor a top signal
    if sig["footprint_band"]:
        out.append(("footprint_band", FOOTPRINT_POINTS_PER_BAND * sig["footprint_band"], "fit"))
    if sig["sensitive_stack"]:
        out.append(("sensitive_stack", SENSITIVE_POINTS, "fit"))
    return out


def operator_penalised(sig, union=True):
    """Return True when the fit penalty applies: T1 or T2 (the D10 union), or T1 only when union is False (the pre-D10 form)."""
    return bool(sig["operator_shape_t1"] or (union and sig["operator_shape_t2"]))


def reference_account(sig, union=True):
    """Recompute one account from its signals row: scores, bands, cap reasons and top_signals, from D9.6, D9.7 and D10 only."""
    urgency = min(100, sum(p for n, p, c in scored_candidates(sig) if c != "fit"))
    fit = max(0, min(100, sum(p for n, p, c in scored_candidates(sig) if c == "fit") - (OPERATOR_PENALTY if operator_penalised(sig, union) else 0)))
    contact = round_half_up(urgency * (FLOOR + (1 - FLOOR) * Fraction(fit, 100)))
    excluded = sig["noise_host_count"] >= NOISE_MIN_HOSTS and sig["noise_host_share"] >= NOISE_MIN_SHARE
    uncapped = "exclude" if excluded else "contact" if contact >= CONTACT_MIN else "review" if contact >= REVIEW_MIN else "skip"
    reasons = []
    if uncapped == "contact":
        reasons = [r for r, hit in (("low_confidence", sig["identity_confidence"] == "low"), ("operator_name_shape", operator_penalised(sig, True)),
                                    ("operator_unverified", True), ("singleton", sig["host_count"] == 1)) if hit]
    ranked = sorted(scored_candidates(sig), key=lambda c: (-c[1], CATEGORY_RANK[c[2]], [n for n, _, _ in scored_candidates(sig)].index(c[0])))
    top = None if (urgency == 0 or excluded) else [n for n, _, _ in ranked[:2]]
    return {"fit_score": fit, "urgency_score": urgency, "contact_score": contact, "band_uncapped": uncapped, "cap_reasons": ",".join(reasons) or None,
            "band": "review" if reasons else uncapped, "top_signals": top}  # band here is the cap-level band; reference_all applies the D11.2 top-N rule


def rank_order(ref, sig):
    """Return the D9.6 item 8 total order key of one account: contact_score desc, urgency_score desc, host_count desc, account_id asc."""
    return (-ref["contact_score"], -ref["urgency_score"], -sig["host_count"], sig["company_id"])


def review_selection(refs, sigs, review_n=REVIEW_N, floor=REVIEW_MIN):
    """Return (review ids, cut stats) by the D11.2 rule: every would-be contact plus the best non-excluded others by the total order until review_n, floor contact_score >= floor."""
    would = {cid for cid, r in refs.items() if r["band_uncapped"] == "contact"}
    ranked = sorted((cid for cid, r in refs.items() if r["band_uncapped"] != "exclude"), key=lambda cid: rank_order(refs[cid], sigs[cid]))
    eligible = [cid for cid in ranked if cid not in would and refs[cid]["contact_score"] >= floor]
    chosen = eligible[:max(0, review_n - len(would))]
    cut = refs[chosen[-1]]["contact_score"] if chosen else None
    tied = [cid for cid in ranked if refs[cid]["contact_score"] == cut] if cut is not None else []
    kept = [cid for cid in chosen if refs[cid]["contact_score"] == cut]
    stats = {"would_be_contacts": len(would), "top_n_only": len(chosen), "cut_score": cut, "tie_size": len(tied), "tie_kept": len(kept),
             "tie_to_skip": len(tied) - len(kept), "accounts_above_cut": sum(1 for cid in ranked if cut is not None and refs[cid]["contact_score"] > cut),
             "kept_tied_ids": sorted(kept), "beyond_cut": len(eligible) - len(chosen)}
    return would | set(chosen), stats


def reference_all(signal_rows, review_n=REVIEW_N):
    """Recompute every account (scores, caps, top_signals and the final band after the D11.2 top-N rule); return (refs by id, cut stats)."""
    sigs = {s["company_id"]: s for s in signal_rows}
    refs = {cid: reference_account(s) for cid, s in sigs.items()}
    review, stats = review_selection(refs, sigs, review_n)
    for cid, ref in refs.items():
        ref["band"] = "exclude" if ref["band_uncapped"] == "exclude" else "review" if cid in review else "skip"
    return refs, stats


def compare_reference(account_rows, signal_rows, review_n=REVIEW_N):
    """Compare every account with the recomputation; return (missing ids, extra ids, per-column disagreement counts, examples, fallback ids)."""
    sigs = {s["company_id"]: s for s in signal_rows}
    refs, _stats = reference_all(signal_rows, review_n)
    seen = {a["account_id"]: a for a in account_rows}
    diffs, examples, fallback = Counter(), {}, []
    for aid, acc in seen.items():
        if aid not in sigs:
            continue
        ref = refs[aid]
        for column in ("fit_score", "urgency_score", "contact_score", "band_uncapped", "cap_reasons", "band"):
            if acc[column] != ref[column]:
                diffs[column] += 1
                examples.setdefault(column, (acc["company_name"], acc[column], ref[column]))
        actual = acc["top_signals"].split(",") if acc["top_signals"] else None
        if actual != ref["top_signals"]:
            if actual and ref["top_signals"] and actual == ref["top_signals"][:1] and acc["band_uncapped"] == "contact":
                fallback.append(aid)  # the stage keeps the D10 clause and drops the second signal when the why would pass 40 words (author note)
            else:
                diffs["top_signals"] += 1
                examples.setdefault("top_signals", (acc["company_name"], acc["top_signals"], ref["top_signals"]))
    return sorted(set(sigs) - set(seen)), sorted(set(seen) - set(sigs)), diffs, examples, fallback


def check_ids_and_rows(account_rows, signal_rows, company_rows, results):
    """Check rows equal signals rows equal companies rows, account_id unique and non-null, id sets equal both ways."""
    ids = [a["account_id"] for a in account_rows]
    dup = len(ids) - len(set(ids))
    s_ids, c_ids = {s["company_id"] for s in signal_rows}, {c["company_id"] for c in company_rows}
    ok = (len(account_rows) == len(signal_rows) == len(company_rows) and dup == 0 and None not in ids and set(ids) == s_ids == c_ids)
    results.append(("accounts rows == signals rows == companies rows, account_id unique and non-null, id sets equal both ways", ok,
                    f"accounts {len(account_rows):,}, signals {len(signal_rows):,}, companies {len(company_rows):,}, duplicate ids {dup}, "
                    f"only in accounts {len(set(ids) - s_ids)}, only in signals {len(s_ids - set(ids))}"))


def check_recompute(account_rows, signal_rows, results, review_n=REVIEW_N):
    """Check fit, urgency, contact, band_uncapped, cap_reasons, band (D11.2 top-N) and top_signals equal the independent recomputation on every account."""
    missing, extra, diffs, examples, fallback = compare_reference(account_rows, signal_rows, review_n)
    total = sum(diffs.values()) + len(missing) + len(extra)
    results.append(("independent recompute of fit, urgency, contact, band_uncapped, cap_reasons, band, top_signals from signals: 0 disagreements", total == 0,
                    f"{len(account_rows):,} accounts; missing {len(missing)}, extra {len(extra)}; column disagreements {dict(diffs) or 'none'}; examples {list(examples.items())[:3]}; "
                    f"one-signal fallback on {len(fallback)} would-be contacts (tolerated: second signal dropped for the 40-word limit)"))


def words(text):
    """Return the whitespace-separated words of a text."""
    return text.split()


def parse_why(text, sig, account):
    """Parse a why into (signal names in order, problems): every phrase must be known, true in signals and carry the right numbers."""
    problems, found, rest = [], [], text
    ports_of = set(sig["risky_ports"] or [])
    for name, pattern in PHRASES:
        for m in pattern.finditer(text):
            found.append((m.start(), name))
            rest = rest.replace(m.group(0), "", 1)
            g = m.group(1) if m.groups() else None
            ok = PHRASE_TRUTH[name](sig, g, ports_of)
            if not ok:
                problems.append(f"phrase for {name} is false or wrongly numbered: {m.group(0)!r}")
            if name in ("kev_exposed", "eol_stack", "cert_expired_or_soon", "legacy_tls") and g is not None and (g == "1") != bool(re.match(r"1 host\b", m.group(0))):
                problems.append(f"singular/plural wrong: {m.group(0)!r}")
    return [n for _, n in sorted(found)], problems, rest


def check_why_row(account, sig):
    """Return the list of problems with one why: words, forbidden words, D10 clause, skip clause, operator clause, phrases true in signals, nothing unrecognised."""
    why, problems = account["why"], []
    if why is None or not why.strip():
        return ["why is null or empty"]
    if why != why.strip():
        problems.append("why is not trimmed")
    if len(words(why)) > WHY_MAX_WORDS:
        problems.append(f"why has {len(words(why))} words (limit {WHY_MAX_WORDS})")
    if "=" in why or "_" in why:
        problems.append("why contains '=' or '_'")
    low = why.lower()
    problems += [f"why contains {w!r}" for w in FORBIDDEN_WORDS if w in low]
    problems += [f"why uses the old or forbidden wording {w!r}" for w in OLD_WORDING if w.lower() in low]
    if why[0] != why[0].upper():
        problems.append("why does not start with a capital letter")
    clause_expected = account["band_uncapped"] == "contact"
    if why.endswith(CLAUSE) != clause_expected or (CLAUSE in why and not why.endswith(CLAUSE)):
        problems.append("D10 clause missing from a would-be contact, present elsewhere or not at the end")
    body = why[:-len(CLAUSE)].strip() if why.endswith(CLAUSE) else why
    if account["band"] == "exclude":
        m = EXCLUDED.fullmatch(body)
        if not m or int(m.group(1)) != sig["noise_host_count"] or int(m.group(2)) != sig["noise_host_count"] + sig["host_count"]:
            problems.append("excluded why is not 'Mostly honeypot ... (K of N)' with K = noise_host_count and N = noise rows + hosts")
        return problems
    m = NO_SIGNAL.fullmatch(body)
    if account["urgency_score"] == 0:
        if not m or int(m.group(1)) != sig["host_count"] or (m.group(1) == "1") != ("1 host seen" in body):
            problems.append("urgency 0 why is not 'No exposure signal found in the scan (N host(s) seen).' with N = host_count")
        return problems
    if m:
        problems.append("no-signal why on an account with urgency above 0")
    named, bad, rest = parse_why(body, sig, account)
    problems += bad
    expected = account["top_signals"].split(",") if account["top_signals"] else []
    if named != expected:
        problems.append(f"signals named in why {named} differ from top_signals {expected}")
    found = [reason for reason, text in CAP_CLAUSES if text in body]
    operator_expected = account["band"] == "review" and bool(sig["operator_shape_t1"] or sig["operator_shape_t2"])
    if operator_expected != ("operator_name_shape" in found):
        problems.append(f"operator clause {'missing from an operator-shaped review row' if operator_expected else 'present on a row that is not an operator-shaped review row'}")
    reasons = (account["cap_reasons"] or "").split(",")
    listed = [r for r in reasons if r in ("low_confidence", "operator_name_shape", "singleton")]
    if len(found) > 1 or any(c not in reasons for c in found if c != "operator_name_shape") or (listed and not found):
        problems.append(f"cap clause {found} does not match cap_reasons {account['cap_reasons']!r} (at most one clause, exactly one when a cap flag is listed)")
    for reason, text in CAP_CLAUSES:
        if text in body and not body.endswith(text):
            problems.append(f"clause {text!r} is not the last sentence before the D10 clause")
        rest = rest.replace(text, "")
    if SKIP_CLAUSE in rest:
        rest = rest.replace(SKIP_CLAUSE, "")
        if account["band"] != "skip":
            problems.append(f"{SKIP_CLAUSE!r} on an account that is not skip")
        elif not body.endswith(SKIP_CLAUSE):
            problems.append(f"{SKIP_CLAUSE!r} is not the last sentence of a skip why")
    elif account["band"] == "skip":
        problems.append(f"skip account with urgency above 0 lacks {SKIP_CLAUSE!r} (D11.3)")
    if re.sub(r"[;.\s]", "", rest):
        problems.append(f"unrecognised text in why: {rest.strip()!r}")
    return problems


def check_why(account_rows, signal_rows, results):
    """Run the why checks on every account (a superset of the top 25 and a random 200); report counts per problem type."""
    sigs = {s["company_id"]: s for s in signal_rows}
    kinds, examples = Counter(), {}
    for acc in account_rows:
        if acc["account_id"] not in sigs:
            continue
        for problem in check_why_row(acc, sigs[acc["account_id"]]):
            key = re.sub(r"['\"(\d].*", "", problem)[:60]
            kinds[key] += 1
            examples.setdefault(key, (acc["company_name"], problem))
    results.append(("why on every account: non-empty, at most 40 words, no '=' or '_', no breach words, D10 clause exactly on would-be contacts, every phrase true and "
                    "correctly numbered in signals, named signals equal top_signals, cap clause matches cap_reasons, nothing unrecognised", not kinds,
                    f"{len(account_rows):,} accounts checked; problems {dict(kinds) or 'none'}; examples {list(examples.values())[:3]}"))
    flagged = sorted({(a["company_name"], w) for a in account_rows if a["why"] for w in ALARM_WORDS if w in a["why"].lower()})
    return flagged


def check_cut(account_rows, signal_rows, results, review_n=REVIEW_N):
    """Check the review cut taken from the accounts file (cut score, tie size, tied accounts kept, band size, order of skip versus review) equals my recomputation (D11.2)."""
    sigs = {s["company_id"]: s for s in signal_rows}
    refs, mine = reference_all(signal_rows, review_n)
    live = [a for a in account_rows if a["account_id"] in sigs and a["band"] != "exclude"]
    top_n = [a for a in live if a["band"] == "review" and a["band_uncapped"] != "contact"]
    cut = min((a["contact_score"] for a in top_n), default=None)
    tied = [a for a in live if cut is not None and a["contact_score"] == cut]
    kept = sorted(a["account_id"] for a in tied if a["band"] == "review")
    review = sum(1 for a in live if a["band"] == "review")
    would = sum(1 for a in live if a["band_uncapped"] == "contact")
    stage = {"cut_score": cut, "tie_size": len(tied), "tie_kept": len(kept), "tie_to_skip": len(tied) - len(kept), "kept_tied_ids": kept, "top_n_only": len(top_n)}
    differs = {k: (stage[k], mine[k]) for k in stage if stage[k] != mine[k]}
    weakest = max((rank_order(refs[a["account_id"]], sigs[a["account_id"]]) for a in top_n), default=None)
    out_of_order = [a["company_name"] for a in live if a["band"] == "skip" and a["band_uncapped"] == "review" and weakest is not None
                    and rank_order(refs[a["account_id"]], sigs[a["account_id"]]) < weakest]
    expected_size = would + min(max(0, review_n - would), mine["top_n_only"] + mine["beyond_cut"])
    ok = not differs and not out_of_order and review == expected_size
    results.append((f"review cut (D11.2, N = {review_n}, floor {REVIEW_MIN}): band size, cut score, tie size, tied accounts kept and order of skip versus review equal my recomputation", ok,
                    f"review {review} (expected {expected_size}), would-be {would}, top-N only {len(top_n)}, cut score {cut}, tie {len(tied)}, kept {len(kept)}, to skip {len(tied) - len(kept)}; "
                    f"differences from mine {differs or 'none'}; skip accounts ranked above the weakest review account {len(out_of_order)} {out_of_order[:3]}"))


def check_order(account_rows, results):
    """Check the file is sorted by contact_score desc, urgency_score desc, host_count desc, account_id (D9.6 item 8)."""
    keys = [(-a["contact_score"], -a["urgency_score"], -a["host_count"], a["account_id"]) for a in account_rows]
    bad = [i for i in range(1, len(keys)) if keys[i - 1] > keys[i]]
    results.append(("file order is contact_score desc, urgency_score desc, host_count desc, account_id asc (D9.6 item 8)", not bad,
                    f"{len(bad)} adjacent pairs out of order; first at row {bad[0] if bad else 'none'}"))


def check_denylist(account_rows, results):
    """Apply the shared denylist rules to company_name; 0 hits expected."""
    matcher = load_matcher()
    rules = matcher.load_rules()
    hits = [(a["company_name"], hit[0], hit[1]) for a in account_rows if (hit := matcher.match_name(a["company_name"], "org", rules))]
    results.append(("denylist leakage in company_name (shared rules, org text)", not hits, f"{len(hits)} hits; {hits[:5] or 'none'}"))


def check_stage_rules(account_rows, results):
    """Check cross-column rules that need no signals: bounds, ordering of scores, M2 adjudication columns and the no-contact-before-adjudication rule."""
    bad = []
    for a in account_rows:
        scores = (a["fit_score"], a["urgency_score"], a["contact_score"])
        if any(s is None or not 0 <= s <= 100 for s in scores) or a["contact_score"] > a["urgency_score"] or a["contact_score"] * 100 < 50 * a["urgency_score"]:
            bad.append((a["company_name"], "score range or 0 <= contact <= urgency or FLOOR invariant"))
        if a["band"] not in BANDS or a["band_uncapped"] not in BANDS or a["final_band"] != a["band"]:
            bad.append((a["company_name"], "band, band_uncapped or final_band"))
        if a["band"] == "contact" and a["decision"] is None:
            bad.append((a["company_name"], "contact before adjudication (D10)"))
        if a["decision"] is not None or a["prompt_version"] is not None:
            bad.append((a["company_name"], "decision or prompt_version set at stage 4"))
        reasons = a["cap_reasons"].split(",") if a["cap_reasons"] else []
        if reasons != sorted(set(reasons)) or any(r not in CAP_ORDER for r in reasons) or (a["cap_reasons"] == ""):
            bad.append((a["company_name"], "cap_reasons values or order"))
    results.append(("score bounds, contact <= urgency, FLOOR invariant, band set, final_band = band, no contact before adjudication, decision null, cap_reasons order", not bad,
                    f"{len(bad)} violations; {bad[:3] or 'none'}"))


def run_checks(accounts_path, signals_path, companies_path, review_n=REVIEW_N):
    """Run every extra check with the review band size review_n; return (results, flagged alarm words, account rows, signal rows)."""
    con = duckdb.connect()
    account_rows = fetch_dicts(con, f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM read_parquet('{Path(accounts_path).as_posix()}')")
    signal_rows = fetch_dicts(con, f"SELECT {', '.join(SIGNAL_COLUMNS)} FROM read_parquet('{Path(signals_path).as_posix()}')")
    company_rows = fetch_dicts(con, f"SELECT company_id FROM read_parquet('{Path(companies_path).as_posix()}')")
    results = []
    check_ids_and_rows(account_rows, signal_rows, company_rows, results)
    check_recompute(account_rows, signal_rows, results, review_n)
    check_cut(account_rows, signal_rows, results, review_n)
    flagged = check_why(account_rows, signal_rows, results)
    check_order(account_rows, results)
    check_denylist(account_rows, results)
    check_stage_rules(account_rows, results)
    return results, flagged, account_rows, signal_rows


def quantile(values, q):
    """Return the linearly interpolated quantile q (0 to 1) of a list of numbers."""
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def recomputed_numbers(account_rows, signal_rows, review_n=REVIEW_N):
    """Return my own headline numbers (bands, would-be contacts, cut, cap sets, skip splits, quantiles, union effect) for the author-versus-mine table."""
    sigs = {s["company_id"]: s for s in signal_rows}
    mine, cut = reference_all(signal_rows, review_n)
    old = {s["company_id"]: reference_account(s, union=False) for s in signal_rows}
    bands = Counter(r["band"] for r in mine.values())
    sets = Counter(r["cap_reasons"] for r in mine.values() if r["cap_reasons"])
    review = [cid for cid, r in mine.items() if r["band"] == "review"]
    operator = lambda cid: bool(sigs[cid]["operator_shape_t1"] or sigs[cid]["operator_shape_t2"])  # noqa: E731
    skip_urgent = [cid for cid, r in mine.items() if r["band"] == "skip" and r["urgency_score"] > 0]
    below = [cid for cid in skip_urgent if mine[cid]["contact_score"] < REVIEW_MIN]
    beyond = [cid for cid in skip_urgent if mine[cid]["contact_score"] >= REVIEW_MIN]
    non_ssh = lambda cid: bool(sigs[cid]["risky_non_ssh_exposed"])  # noqa: E731
    cvss7 = lambda cid: sigs[cid]["max_cvss"] is not None and sigs[cid]["max_cvss"] >= 7.0  # noqa: E731
    out = {"rows": len(mine), **{b: bands.get(b, 0) for b in BANDS}, "would_be_contacts": cut["would_be_contacts"], "cap_sets": dict(sets),
           "urgency_above_0": sum(1 for r in mine.values() if r["urgency_score"] > 0), "fit_above_0": sum(1 for r in mine.values() if r["fit_score"] > 0),
           "max_fit": max(r["fit_score"] for r in mine.values()), "cut_score": cut["cut_score"], "tie_size": cut["tie_size"], "tie_kept": cut["tie_kept"],
           "tie_to_skip": cut["tie_to_skip"], "accounts_above_cut": cut["accounts_above_cut"], "top_n_only": cut["top_n_only"],
           "review_operator_shaped": sum(1 for cid in review if operator(cid)),
           "review_operator_via_cap": sum(1 for cid in review if operator(cid) and mine[cid]["band_uncapped"] == "contact"),
           "review_operator_via_top_n": sum(1 for cid in review if operator(cid) and mine[cid]["band_uncapped"] != "contact"),
           "review_singletons": sum(1 for cid in review if sigs[cid]["is_singleton"]), "review_low_confidence": sum(1 for cid in review if sigs[cid]["identity_confidence"] == "low"),
           "skip_urgency_above_0": len(skip_urgent), "skip_below_floor": len(below), "skip_below_floor_non_ssh": sum(1 for c in below if non_ssh(c)),
           "skip_below_floor_cvss7": sum(1 for c in below if cvss7(c)), "skip_below_floor_overlap": sum(1 for c in below if non_ssh(c) and cvss7(c)),
           "skip_below_floor_union": sum(1 for c in below if non_ssh(c) or cvss7(c)), "skip_beyond_cut": len(beyond),
           "skip_beyond_cut_non_ssh": sum(1 for c in beyond if non_ssh(c)), "skip_beyond_cut_cvss7": sum(1 for c in beyond if cvss7(c)),
           "skip_beyond_cut_union": sum(1 for c in beyond if non_ssh(c) or cvss7(c)),
           "longest_why_words": max((len(words(a["why"])) for a in account_rows if a["why"]), default=0),
           "union_fit_lost": sum(1 for cid in mine if mine[cid]["fit_score"] < old[cid]["fit_score"]),
           "union_contact_changed": sum(1 for cid in mine if mine[cid]["contact_score"] != old[cid]["contact_score"]),
           "quantiles": {name: {q: quantile([r[name] for r in mine.values()], q / 100) for q in (5, 25, 50, 75, 90, 95, 99)} for name in ("fit_score", "urgency_score", "contact_score")},
           "max_scores": {name: max(r[name] for r in mine.values()) for name in ("fit_score", "urgency_score", "contact_score")}}
    return out


def author_table(mine):
    """Return markdown lines comparing the author's reported numbers with my recomputation; every mismatch is marked."""
    rows = [(k, v, mine[k]) for k, v in AUTHOR.items() if k != "cap_sets"]
    rows += [(f"cap set {k}", v, mine["cap_sets"].get(k, 0)) for k, v in AUTHOR["cap_sets"].items()]
    lines = ["| quantity | author | mine | match |", "|---|---|---|---|"]
    lines += [f"| {k} | {a} | {m} | {'yes' if a == m else 'NO'} |" for k, a, m in rows]
    return lines


def render(results):
    """Return the results as markdown table lines."""
    failed = [r for r in results if not r[1]]
    lines = [f"**{'FAIL' if failed else 'PASS'}**: {len(results) - len(failed)}/{len(results)} extra checks passed", "", "| result | check | evidence |", "|---|---|---|"]
    lines += [f"| {'PASS' if ok else 'FAIL'} | {name} | {evidence} |" for name, ok, evidence in results]
    return lines


def main():
    """Run the extra checks on the real files, print markdown with the recomputed numbers, exit 1 on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts", default=str(ACCOUNTS_PATH))
    parser.add_argument("--signals", default=str(SIGNALS_PATH))
    parser.add_argument("--companies", default=str(COMPANIES_PATH))
    parser.add_argument("--review-n", type=int, default=REVIEW_N, help="REVIEW_N of the run (provisional, D11.2)")
    args = parser.parse_args()
    results, flagged, account_rows, signal_rows = run_checks(args.accounts, args.signals, args.companies, args.review_n)
    print("\n".join(render(results)))
    mine = recomputed_numbers(account_rows, signal_rows, args.review_n)
    print("\n## Author versus independent recomputation\n")
    print("\n".join(author_table(mine)))
    print("\n## Other recomputed numbers (mine)\n")
    for key, value in mine.items():
        if key not in ("cap_sets", "quantiles"):
            print(f"- {key}: {value}")
    print(f"- cap sets: {mine['cap_sets']}")
    for name, qs in mine["quantiles"].items():
        print(f"- {name} quantiles (linear): {', '.join(f'p{q} {v:.2f}' for q, v in qs.items())}")
    print(f"\n## Alarm or reassurance words in why (report only, {len(flagged)} hits)\n")
    print("\n".join(f"- {n}: {w}" for n, w in flagged[:20]) or "- none")
    sys.exit(1 if any(not r[1] for r in results) else 0)


if __name__ == "__main__":
    main()
