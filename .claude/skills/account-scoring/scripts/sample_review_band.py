"""Sample accounts from a band into a candidates JSONL file for the user to label (never labels them)."""
import argparse
import json
import sys

import duckdb

PROTECTED_OUTPUT = "labeled.jsonl"


def source_sql(path):
    """Return the DuckDB reader expression for a file path."""
    safe = path.replace("'", "''")
    if path.lower().endswith(".parquet"):
        return f"read_parquet('{safe}')"
    return f"read_csv_auto('{safe}')"


def main():
    """Draw a seeded random sample from one band and write it with empty label fields."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accounts", help="data/gold/accounts.parquet")
    parser.add_argument("--band", default="review")
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="evals/candidates.jsonl")
    args = parser.parse_args()

    if args.out.replace("\\", "/").endswith(PROTECTED_OUTPUT):
        sys.exit("Refusing to write to labeled.jsonl: labels are written by the user only.")

    con = duckdb.connect()
    cur = con.execute(
        f"SELECT * FROM (SELECT * FROM {source_sql(args.accounts)} WHERE band = ?) "
        f"USING SAMPLE reservoir({int(args.n)} ROWS) REPEATABLE ({int(args.seed)})",
        [args.band],
    )
    names = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(args.out, "w", encoding="utf-8") as handle:
        for row in rows:
            record = dict(zip(names, row))
            record.update({"label": None, "label_notes": "", "suggested_label": None})
            handle.write(json.dumps(record, default=str) + "\n")
    print(f"wrote {len(rows)} '{args.band}' candidates to {args.out}")
    print("Labels are the user's: Claude may fill suggested_label with reasoning, never label.")


if __name__ == "__main__":
    main()
