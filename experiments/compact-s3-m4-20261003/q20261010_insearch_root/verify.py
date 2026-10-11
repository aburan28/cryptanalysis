#!/usr/bin/env python3
"""Independently check the observed coordinates of a CaDiCaL model."""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
sys.path.insert(0, str(STAGE))
from chain_s3 import evaluate_s3, field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--solver-output", type=Path, required=True)
    args = parser.parse_args()
    meta = json.loads(args.meta.read_text())
    n = meta["degree"]
    output = args.solver_output.read_text().splitlines()
    result = json.loads(output[0])
    assert result["status"] == 10
    literals = [int(item) for item in output[1].split()[1:-1]]
    rows = [*meta["leaves"], *meta["mids"]]
    assert len(literals) == n * 6
    values = []
    for row, assignment in zip(rows, (literals[i:i + n]
                                  for i in range(0, len(literals), n))):
        assert all(abs(lit) == var for lit, var in zip(assignment, row))
        values.append(sum((lit > 0) << bit for bit, lit in enumerate(assignment)))
    onb = field.Onb(n)
    for pair in range(2):
        a, b, c = (onb.fromCoords(values[2 * pair]),
                   onb.fromCoords(values[2 * pair + 1]),
                   onb.fromCoords(values[4 + pair]))
        assert evaluate_s3(onb, a, b, c) == 0
        assert c in s3_roots(onb, a, b)
    if meta["mode"] == "control":
        assert values[:4] == meta["witness_leaf_x"]
    print(json.dumps({"status": "verified", "mode": meta["mode"],
                      "leaf_x_coordinates": values[:4],
                      "middle_x_coordinates": values[4:]}))


if __name__ == "__main__":
    main()
