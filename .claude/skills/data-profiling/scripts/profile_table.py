"""Profile a table (parquet/csv/json): rows, nulls, distincts, min/max, top values, samples."""
import argparse

import duckdb

TRUNCATE_AT = 60


def source_sql(path):
    """Return the DuckDB reader expression for a file path or glob."""
    safe = path.replace("'", "''")
    lower = path.lower()
    if lower.endswith(".parquet"):
        return f"read_parquet('{safe}')"
    if lower.endswith((".json", ".jsonl", ".ndjson")):
        return f"read_json_auto('{safe}')"
    return f"read_csv_auto('{safe}')"


def quote(name):
    """Quote a column name for safe use in SQL."""
    return '"' + name.replace('"', '""') + '"'


def load(con, path, sample):
    """Create table t from the file, optionally as a seeded random row sample."""
    query = f"SELECT * FROM {source_sql(path)}"
    if sample:
        query += f" USING SAMPLE reservoir({int(sample)} ROWS) REPEATABLE (42)"
    con.execute(f"CREATE TABLE t AS {query}")


def short(value):
    """Truncate long values so the report stays readable."""
    text = str(value)
    return text if len(text) <= TRUNCATE_AT else text[:TRUNCATE_AT] + "..."


def profile_column(con, name, dtype, total, top):
    """Return a dict of stats for one column."""
    col = quote(name)
    nulls, distinct = con.execute(
        f"SELECT count(*) - count({col}), approx_count_distinct({col}) FROM t"
    ).fetchone()
    stats = {
        "name": name, "type": dtype, "distinct": distinct, "min": None, "max": None,
        "null_pct": round(100 * nulls / total, 2) if total else 0.0, "top": [],
    }
    try:
        stats["min"], stats["max"] = con.execute(
            f"SELECT min({col})::VARCHAR, max({col})::VARCHAR FROM t"
        ).fetchone()
    except duckdb.Error:
        pass
    if dtype == "VARCHAR":
        rows = con.execute(
            f"SELECT {col}, count(*) AS c FROM t WHERE {col} IS NOT NULL "
            f"GROUP BY 1 ORDER BY c DESC LIMIT {int(top)}"
        ).fetchall()
        stats["top"] = [f"{short(v)} ({c})" for v, c in rows]
    return stats


def build_report(con, path, top):
    """Return the profile as a list of markdown lines."""
    total = con.execute("SELECT count(*) FROM t").fetchone()[0]
    schema = con.execute("DESCRIBE t").fetchall()
    lines = [f"# Profile: {path}", "", f"- rows profiled: {total:,}", f"- columns: {len(schema)}", ""]
    lines += ["| column | type | null % | distinct | min | max |", "|---|---|---|---|---|---|"]
    details = []
    for name, dtype, *_ in schema:
        s = profile_column(con, name, dtype, total, top)
        lines.append(
            f"| {name} | {dtype} | {s['null_pct']} | {s['distinct']:,} | "
            f"{short(s['min'])} | {short(s['max'])} |"
        )
        if s["top"]:
            details.append(f"- `{name}` top values: " + "; ".join(s["top"]))
    lines += ["", "## Top values (text columns)", *details, "", "## 5 random rows"]
    cur = con.execute("SELECT * FROM t USING SAMPLE reservoir(5 ROWS)")
    names = [d[0] for d in cur.description]
    for i, row in enumerate(cur.fetchall(), 1):
        lines.append(f"- row {i}: " + ", ".join(f"{n}={short(v)}" for n, v in zip(names, row)))
    return lines


def main():
    """Parse arguments, profile the file, print and optionally save the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="parquet/csv/json file or glob")
    parser.add_argument("--sample", type=int, default=0, help="profile a random N-row sample")
    parser.add_argument("--top", type=int, default=5, help="top values per text column")
    parser.add_argument("--out", help="also write the report to this markdown file")
    args = parser.parse_args()

    con = duckdb.connect()
    load(con, args.path, args.sample)
    report = "\n".join(build_report(con, args.path, args.top))
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(report + "\n")


if __name__ == "__main__":
    main()
