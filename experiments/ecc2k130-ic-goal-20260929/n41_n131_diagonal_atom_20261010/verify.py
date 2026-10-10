#!/usr/bin/env python3
"""Independent Python replay of the native diagonal-atom relation."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ARITH = BASE / "n41_two_free_pair_occupancy_20261009/arithmetic_snapshot.py"
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    for name, path in [("join", HERE / "join.cpp"),
                       ("included_arithmetic", HERE / "../../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"),
                       ("input", HERE / "input.txt"), ("screen", HERE / "screen.json")]:
        assert sha(path) == protocol["source_sha256"][name]
    spec = importlib.util.spec_from_file_location("independent_arithmetic", ARITH)
    arithmetic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arithmetic)
    f = arithmetic.Field(41, [0, 3])
    curve = arithmetic.Curve(f, 0)
    result = json.loads((HERE / "join_result.json").read_text())
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    assert result["status"] == "VERIFIED_EIGHT_POINT_ROW"
    q = tuple(geometry["public_target_q"])
    r = geometry["subgroup_order"]
    assert result["target"] == list(q) and curve.on_curve(q)
    assert curve.mul(r, q) is None

    def frob(p, n):
        x, y = p
        for _ in range(n):
            x, y = f.mul(x, x), f.mul(y, y)
        return x, y

    sqrt_minus_7 = pow((-7) % r, (r + 1) // 4, r)
    assert sqrt_minus_7 * sqrt_minus_7 % r == (-7) % r
    lambdas = [((-1 + s * sqrt_minus_7) * pow(2, -1, r)) % r for s in [1, -1]]
    eigen = next(lam for lam in lambdas if curve.mul(lam, q) == frob(q, 1))
    alpha = (1 + eigen) % r
    assert alpha != 0
    inverse_alpha = pow(alpha, -1, r)

    rows = geometry["point_rows_by_unique_rotation"]["0"]
    by_mask_sign = {(row[3], row[5]): tuple(row[:2]) for row in rows}
    witness = result["verified_relation"]
    assert len(set(witness["columns"])) == 8
    assert len(witness["points"]) == 8
    subgroup_sum = raw_base_sum = None
    atom_replays = []
    rotations = [0, 5, 10, 15, 20, 25, 30, 35]
    for i, rotation in enumerate(rotations):
        mask, sign = witness["seed_masks"][i], witness["curve_sign_indices"][i]
        source = by_mask_sign[(mask, sign)]
        source_rotated = frob(source, rotation)
        transformed = curve.add(source_rotated, frob(source_rotated, 1))
        assert transformed == tuple(witness["points"][i])
        assert curve.on_curve(transformed) and curve.mul(r, transformed) is None
        assert curve.mul(alpha, source_rotated) == transformed
        subgroup_sum = curve.add(subgroup_sum, transformed)
        raw_base_sum = curve.add(raw_base_sum, source_rotated)
        atom_replays.append({"rotation": rotation, "mask": mask, "sign": sign,
                             "column": witness["columns"][i],
                             "source_point": list(source_rotated),
                             "atom_point": list(transformed)})
    assert subgroup_sum == q
    assert curve.mul(inverse_alpha, q) == raw_base_sum
    assert curve.mul(alpha, raw_base_sum) == q
    out = {"status": "PASS", "candidate_id": None,
           "source_sha256": sha(Path(__file__)), "arithmetic_sha256": sha(ARITH),
           "geometry_sha256": sha(GEOMETRY), "join_receipt_sha256": sha(HERE / "join_result.json"),
           "public_target": list(q), "subgroup_order": r,
           "frobenius_eigenvalue_mod_r": eigen, "alpha_mod_r": alpha,
           "source_target": list(raw_base_sum), "verified_atoms": atom_replays,
           "distinct_folded_columns": len(set(witness["columns"]))}
    (HERE / "verification.json").write_text(json.dumps(out, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "verified_atoms"}, indent=2))


if __name__ == "__main__":
    main()
