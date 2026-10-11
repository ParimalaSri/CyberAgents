"""Stage N: read the previous layer, write this layer (replace this line with what the stage does)."""
import argparse
import subprocess
import sys

import duckdb

INPUT_PATH = "data/silver/hosts.parquet"  # previous layer's output
OUTPUT_PATH = "data/silver/companies.parquet"  # this stage's output
SAMPLE_ROWS = 100_000  # dev default; use --full for the whole dataset
REPORT_SCRIPT = ".claude/skills/pipeline-stage-build/scripts/stage_report.py"


def transform(con, sample_rows):
    """Build this stage's table in DuckDB from the previous layer (all logic is deterministic SQL)."""
    limit = f"USING SAMPLE reservoir({sample_rows} ROWS) REPEATABLE (42)" if sample_rows else ""
    con.execute(
        f"""
        CREATE TABLE out AS
        SELECT *
        FROM read_parquet('{INPUT_PATH}') {limit}
        """
    )


def write_output(con):
    """Write the stage table to its parquet output path."""
    con.execute(f"COPY out TO '{OUTPUT_PATH}' (FORMAT PARQUET)")


def print_report():
    """Run the shared stage report so row counts, null rates and samples are always shown."""
    subprocess.run(
        [sys.executable, REPORT_SCRIPT, OUTPUT_PATH, "--prev", INPUT_PATH], check=True
    )


def main():
    """Run the stage end to end: transform, write, report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="run on the full dataset")
    args = parser.parse_args()

    con = duckdb.connect()
    transform(con, 0 if args.full else SAMPLE_ROWS)
    write_output(con)
    print_report()


if __name__ == "__main__":
    main()
