"""Show a score column's distribution and preview band sizes for candidate thresholds."""
import argparse

import duckdb

QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
BAR_WIDTH = 40


def source_sql(path):
    """Return the DuckDB reader expression for a file path."""
    safe = path.replace("'", "''")
    if path.lower().endswith(".parquet"):
        return f"read_parquet('{safe}')"
    return f"read_csv_auto('{safe}')"


def print_summary(con, score):
    """Print count, min, max, mean and quantiles for the score column."""
    n, lo, hi, mean = con.execute(
        f'SELECT count("{score}"), min("{score}"), max("{score}"), avg("{score}") FROM t'
    ).fetchone()
    if not n:
        print(f"{score}: 0 rows (no scores to summarise)")
        return False
    print(f"{score}: n={n:,} min={lo} max={hi} mean={mean:.2f}")
    for q in QUANTILES:
        value = con.execute(f'SELECT quantile_cont("{score}", {q}) FROM t').fetchone()[0]
        print(f"  p{int(q * 100):<3} {value:.2f}")
    return True


def print_histogram(con, score, buckets):
    """Print an ASCII histogram so the shape of the distribution is visible."""
    lo, hi = con.execute(f'SELECT min("{score}"), max("{score}") FROM t').fetchone()
    if lo is None:
        print("histogram: no scores")
        return
    width = (hi - lo) / buckets or 1
    rows = con.execute(
        f'SELECT least(floor(("{score}" - {lo}) / {width}), {buckets - 1})::INT AS b, count(*) '
        f"FROM t WHERE \"{score}\" IS NOT NULL GROUP BY 1 ORDER BY 1"
    ).fetchall()
    peak = max(c for _, c in rows)
    print("\nhistogram:")
    for b, c in rows:
        start = lo + b * width
        print(f"  {start:7.1f}+ | {'#' * max(1, round(BAR_WIDTH * c / peak))} {c:,}")


def print_bands(con, score, contact, review):
    """Print how many accounts land in each band at the proposed thresholds."""
    total = con.execute("SELECT count(*) FROM t").fetchone()[0]
    sql = (
        f"SELECT CASE WHEN \"{score}\" >= {contact} THEN 'contact' "
        f"WHEN \"{score}\" >= {review} THEN 'review' ELSE 'skip' END AS band, count(*) "
        f"FROM t GROUP BY 1"
    )
    counts = dict(con.execute(sql).fetchall())
    print(f"\nbands at contact >= {contact}, review >= {review}:")
    for band in ("contact", "review", "skip"):
        c = counts.get(band, 0)
        print(f"  {band:<8} {c:>10,}  {(100 * c / total if total else 0.0):5.1f}%")


def main():
    """Parse arguments and print the distribution report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="accounts parquet/csv")
    parser.add_argument("--score", default="contact_score", help="score column to inspect")
    parser.add_argument("--buckets", type=int, default=10)
    parser.add_argument("--contact", type=float, help="candidate contact threshold")
    parser.add_argument("--review", type=float, help="candidate review threshold")
    args = parser.parse_args()

    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM {source_sql(args.path)}")
    print_summary(con, args.score)
    print_histogram(con, args.score, args.buckets)
    if args.contact is not None and args.review is not None:
        print_bands(con, args.score, args.contact, args.review)


if __name__ == "__main__":
    main()
