"""Check candidate signals: coverage, prevalence, redundancy (correlation), and lift against labels."""
import argparse
import itertools

import duckdb

CORR_FLAG = 0.8
NUMERIC_PREFIXES = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "FLOAT", "DOUBLE", "DECIMAL", "BOOLEAN")


def source_sql(path):
    """Return the DuckDB reader expression for a file path."""
    safe = path.replace("'", "''")
    if path.lower().endswith(".parquet"):
        return f"read_parquet('{safe}')"
    return f"read_csv_auto('{safe}')"


def pick_signals(con, requested):
    """Return the requested signal columns, or every numeric/boolean column if none given."""
    if requested:
        return [c.strip() for c in requested.split(",")]
    schema = con.execute("DESCRIBE t").fetchall()
    return [name for name, dtype, *_ in schema if dtype.upper().startswith(NUMERIC_PREFIXES)]


def print_coverage(con, signals):
    """Print null rate, share non-zero and mean for each signal."""
    print("signal coverage:")
    print(f"  {'signal':<28}{'null %':>8}{'nonzero %':>11}{'mean':>10}")
    for name in signals:
        col = f'"{name}"'
        null_pct, nonzero_pct, mean = con.execute(
            f"SELECT 100.0 * (count(*) - count({col})) / count(*), "
            f"100.0 * sum(CASE WHEN {col}::DOUBLE <> 0 THEN 1 ELSE 0 END) / count(*), avg({col}::DOUBLE) FROM t"
        ).fetchone()
        print(f"  {name:<28}{null_pct:>8.1f}{(nonzero_pct or 0):>11.1f}{(mean or 0):>10.3f}")


def print_redundancy(con, signals):
    """Flag pairs of signals that are highly correlated (they may measure the same thing)."""
    print(f"\nredundant pairs (|corr| >= {CORR_FLAG}):")
    found = False
    for a, b in itertools.combinations(signals, 2):
        corr = con.execute(f'SELECT corr("{a}"::DOUBLE, "{b}"::DOUBLE) FROM t').fetchone()[0]
        if corr is not None and abs(corr) >= CORR_FLAG:
            print(f"  {a} ~ {b}: {corr:.2f}")
            found = True
    if not found:
        print("  none")


def print_lift(con, signals, labels, positive, id_col):
    """Print the signal's mean among positive vs negative labelled accounts."""
    con.execute(f"CREATE VIEW lab AS SELECT * FROM read_json_auto('{labels}')")
    print(f"\nlift vs labels ('{positive}' vs rest):")
    print(f"  {'signal':<28}{'mean if +':>11}{'mean if -':>11}")
    for name in signals:
        col = f'"{name}"'
        pos, neg = con.execute(
            f"SELECT avg(CASE WHEN l.label = ? THEN t.{col}::DOUBLE END), "
            f"avg(CASE WHEN l.label <> ? THEN t.{col}::DOUBLE END) "
            f'FROM t JOIN lab l ON t."{id_col}" = l."{id_col}" WHERE l.label IS NOT NULL',
            [positive, positive],
        ).fetchone()
        print(f"  {name:<28}{(pos if pos is not None else float('nan')):>11.3f}{(neg if neg is not None else float('nan')):>11.3f}")


def main():
    """Parse arguments and print the signal diagnostics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="signals parquet/csv")
    parser.add_argument("--signals", help="comma-separated columns (default: all numeric)")
    parser.add_argument("--labels", help="labelled JSONL (id column + label) to compute lift")
    parser.add_argument("--positive", default="contact")
    parser.add_argument("--id", default="account_id")
    args = parser.parse_args()

    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM {source_sql(args.path)}")
    signals = pick_signals(con, args.signals)
    print_coverage(con, signals)
    print_redundancy(con, signals)
    if args.labels:
        print_lift(con, signals, args.labels, args.positive, args.id)


if __name__ == "__main__":
    main()
