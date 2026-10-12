"""Check a data layer against its contract in context/contracts/<layer>.yml and report PASS/FAIL."""
import argparse
import sys
from datetime import date
from pathlib import Path

import duckdb

try:
    import yaml
except ImportError:
    sys.exit("pyyaml is required: pip install pyyaml")

SAMPLE_LIMIT = 5
REPO_ROOT = Path(__file__).resolve().parents[4]
OPERATORS = {"<=": lambda a, b: a <= b, "==": lambda a, b: a == b, ">=": lambda a, b: a >= b}


def source_sql(path):
    """Return the DuckDB reader expression for a file path or glob."""
    safe = str(path).replace("'", "''")
    if str(path).lower().endswith(".parquet"):
        return f"read_parquet('{safe}')"
    return f"read_csv_auto('{safe}')"


def quote(name):
    """Quote a column name for safe use in SQL."""
    return '"' + name.replace('"', '""') + '"'


def scalar(con, sql):
    """Run a query and return its first value."""
    return con.execute(sql).fetchone()[0]


def check_columns(con, contract, results):
    """Check column existence, type, nullability and value ranges."""
    actual = {row[0]: row[1] for row in con.execute("DESCRIBE t").fetchall()}
    for name, rule in contract.get("columns", {}).items():
        if name not in actual:
            results.append((f"column '{name}' exists", False, "missing from table"))
            continue
        want = rule.get("type")
        if want:
            ok = actual[name].upper().startswith(want.upper())
            results.append((f"column '{name}' type {want}", ok, f"actual {actual[name]}"))
        col = quote(name)
        if rule.get("nullable") is False:
            bad = scalar(con, f"SELECT count(*) FROM t WHERE {col} IS NULL")
            results.append((f"column '{name}' has no nulls", bad == 0, f"{bad} nulls"))
        for bound, op in (("min", "<"), ("max", ">")):
            if bound in rule:
                bad = scalar(con, f"SELECT count(*) FROM t WHERE {col} {op} {rule[bound]}")
                results.append((f"column '{name}' {bound} {rule[bound]}", bad == 0, f"{bad} violations"))


def check_key(con, contract, results):
    """Check the declared key is unique and non-null."""
    key = contract.get("key")
    if not key:
        return
    cols = [key] if isinstance(key, str) else key
    joined = ", ".join(quote(c) for c in cols)
    dupes = scalar(con, f"SELECT count(*) - count(DISTINCT ({joined})) FROM t")
    results.append((f"key {cols} is unique", dupes == 0, f"{dupes} duplicate rows"))


def check_row_rule(con, contract, results):
    """Compare this layer's row count with another file (e.g. companies <= hosts)."""
    rule = contract.get("row_rule")
    if not rule:
        return
    mine = scalar(con, "SELECT count(*) FROM t")
    other = scalar(con, f"SELECT count(*) FROM {source_sql(rule['other'])}")
    ok = OPERATORS[rule["op"]](mine, other)
    results.append((f"row count {rule['op']} {rule['other']}", ok, f"this={mine:,} other={other:,}"))


def load_matcher():
    """Import the shared matcher scripts/denylist_match.py from the repo root; return (module, error text)."""
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        import denylist_match
    except ImportError as exc:
        return None, f"cannot import shared matcher from {scripts_dir}: {exc}"
    return denylist_match, None


def distinct_values(con, column):
    """Return (value, row count) pairs for the non-null distinct values of a column."""
    col = quote(column)
    return con.execute(f"SELECT {col}, count(*) FROM t WHERE {col} IS NOT NULL GROUP BY 1").fetchall()


def resolve_path(path):
    """Resolve a contract path against the repo root when it is relative."""
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def check_denylist(con, contract, results):
    """Fail on denylist leakage: old form {column, file} (exact, normalised both sides) or new form {column, rules: shared}."""
    rule = contract.get("denylist")
    if not rule:
        return
    label = f"denylist leakage in '{rule['column']}'"
    matcher, error = load_matcher()
    if matcher is None:
        results.append((label, False, error))
        return
    try:
        if rule.get("rules") == "shared":
            rules = matcher.load_rules(resolve_path(rule["context_dir"]) if rule.get("context_dir") else None)
        elif "file" in rule:
            names = matcher.load_exact(resolve_path(rule["file"]))
        else:
            results.append((label, False, "denylist needs 'rules: shared' or 'file: <path>'"))
            return
    except (OSError, ValueError) as exc:
        results.append((label, False, f"cannot load denylist rules: {exc}"))
        return
    values = distinct_values(con, rule["column"])
    hits = []
    if rule.get("rules") == "shared":
        for value, rows in values:
            hit = matcher.match_name(value, "org", rules)  # D5: org text only, never the isp field
            if hit:
                hits.append((value, rows, hit[0], hit[1]))
        label += " (shared rules)"
    else:
        hits = [(v, n, "exact", matcher.normalise(v)) for v, n in values if matcher.normalise(v) in names]
        label += " (exact file)"
    hits.sort(key=lambda h: -h[1])
    evidence = "none"
    if hits:
        shown = "; ".join(f"{v!r} x{n} [{kind}: {entry}]" for v, n, kind, entry in hits[:SAMPLE_LIMIT])
        evidence = f"{len(hits)} distinct names ({sum(h[1] for h in hits)} rows) match; e.g. {shown}"
    results.append((label, not hits, evidence))


