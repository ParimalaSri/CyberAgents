"""Independent accounts-layer checks: recompute fit, urgency, contact, bands, caps and top_signals from signals (D9.6 to D9.9, D10), why phrases, sort order."""
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

# PROVISIONAL constants (D9.7, D10): the starting point only, not calibrated, not owner approved. Written here from the decision text,
# not copied from pipeline/4_score.py. Change them together with context/contracts/accounts.yml when scoring-calibration decides.
KEV_POINTS = 50
CVSS_POINTS = {3: 40, 2: 25, 1: 10}
EXPOSURE_POINTS = (("exposed_and_outdated", 30), ("risky_non_ssh_exposed", 15), ("risky_service_exposed", 5))  # highest applicable
HYGIENE_POINTS = (("eol_stack", 10), ("cert_expired_or_soon", 5), ("legacy_tls", 5))  # summed
TERRITORY_POINTS, FOOTPRINT_POINTS_PER_BAND, SENSITIVE_POINTS, OPERATOR_PENALTY = 35, 15, 20, 30
FLOOR = Fraction(1, 2)  # contact form (b), PROVISIONAL
CONTACT_MIN, REVIEW_MIN = 40, 20  # X and Y, PROVISIONAL
NOISE_MIN_HOSTS, NOISE_MIN_SHARE = 2, 0.5  # D9.3, decided
WHY_MAX_WORDS = 40  # D9.6 item 7 and D9.8
CLAUSE = "Not yet checked that this is an end-user organisation, not a network operator."  # D10
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
# The numbers the stage author reported (accounts_stage_2026-10-11.md and the hand-off), compared with my own recomputation.
AUTHOR = {"rows": 5790, "contact": 0, "review": 664, "skip": 5125, "exclude": 1, "would_be_contacts": 107, "urgency_above_0": 1324, "fit_above_0": 2271,
          "union_fit_lost": 167, "review_by_threshold": 557, "max_contact_before_d10": 75,
          "cap_sets": {"operator_unverified": 70, "operator_unverified,singleton": 20, "operator_name_shape,operator_unverified": 12,
                       "low_confidence,operator_unverified,singleton": 3, "low_confidence,operator_unverified": 1,
                       "operator_name_shape,operator_unverified,singleton": 1}}
# Phrase table, written from D9.6 item 7 (the wording the stage uses is matched here by pattern; the signal each phrase names must be true).
PHRASES = (
    ("kev_exposed", re.compile(r"(\d+) hosts? with a vulnerability on the CISA known-exploited list", re.I)),
    ("max_cvss_band", re.compile(r"worst vulnerability scores CVSS (\d+(?:\.\d+)?)", re.I)),
    ("exposed_and_outdated", re.compile(r"an exposed admin or database service \(([^)]*)\) on outdated software", re.I)),
    ("risky_non_ssh_exposed", re.compile(r"remote-admin or database services exposed \(([^)]*)\)", re.I)),
    ("risky_service_exposed", re.compile(r"SSH \(port 22\) open to the internet", re.I)),
    ("eol_stack", re.compile(r"(\d+) hosts? on end-of-life software", re.I)),
    ("cert_expired_or_soon", re.compile(r"(\d+) hosts? with expired or soon-expiring certificates", re.I)),
    ("legacy_tls", re.compile(r"(\d+) hosts? still offering old TLS versions", re.I)),
    ("footprint_band", re.compile(r"(\d+) IPs in the footprint")),
    ("in_territory", re.compile(r"hosts located in ([A-Z]{2})", re.I)),
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
    "in_territory": lambda sig, g, ports: bool(sig["in_territory"]) and g == sig["country_code"],
    "sensitive_stack": lambda sig, g, ports: bool(sig["sensitive_stack"]),
}
CAP_CLAUSES = (("operator_name_shape", "Name looks like a network operator."), ("singleton", "Only one host seen."),
               ("low_confidence", "Named only by a TLS certificate."))
NO_SIGNAL = re.compile(r"No exposure signal found in the scan \((\d+) hosts? seen\)\.")
EXCLUDED = re.compile(r"Mostly honeypot or attacker-infrastructure hosts \((\d+) of (\d+)\)\.")
LIMITED = "Exposure is limited."  # stage wording for a skip account that does have an urgency signal; not in D9.6 text (DQ-013)


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
    if sig["in_territory"]:
        out.append(("in_territory", TERRITORY_POINTS, "fit"))
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
            "band": "review" if reasons else uncapped, "top_signals": top}


def compare_reference(account_rows, signal_rows):
    """Compare every account with the recomputation; return (missing ids, extra ids, per-column disagreement counts, examples, fallback ids)."""
    sigs = {s["company_id"]: s for s in signal_rows}
    seen = {a["account_id"]: a for a in account_rows}
    diffs, examples, fallback = Counter(), {}, []
    for aid, acc in seen.items():
        if aid not in sigs:
            continue
        ref = reference_account(sigs[aid])
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


