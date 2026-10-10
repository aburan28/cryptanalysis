#!/usr/bin/env python3
"""Exact N41 Frobenius-diagonal atom geometry and reciprocal S3 audit."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SNAPSHOT = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
ARITH = BASE / "n41_two_free_pair_occupancy_20261009/arithmetic_snapshot.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location("independent_arithmetic", ARITH)
arith = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arith)
f = arith.Field(41, [0, 3])
curve = arith.Curve(f, 0)


def frob(p, k=1):
    if p is None:
        return None
    x, y = p
    for _ in range(k):
        x, y = f.mul(x, x), f.mul(y, y)
    return x, y


def reciprocal_s3(a, b, c):
    ab = f.mul(a, b)
    abc = f.mul(ab, c)
    abc2 = f.mul(abc, abc)
    return f.mul(a ^ b ^ c, a ^ b ^ c) ^ abc ^ abc2


def main():
    input_data = json.loads(SNAPSHOT.read_text())
    n41 = input_data["n41"]
    source_rows = n41["point_rows_by_unique_rotation"]["0"]
    basis_w = n41["window_basis_w"][0]
    basis_u = n41["window_basis_halftrace"][0]
    atoms = []
    source_atoms = {}
    for x, y, column, mask, rotation, sign in source_rows:
        assert rotation == 0
        p = (x, y)
        assert curve.on_curve(p) and curve.mul(n41["subgroup_order"], p) is None
        d = curve.add(p, frob(p))
        assert d is not None and curve.on_curve(d)
        atoms.append({"mask": mask, "sign": sign, "source_column": column,
                      "point": list(d)})
        source_atoms[(mask, sign)] = d
    assert len(atoms) == 64 and len({tuple(a["point"]) for a in atoms}) == 64

    raw_audit = []
    for mask in sorted({a["mask"] for a in atoms}):
        w = u = 0
        for bit in range(6):
            if mask >> bit & 1:
                w ^= basis_w[bit]
                u ^= basis_u[bit]
        assert w != 0 and f.mul(u, u) ^ u == w
        raw_x = 1 ^ f.inv(u)
        raw_points = arith.points_with_x(curve, raw_x)
        assert len(raw_points) == 2
        found = False
        expected = {(x, y): sign for x, y, _, m, _, sign in source_rows if m == mask}
        for raw in raw_points:
            subgroup = curve.mul(4, raw)
            if subgroup not in expected:
                continue
            d_raw = curve.add(raw, frob(raw))
            assert d_raw is not None and d_raw[0] == f.inv(w)
            assert curve.mul(4, d_raw) == source_atoms[(mask, expected[subgroup])]
            raw_audit.append({"mask": mask, "w": w, "u": u,
                              "raw_pair_point": list(d_raw),
                              "subgroup_atom": list(curve.mul(4, d_raw))})
            found = True
            break
        assert found

    rotations = [0, 5, 10, 15, 20, 25, 30, 35]
    slots = []
    for k in rotations:
        slots.append([{**a, "rotation": k, "point": list(frob(tuple(a["point"]), k))}
                      for a in atoms])
    all_points = {tuple(a["point"]) for slot in slots for a in slot}
    orbit_reps = set()
    for p in all_points:
        orbit_reps.add(min(min(frob(p, j), curve.neg(frob(p, j))) for j in range(41)))
    intersections = {f"{rotations[i]}_{rotations[j]}": len(
        {tuple(a["point"]) for a in slots[i]} &
        {tuple(a["point"]) for a in slots[j]})
        for i in range(8) for j in range(i+1, 8)}

    # For x_i = 1/a_i, clearing the three denominators in S3 gives
    # (a+b+c)^2 + abc + (abc)^2 = 0.
    s3_checks = 0
    for a in raw_audit[:16]:
        for b in raw_audit[16:32]:
            t = curve.add(tuple(a["raw_pair_point"]), tuple(b["raw_pair_point"]))
            if t is None or t[0] == 0:
                continue
            x1, x2, x3 = a["raw_pair_point"][0], b["raw_pair_point"][0], t[0]
            aa, bb, cc = f.inv(x1), f.inv(x2), f.inv(x3)
            assert reciprocal_s3(aa, bb, cc) == 0
            pair_products = f.mul(x1, x2) ^ f.mul(x3, x1 ^ x2)
            direct = f.mul(pair_products, pair_products) ^ f.mul(x3, f.mul(x1, x2)) ^ 1
            assert direct == 0
            s3_checks += 1

    result = {"status": "complete", "source_sha256": sha(Path(__file__)),
              "geometry_sha256": sha(SNAPSHOT), "arithmetic_sha256": sha(ARITH),
              "curve_id": n41["curve_id"], "candidate_id": None,
              "source_masks": 32, "raw_reciprocal_audits": len(raw_audit),
              "raw_audit": raw_audit, "slot_rotations": rotations,
              "slot_size": 64, "actual_usable_points_B": len(all_points),
              "signed_frobenius_columns_K": len(orbit_reps),
              "pairwise_slot_intersections": intersections,
              "reciprocal_s3_algebra_checks": s3_checks,
              "public_target": n41["public_target_q"],
              "subgroup_order": n41["subgroup_order"],
              "slots": slots}
    (HERE / "screen.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("slots", "raw_audit", "pairwise_slot_intersections")}, indent=2))


if __name__ == "__main__":
    main()
