"""Preview how organisation names collapse into companies: normalisation, clusters, denylist, unresolved share."""
import argparse
from pathlib import Path

import duckdb

SUFFIXES = "inc|llc|ltd|limited|pty|corp|corporation|co|company|gmbh|plc|sa|ag|bv|pvt|the|group|holdings"


def source_sql(path):
    """Return the DuckDB reader expression for a file path."""
    safe = path.replace("'", "''")
    if path.lower().endswith(".parquet"):
        return f"read_parquet('{safe}')"
    return f"read_csv_auto('{safe}')"


def norm_sql(col):
    """Return the SQL expression that normalises a name: lowercase, no punctuation or legal suffixes."""
    stripped = f"regexp_replace(lower({col}), '[^a-z0-9 ]', ' ', 'g')"
    no_suffix = f"regexp_replace({stripped}, '\\b({SUFFIXES})\\b', ' ', 'g')"
    return f"trim(regexp_replace({no_suffix}, '\\s+', ' ', 'g'))"


def load_denylist(path):
    """Return lowercase denylist names from a file (one per line, # comments)."""
    if not path:
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip().lower() for ln in lines if ln.strip() and not ln.startswith("#")]


def main():
    """Parse arguments and print the clustering preview."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="hosts parquet/csv")
    parser.add_argument("--column", required=True, help="organisation name column")
    parser.add_argument("--denylist", help="file of cloud/CDN/ISP names that are not companies")
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    col = f'"{args.column}"'
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT {col} AS raw, {norm_sql(col)} AS norm FROM {source_sql(args.path)}")
    total = con.execute("SELECT count(*) FROM t").fetchone()[0]
    empty = con.execute("SELECT count(*) FROM t WHERE raw IS NULL OR norm = ''").fetchone()[0]
    raw_n, norm_n = con.execute(
        "SELECT count(DISTINCT raw), count(DISTINCT norm) FROM t WHERE norm <> ''"
    ).fetchone()
    print(f"rows: {total:,} | unresolved (null/empty name): {empty:,} ({100 * empty / total:.1f}%)")
    print(f"distinct raw names: {raw_n:,} -> distinct normalised: {norm_n:,}")

    deny = load_denylist(args.denylist)
    if deny:
        hits = con.execute(
            "SELECT raw, count(*) c FROM t WHERE lower(trim(raw)) IN (SELECT unnest(?)) GROUP BY 1 ORDER BY 2 DESC LIMIT 10",
            [deny],
        ).fetchall()
        print(f"\ndenylist hits (rows that must NOT become companies): {hits or 'none'}")

    print(f"\nlargest clusters (norm | rows | raw variants):")
    rows = con.execute(
        f"SELECT norm, count(*) c, list(DISTINCT raw)[:4] FROM t WHERE norm <> '' "
        f"GROUP BY 1 ORDER BY c DESC LIMIT {int(args.top)}"
    ).fetchall()
    for norm, count, variants in rows:
        print(f"  {norm[:30]:<30} {count:>8,}  {variants}")

    print("\nclusters merging several different raw spellings (check these for false merges):")
    merged = con.execute(
        "SELECT norm, count(DISTINCT raw) v, list(DISTINCT raw)[:4] FROM t WHERE norm <> '' "
        f"GROUP BY 1 HAVING v > 1 ORDER BY v DESC LIMIT {int(args.top)}"
    ).fetchall()
    for norm, variants_n, variants in merged:
        print(f"  {norm[:30]:<30} {variants_n:>4} variants  {variants}")


if __name__ == "__main__":
    main()