def check_recompute(account_rows, signal_rows, results):
    """Check fit, urgency, contact, band_uncapped, cap_reasons, band and top_signals equal the independent recomputation on every account."""
    missing, extra, diffs, examples, fallback = compare_reference(account_rows, signal_rows)
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
    """Return the list of problems with one why: words, forbidden characters, clause, phrases true in signals, one cap clause, nothing unrecognised."""
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
    clauses = [reason for reason, text in CAP_CLAUSES if text in rest]
    for reason, text in CAP_CLAUSES:
        rest = rest.replace(text, "")
    reasons = (account["cap_reasons"] or "").split(",")
    if len(clauses) > 1 or any(c not in reasons for c in clauses) or (not clauses and any(r in reasons for r in ("low_confidence", "operator_name_shape", "singleton"))):
        problems.append(f"cap clause {clauses} does not match cap_reasons {account['cap_reasons']!r} (at most one clause, exactly one when a cap flag is listed)")
    if LIMITED in rest:
        rest = rest.replace(LIMITED, "")
        if account["band"] != "skip":
            problems.append("'Exposure is limited.' on an account that is not skip")
    elif account["band"] == "skip":
        problems.append("skip account with urgency above 0 lacks the 'Exposure is limited.' sentence (stage convention)")
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


def run_checks(accounts_path, signals_path, companies_path):
    """Run every extra check; return (results, flagged alarm words, account rows, signal rows)."""
    con = duckdb.connect()
    account_rows = fetch_dicts(con, f"SELECT {', '.join(ACCOUNT_COLUMNS)} FROM read_parquet('{Path(accounts_path).as_posix()}')")
    signal_rows = fetch_dicts(con, f"SELECT {', '.join(SIGNAL_COLUMNS)} FROM read_parquet('{Path(signals_path).as_posix()}')")
    company_rows = fetch_dicts(con, f"SELECT company_id FROM read_parquet('{Path(companies_path).as_posix()}')")
    results = []
    check_ids_and_rows(account_rows, signal_rows, company_rows, results)
    check_recompute(account_rows, signal_rows, results)
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


def recomputed_numbers(account_rows, signal_rows):
    """Return my own headline numbers (bands, would-be contacts, cap sets, quantiles, above-zero counts, union effect) for the author-versus-mine table."""
    sigs = {s["company_id"]: s for s in signal_rows}
    mine = {s["company_id"]: reference_account(s) for s in signal_rows}
    old = {s["company_id"]: reference_account(s, union=False) for s in signal_rows}
    bands = Counter(r["band"] for r in mine.values())
    sets = Counter(r["cap_reasons"] for r in mine.values() if r["cap_reasons"])
    review = [cid for cid, r in mine.items() if r["band"] == "review"]
    out = {"rows": len(mine), **{b: bands.get(b, 0) for b in BANDS}, "would_be_contacts": sum(1 for r in mine.values() if r["band_uncapped"] == "contact"),
           "cap_sets": dict(sets), "urgency_above_0": sum(1 for r in mine.values() if r["urgency_score"] > 0),
           "fit_above_0": sum(1 for r in mine.values() if r["fit_score"] > 0), "fit_above_0_t1_only": sum(1 for r in old.values() if r["fit_score"] > 0),
           "union_fit_lost": sum(1 for cid in mine if mine[cid]["fit_score"] < old[cid]["fit_score"]),
           "union_contact_changed": sum(1 for cid in mine if mine[cid]["contact_score"] != old[cid]["contact_score"]),
           "review_by_threshold": sum(1 for cid in review if mine[cid]["band_uncapped"] == "review"),
           "review_singletons": sum(1 for cid in review if sigs[cid]["is_singleton"]),
           "review_operator_shaped": sum(1 for cid in review if sigs[cid]["operator_shape_t1"] or sigs[cid]["operator_shape_t2"]),
           "review_low_confidence": sum(1 for cid in review if sigs[cid]["identity_confidence"] == "low"),
           "review_threshold_operator_shaped": sum(1 for cid in review if mine[cid]["band_uncapped"] == "review" and (sigs[cid]["operator_shape_t1"] or sigs[cid]["operator_shape_t2"])),
           "max_contact": max(r["contact_score"] for r in mine.values()), "max_contact_t1_only": max(r["contact_score"] for r in old.values()),
           "would_be_t1_only": sum(1 for r in old.values() if r["band_uncapped"] == "contact"),
           "quantiles": {name: {q: quantile([r[name] for r in mine.values()], q / 100) for q in (5, 25, 50, 75, 90, 95, 99)} for name in ("fit_score", "urgency_score", "contact_score")},
           "max_scores": {name: max(r[name] for r in mine.values()) for name in ("fit_score", "urgency_score", "contact_score")}}
    return out


def author_table(mine):
    """Return markdown lines comparing the author's reported numbers with my recomputation; every mismatch is marked."""
    rows = [(k, AUTHOR[k], mine[k]) for k in ("rows", "contact", "review", "skip", "exclude", "would_be_contacts", "urgency_above_0", "fit_above_0", "union_fit_lost",
                                              "review_by_threshold")]
    rows += [(f"cap set {k}", v, mine["cap_sets"].get(k, 0)) for k, v in AUTHOR["cap_sets"].items()]
    rows.append(("max contact_score before D10 (T1-only penalty, mine)", AUTHOR["max_contact_before_d10"], mine["max_contact_t1_only"]))
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
    args = parser.parse_args()
    results, flagged, account_rows, signal_rows = run_checks(args.accounts, args.signals, args.companies)
    print("\n".join(render(results)))
    mine = recomputed_numbers(account_rows, signal_rows)
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
