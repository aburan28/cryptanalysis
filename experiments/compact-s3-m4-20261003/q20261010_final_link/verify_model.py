#!/usr/bin/env python3
"""Replay all three S3 links of one Q1432 model independently of CaDiCaL."""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
sys.path.insert(0, str(STAGE))
from chain_s3 import evaluate_s3, field  # noqa: E402


def verify(meta_path, log_path):
    meta = json.loads(Path(meta_path).read_text())
    lines = Path(log_path).read_text().splitlines()
    result = json.loads(lines[0])
    assert result["status"] == 10
    n = meta["degree"]
    literals = [int(item) for item in lines[1].split()[1:-1]]
    rows = [*meta["leaves"], *meta["mids"]]
    assert len(literals) == 6 * n
    values = []
    for index, row in enumerate(rows):
        assigned = literals[index * n:(index + 1) * n]
        assert all(abs(lit) == var for lit, var in zip(assigned, row))
        values.append(sum((lit > 0) << bit for bit, lit in enumerate(assigned)))
    onb = field.Onb(n)
    a = [onb.fromCoords(value) for value in values]
    for x, y, z in ((0, 1, 4), (2, 3, 5)):
        assert evaluate_s3(onb, a[x], a[y], a[z]) == 0
    final_targets = [value for value in meta["raw_target_x_coordinates"]
                     if evaluate_s3(onb, a[4], a[5], onb.fromCoords(value)) == 0]
    assert final_targets
    if meta["mode"] == "control":
        assert values[:4] == meta["witness_leaf_x"]
    return {"status": "verified_s3", "mode": meta["mode"],
            "degree": n, "leaf_x_coordinates": values[:4],
            "middle_x_coordinates": values[4:],
            "compatible_target_x_coordinates": final_targets}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta", type=Path, required=True)
    parser.add_argument("--solver-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.meta, args.solver_output), sort_keys=True))
