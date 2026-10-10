#!/usr/bin/env python3
"""Freeze the four-atom positive control and independent public N41 point."""

import hashlib
import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
PUBLIC = run.BASE / "n41_adjacent_pairpair/public_target.json"
PAIR_ORACLE = run.BASE.parent / "koblitz-polynomial-w-pair-20260925/pair_oracle.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (HERE / "input.json").exists()
    assert not (HERE / "protocol.json").exists()
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    public = json.loads(PUBLIC.read_text())
    f, curve, geometry, rotations, bases, atom_states = run.source_context()
    assert public["curve_id"] == geometry["curve_id"]
    assert public["target_q"] == geometry["public_target_q"]
    positive_witness = [[5, 0], [2, 1], [16, 0], [49, 1]]
    columns = [atom_states[side][tuple(row)]["column"]
               for side, two in enumerate((positive_witness[:2], positive_witness[2:]))
               for row in two]
    assert len(set(columns)) == 4
    raw_sum = None
    atom_points = []
    for side, two in enumerate((positive_witness[:2], positive_witness[2:])):
        for row in two:
            point = atom_states[side][tuple(row)]["point"]
            atom_points.append(list(point))
            raw_sum = curve.add(raw_sum, point)
    assert raw_sum is not None and raw_sum[0] != 0
    positive = curve.mul(4, raw_sum)
    assert positive is not None and curve.mul(run.R, positive) is None
    pair_left = curve.add(tuple(atom_points[0]), tuple(atom_points[1]))
    pair_right = curve.add(tuple(atom_points[2]), tuple(atom_points[3]))
    assert pair_left is not None and pair_left[0] != 0
    assert pair_right is not None and pair_right[0] != 0
    assert curve.add(pair_left, pair_right) == raw_sum
    inputs = {"kind": "n41_diagonal_four_atom_double_norm",
              "candidate_id": None, "curve_id": geometry["curve_id"],
              "field_degree": 41, "field_modulus_low_terms": [0, 3],
              "curve": "y^2+xy=x^3+1", "subgroup_order": run.R,
              "rotations": rotations,
              "positive_witness": positive_witness,
              "positive_atom_points": atom_points,
              "positive_columns": columns,
              "positive_pair_points": [list(pair_left), list(pair_right)],
              "positive_raw_sum": list(raw_sum),
              "positive_subgroup_target": list(positive),
              "positive_input_law": "deterministic four-atom correctness control",
              "public_subgroup_target": public["target_q"],
              "public_input_law": public["input_law"],
              "source_masks_per_rotation": 32,
              "signed_atom_states_per_rotation": 64,
              "actual_subgroup_base_points_B": 128,
              "folded_columns_K": 26}
    run.save(HERE / "input.json", inputs)
    sources = {"run": HERE / "run.py", "freeze": Path(__file__),
               "input": HERE / "input.json", "geometry": run.GEOMETRY,
               "base": Path(run.old.__file__), "pair_oracle": PAIR_ORACLE,
               "runtime": HERE / "sage_runtime_info.json", "public": PUBLIC}
    protocol = {"status": "FROZEN_BEFORE_RUN", "candidate_id": None,
                "curve_id": geometry["curve_id"],
                "cases": ["positive", "public"],
                "case_wall_cap_seconds": 300, "rss_cap_bytes": 4*1024**3,
                "workers": 1,
                "algorithm": "reciprocal pair-bucket polynomials, target-dependent quadratic resultants, double-sided polynomial GCD",
                "source_sha256": {name: sha(path) for name, path in sources.items()}}
    run.save(HERE / "protocol.json", protocol)
    print(json.dumps({"status": protocol["status"],
                      "positive_subgroup_target": list(positive),
                      "positive_raw_sum": list(raw_sum),
                      "public_subgroup_target": public["target_q"],
                      "input_sha256": sha(HERE / "input.json")}, indent=2))


if __name__ == "__main__":
    main()
