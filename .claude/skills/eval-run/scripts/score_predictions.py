"""Score predictions against hand labels: precision, recall, F1, confusion matrix, flips vs a baseline."""
import argparse
import json
from pathlib import Path

MIN_RECOMMENDED = 20


def read_jsonl(path):
    """Return the records of a JSONL file as a list of dicts."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def to_map(records, id_key, value_key):
    """Map id -> value, skipping records whose value is missing or null."""
    return {r[id_key]: r[value_key] for r in records if r.get(value_key) is not None}


def confusion(labels, preds, positive):
    """Return (tp, fp, fn, tn, missing) counts over labelled ids."""
    tp = fp = fn = tn = missing = 0
    for ident, truth in labels.items():
        if ident not in preds:
            missing += 1
            continue
        is_pos, said_pos = truth == positive, preds[ident] == positive
        tp += is_pos and said_pos
        fp += (not is_pos) and said_pos
        fn += is_pos and (not said_pos)
        tn += (not is_pos) and (not said_pos)
    return tp, fp, fn, tn, missing


def metrics(tp, fp, fn):
    """Return precision, recall and F1, treating empty denominators as 0."""
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def print_scores(name, labels, preds, positive):
    """Print the metrics block for one set of predictions and return the numbers."""
    tp, fp, fn, tn, missing = confusion(labels, preds, positive)
    p, r, f1 = metrics(tp, fp, fn)
    print(f"{name}: precision={p:.2f} recall={r:.2f} f1={f1:.2f}  (n={len(labels) - missing}, missing={missing})")
    print(f"  confusion: TP={tp} FP={fp} FN={fn} TN={tn}")
    return p, r, f1


def print_flips(labels, base, cand):
    """List examples whose prediction changed between baseline and candidate."""
    fixed, regressed, other = [], [], []
    for ident, truth in labels.items():
        if ident not in base or ident not in cand or base[ident] == cand[ident]:
            continue
        if cand[ident] == truth:
            fixed.append(ident)
        elif base[ident] == truth:
            regressed.append(ident)
        else:
            other.append(ident)
    print(f"\nflips vs baseline: fixed={len(fixed)} regressed={len(regressed)} still-wrong={len(other)}")
    for title, ids in (("fixed", fixed), ("regressed", regressed)):
        if ids:
            print(f"  {title}: {', '.join(ids)}")


def main():
    """Parse arguments, score the candidate (and baseline), print the comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="evals/labeled.jsonl")
    parser.add_argument("--pred", required=True, help="candidate predictions JSONL")
    parser.add_argument("--baseline", help="baseline predictions JSONL")
    parser.add_argument("--positive", default="contact", help="the positive class")
    parser.add_argument("--id-key", default="account_id")
    parser.add_argument("--label-key", default="label")
    parser.add_argument("--pred-key", default="decision")
    args = parser.parse_args()

    labels = to_map(read_jsonl(args.labels), args.id_key, args.label_key)
    if len(labels) < MIN_RECOMMENDED:
        print(f"WARNING: only {len(labels)} labelled examples (aim for {MIN_RECOMMENDED}-30); "
              "treat these numbers as indicative.\n")
    cand = to_map(read_jsonl(args.pred), args.id_key, args.pred_key)
    print_scores("candidate", labels, cand, args.positive)
    if args.baseline:
        base = to_map(read_jsonl(args.baseline), args.id_key, args.pred_key)
        print_scores("baseline ", labels, base, args.positive)
        print_flips(labels, base, cand)


if __name__ == "__main__":
    main()
