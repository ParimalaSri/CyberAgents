"""Print the mandatory stage report: row count, null rates, 5 random rows, diff vs previous layer."""
import argparse

import duckdb

KEY_DISPLAY_LIMIT = 15


def source_sql(path):
    """Return the DuckDB reader expression for a file path or glob."""
    safe = path.replace("'", "''")
    if path.lower().endswith(".parquet"):
        return f"read_parquet('{safe}')"
    return f"read_csv_auto('{safe}')"


def quote(name):
    """Quote a column name for safe use in SQL."""
    return '"' + name.replace('"', '""') + '"'


def count_rows(con, path):
    """Return the number of rows in a file."""
    return con.execute(f"SELECT count(*) FROM {source_sql(path)}").fetchone()[0]


def null_rates(con, path, columns, total):
    """Return (column, null percent) pairs for the given columns, worst first."""
    rates = []
    for name in columns:
        nulls = con.execute(
            f"SELECT count(*) - count({quote(name)}) FROM {source_sql(path)}"
        ).fetchone()[0]
        rates.append((name, round(100 * nulls / total, 2) if total else 0.0))
    return sorted(rates, key=lambda pair: -pair[1])


def main():
    """Parse arguments and print the stage report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="this stage's output file")
    parser.add_argument("--prev", help="previous layer's file, for the row count comparison")
    parser.add_argument("--keys", help="comma-separated key columns (default: all columns)")
    args = parser.parse_args()

    con = duckdb.connect()
    total = count_rows(con, args.path)
    schema = con.execute(f"DESCRIBE SELECT * FROM {source_sql(args.path)}").fetchall()
    columns = [c.strip() for c in args.keys.split(",")] if args.keys else [r[0] for r in schema]

    print(f"== Stage report: {args.path}")
    print(f"rows: {total:,}")
    if args.prev:
        prev_total = count_rows(con, args.prev)
        change = total - prev_total
        pct = round(100 * change / prev_total, 2) if prev_total else 0.0
        print(f"previous layer: {prev_total:,} rows | change: {change:+,} ({pct:+}%)")
        if change:
            print("ACTION: explain this row count difference in the PR / docs/ISSUES.md.")

    print("\nnull rates (worst first):")
    for name, pct in null_rates(con, args.path, columns, total)[:KEY_DISPLAY_LIMIT]:
        print(f"  {name:<30} {pct:>6}%")

    print("\n5 random rows:")
    cur = con.execute(f"SELECT * FROM {source_sql(args.path)} USING SAMPLE reservoir(5 ROWS)")
    names = [d[0] for d in cur.description]
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  [{i}] " + ", ".join(f"{n}={str(v)[:40]}" for n, v in zip(names, row)))


if __name__ == "__main__":
    main()
