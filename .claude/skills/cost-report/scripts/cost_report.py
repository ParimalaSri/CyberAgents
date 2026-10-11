"""Summarise LLM spend from a trace JSONL file and project production cost with a recommended ceiling."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def read_traces(path):
    """Return trace records from a JSONL file (empty list if the file does not exist)."""
    file = Path(path)
    if not file.exists():
        return []
    lines = file.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def percentile(values, pct):
    """Return the pct-th percentile (nearest rank) of a list of numbers."""
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * len(ordered)) - 1))
    return ordered[index]


def summarise(records):
    """Group records by (model, prompt_version) and return one stats dict per group."""
    groups = defaultdict(list)
    for rec in records:
        groups[(rec.get("model", "?"), rec.get("prompt_version", "?"))].append(rec)
    rows = []
    for (model, version), recs in sorted(groups.items()):
        n = len(recs)
        lat = [r.get("latency_ms", 0) for r in recs]
        rows.append({
            "model": model, "prompt_version": version, "calls": n,
            "avg_in": sum(r.get("input_tokens", 0) for r in recs) / n,
            "avg_out": sum(r.get("output_tokens", 0) for r in recs) / n,
            "cost": sum(r.get("cost_usd", 0) for r in recs),
            "p50_ms": percentile(lat, 50), "p95_ms": percentile(lat, 95),
        })
    return rows


def render_actuals(rows):
    """Return the actual-spend table as markdown lines."""
    lines = ["## Actual spend", "", "| model | prompt | calls | avg in | avg out | cost USD | p50 ms | p95 ms |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['prompt_version']} | {r['calls']} | {r['avg_in']:.0f} | "
                     f"{r['avg_out']:.0f} | {r['cost']:.4f} | {r['p50_ms']} | {r['p95_ms']} |")
    lines.append(f"\nTotal: {sum(r['cost'] for r in rows):.4f} USD over {sum(r['calls'] for r in rows)} calls")
    return lines


def render_projection(args, rows):
    """Return the projection as markdown lines, showing every term of the math."""
    avg_in = args.in_tokens or (sum(r["avg_in"] * r["calls"] for r in rows) / max(1, sum(r["calls"] for r in rows)))
    avg_out = args.out_tokens or (sum(r["avg_out"] * r["calls"] for r in rows) / max(1, sum(r["calls"] for r in rows)))
    per_call = (avg_in * args.price_in + avg_out * args.price_out) / 1_000_000
    per_run = per_call * args.accounts
    monthly = per_run * args.runs_per_month
    return [
        "", "## Projection", "",
        f"- per call = ({avg_in:.0f} in x ${args.price_in}/MTok + {avg_out:.0f} out x ${args.price_out}/MTok) / 1e6 = ${per_call:.5f}",
        f"- per run = {args.accounts:,} accounts x ${per_call:.5f} = ${per_run:.2f}",
        f"- per month = {args.runs_per_month} runs x ${per_run:.2f} = ${monthly:.2f}",
        f"- recommended per-run ceiling = {args.ceiling_factor}x per run = ${per_run * args.ceiling_factor:.2f} "
        "(abort in llm/client.py if exceeded)",
    ]


def main():
    """Parse arguments, print the report, optionally save it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", default="traces/dev.jsonl")
    parser.add_argument("--accounts", type=int, help="accounts per run to project (e.g. review-band size)")
    parser.add_argument("--runs-per-month", type=int, default=4)
    parser.add_argument("--in-tokens", type=float, help="override avg input tokens per call")
    parser.add_argument("--out-tokens", type=float, help="override avg output tokens per call")
    parser.add_argument("--price-in", type=float, help="USD per million input tokens (look up current pricing)")
    parser.add_argument("--price-out", type=float, help="USD per million output tokens")
    parser.add_argument("--ceiling-factor", type=float, default=2.0)
    parser.add_argument("--out", help="save the report to this markdown file")
    args = parser.parse_args()

    rows = summarise(read_traces(args.traces))
    lines = [f"# Cost report ({args.traces})", ""]
    lines += render_actuals(rows) if rows else ["No trace records found: the actuals table is empty."]
    if args.accounts:
        if args.price_in is None or args.price_out is None:
            lines.append("\nProjection skipped: pass --price-in and --price-out (current USD per million tokens).")
        elif rows or (args.in_tokens and args.out_tokens):
            lines += render_projection(args, rows)
        else:
            lines.append("\nProjection needs trace data or --in-tokens/--out-tokens.")
    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
