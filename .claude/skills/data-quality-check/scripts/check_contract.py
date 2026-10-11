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


def check_denylist(con, contract, results):
    """Fail if any denylisted name (cloud, CDN, ISP) appears in the named column."""
    rule = contract.get("denylist")
    if not rule:
        return
    names = [
        line.strip().lower()
        for line in Path(rule["file"]).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    col = quote(rule["column"])
    hits = con.execute(
        f"SELECT {col}, count(*) FROM t WHERE lower(trim({col})) IN (SELECT unnest(?)) GROUP BY 1 "
        f"ORDER BY 2 DESC LIMIT {SAMPLE_LIMIT}", [names],
    ).fetchall()
    results.append((f"denylist leakage in '{rule['column']}'", not hits, f"hits: {hits}" if hits else "none"))


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
    for step in (check_columns, check_key, check_row_rule, check_denylist, check_custom):
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
