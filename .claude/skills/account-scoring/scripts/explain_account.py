"""Print everything known about one account: its score row and its raw signals."""
import argparse

import duckdb


def source_sql(path):
    """Return the DuckDB reader expression for a file path."""
    safe = path.replace("'", "''")
    if path.lower().endswith(".parquet"):
        return f"read_parquet('{safe}')"
    return f"read_csv_auto('{safe}')"


def show(con, title, path, key, value):
    """Print the matching row of one file as name: value lines."""
    cur = con.execute(f'SELECT * FROM {source_sql(path)} WHERE "{key}" = ?', [value])
    names = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print(f"\n== {title} ({path})")
    if not rows:
        print("  no matching row")
    for row in rows:
        for name, val in zip(names, row):
            print(f"  {name}: {val}")


def main():
    """Parse arguments and print the account from the accounts and signals files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("account_id")
    parser.add_argument("--key", default="account_id", help="id column name")
    parser.add_argument("--accounts", default="data/gold/accounts.parquet")
    parser.add_argument("--signals", default="data/gold/signals.parquet")
    args = parser.parse_args()

    con = duckdb.connect()
    show(con, "account", args.accounts, args.key, args.account_id)
    show(con, "signals", args.signals, args.key, args.account_id)


if __name__ == "__main__":
    main()
