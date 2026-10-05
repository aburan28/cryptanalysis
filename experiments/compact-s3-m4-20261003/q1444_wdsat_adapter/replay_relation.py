#!/usr/bin/env python3
"""Replay a WDSat model against the archived curve, base, and public point.

Launch only with /Volumes/SSD990/cryptanalysis/sage -python.
"""

import argparse
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
from q1439_fixed_leaf import experiment as parent  # noqa: E402
from q1440_witness_anchor import experiment as anchored  # noqa: E402


def replay(cell, model_path):
    n = int(cell[1:3])
    bits = model_path.read_text(encoding="ascii").strip()
    if cell.endswith("choice_pinned"):
        prepared = anchored.inputs(n)
        formula, leaves, mid, selector = anchored.build(prepared, "choice_pinned")
    elif cell.endswith("ordinary"):
        prepared = parent.prepare(n, "ordinary")
        formula, leaves, mid, selector = parent.build(prepared)
    else:
        raise ValueError(cell)
    assert len(bits) >= formula.variables
    assert set(bits) <= {"0", "1"}
    model = {j: char == "1" for j, char in enumerate(bits[:formula.variables], 1)}
    return parent.check_relation(prepared, formula, leaves, mid, selector, model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.cell, args.model), sort_keys=True))
