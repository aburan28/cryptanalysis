#!/usr/bin/env python3
"""Measure whether training-hot rotation seeds remain hot on held-out scalars."""

from pathlib import Path
import json
import math
import sys


def corr(a, b):
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def main(training: Path, evaluation: Path, output: Path):
    train = json.loads(training.read_text())
    test = json.loads(evaluation.read_text())
    assert train["count"] == 20000 and test["count"] == 12288
    a, b = train["hist"], test["hist"]
    assert len(a) == len(b) == 15
    assert all(len(x) == len(y) for x, y in zip(a, b))
    per_row = []
    for row, (x, y) in enumerate(zip(a, b)):
        assert sum(x) in (19999, 20000)
        assert sum(y) in (12287, 12288)
        order = sorted(range(len(x)), key=lambda i: (-x[i], i))
        ks = (100, 1000, 5000, 10000)
        per_row.append({
            "row": row,
            "seed_count": len(x),
            "train_total": sum(x),
            "evaluation_total": sum(y),
            "pearson_train_evaluation": corr(x, y),
            "top_by_training": {
                str(k): {
                    "train_hit_fraction": sum(x[i] for i in order[:k]) / sum(x),
                    "heldout_hit_fraction": sum(y[i] for i in order[:k]) / sum(y),
                    "uniform_fraction": k / len(x),
                } for k in ks
            },
        })
    result = {"schema": 1, "training_count": train["count"],
              "evaluation_count": test["count"], "rows": per_row}
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("mean_train_eval_correlation", sum(r["pearson_train_evaluation"] for r in per_row[:14]) / 14)
    for k in (100, 1000, 5000, 10000):
        print("top", k, "train_hit", sum(r["top_by_training"][str(k)]["train_hit_fraction"] for r in per_row[:14]) / 14,
              "heldout_hit", sum(r["top_by_training"][str(k)]["heldout_hit_fraction"] for r in per_row[:14]) / 14,
              "uniform", k / 22756)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