def check_infra_reason(con, contract, results):
    """Fail if the infra_reason column holds a value outside the shared INFRA_REASONS set (isp_* values included)."""
    rule = contract.get("infra_reason")
    if rule is None:
        return
    rule = rule or {}
    column = rule.get("column", "infra_reason")
    label = f"'{column}' values within INFRA_REASONS"
    matcher, error = load_matcher()
    if matcher is None:
        results.append((label, False, error))
        return
    allowed = set(matcher.INFRA_REASONS)
    bad = [(v, n) for v, n in distinct_values(con, column) if v not in allowed]
    if rule.get("nullable", True) is False:
        nulls = scalar(con, f"SELECT count(*) FROM t WHERE {quote(column)} IS NULL")
        if nulls:
            bad.append((None, nulls))
    bad.sort(key=lambda b: -b[1])
    results.append((label, not bad, f"bad values: {bad[:SAMPLE_LIMIT]}" if bad else "none"))


def check_shares(con, contract, results):
    """Check category shares (optionally row-weighted) sum to 100% with no nulls and the resolved share is in a range."""
    rule = contract.get("shares")
    if not rule:
        return
    col = quote(rule["column"])
    weight = quote(rule["weight"]) if rule.get("weight") else "1"
    rows = con.execute(f"SELECT {col}, sum({weight}) FROM t GROUP BY 1").fetchall()
    total = sum(n for _, n in rows)
    if not total:
        results.append((f"shares of '{rule['column']}'", False, "table is empty"))
        return
    shares = {k: 100.0 * n / total for k, n in rows}
    null_pct = shares.get(None, 0.0)
    allowed = rule.get("allowed")
    outside = {k: round(v, 2) for k, v in shares.items() if k is not None and allowed and k not in allowed}
    ok = abs(sum(shares.values()) - 100.0) < 0.01 and null_pct == 0 and not outside
    detail = ", ".join(f"{k}={v:.2f}%" for k, v in sorted(shares.items(), key=lambda kv: str(kv[0])))
    results.append((f"shares of '{rule['column']}' sum to 100%, no nulls, allowed values only", ok,
                    f"{detail}; unexpected {outside}"))
    if "resolved_values" in rule:
        resolved = sum(shares.get(k, 0.0) for k in rule["resolved_values"])
        low, high = rule.get("resolved_min", 0), rule.get("resolved_max", 100)
        results.append((f"resolved share {low}% to {high}%", low <= resolved <= high, f"{resolved:.2f}%"))


def check_custom(con, contract, results):
    """Run custom SQL checks; each query must return a single number equal to `expect`."""
    for check in contract.get("checks", []):
        value = scalar(con, check["sql"])
        expect = check.get("expect", 0)
        results.append((check["name"], value == expect, f"got {value}, expected {expect}"))


def render(layer, results):
    """Return the results as markdown lines."""
    failed = [r for r in results if not r[1]]
    lines = [f"# Data quality: {layer} ({date.today()})", "", f"**{'FAIL' if failed else 'PASS'}**: "
             f"{len(results) - len(failed)}/{len(results)} checks passed", "",
             "| result | check | evidence |", "|---|---|---|"]
    for name, ok, evidence in results:
        lines.append(f"| {'PASS' if ok else 'FAIL'} | {name} | {evidence} |")
    return lines


def main():
    """Load the contract, run all checks, print the report, exit 1 on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", help="path to context/contracts/<layer>.yml")
    parser.add_argument("--path", help="override the data file named in the contract")
    parser.add_argument("--report", action="store_true", help="save to outputs/dq/<layer>_<date>.md")
    args = parser.parse_args()

    contract = yaml.safe_load(Path(args.contract).read_text(encoding="utf-8"))
    layer = contract["layer"]
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM {source_sql(args.path or contract['path'])}")

    results = []
    for step in (check_columns, check_key, check_row_rule, check_denylist, check_infra_reason, check_shares, check_custom):
        step(con, contract, results)
    lines = render(layer, results)
    print("\n".join(lines))
    if args.report:
        out = Path("outputs/dq") / f"{layer}_{date.today()}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nsaved {out}")
    sys.exit(1 if any(not r[1] for r in results) else 0)


if __name__ == "__main__":
    main()
