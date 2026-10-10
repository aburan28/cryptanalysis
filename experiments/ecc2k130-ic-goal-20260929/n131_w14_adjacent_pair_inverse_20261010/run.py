#!/usr/bin/env python3
"""Exact adjacent-rotation W14 output inverse and finite-geometry screen."""
import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
INVERSE = PARENT / "n131_w14_polynomial_pair_inverse_20261010"
sys.path.insert(0, str(INVERSE))
import oracle  # noqa: E402

SUPPORT = PARENT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
ROTATIONS = (0, 1, 26, 27, 52, 53, 78, 79, 104, 105)
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def square(field, value):
    return field.mul(value, value)


def rotate(field, value, distance):
    for _ in range(distance):
        value = square(field, value)
    return value


def rotate_point(field, point):
    if point is None:
        return None
    return square(field, point[0]), square(field, point[1])


def unique_bases(columns):
    pivots, _ = oracle.echelon(columns)
    chosen, seen = [], {}
    for value in columns:
        if oracle.solve(seen, value) is None:
            chosen.append(value)
            seen, _ = oracle.echelon(chosen)
    assert len(chosen) == len(pivots)
    return chosen


def inverse(candidate, joint, z):
    field = candidate.field
    if z in (0, 1):
        return [], {"status": "EXCEPTIONAL", "rank": None}
    z2 = square(field, z)
    az = z2 ^ z
    columns = [square(field, u) for u in joint["sum_u_basis"]] + [
        field.mul(az, p) for p in joint["product_basis"]]
    pivots, kernel = oracle.echelon(columns)
    if kernel:
        return [], {"status": "RANK_FALLBACK", "rank": len(pivots)}
    code = oracle.solve(pivots, z2)
    if code is None:
        return [], {"status": "SPAN_REJECT", "rank": len(pivots)}
    count = len(joint["sum_u_basis"])
    s = oracle.coordinate(joint["sum_w_basis"], code & ((1 << count)-1))
    p = oracle.coordinate(joint["product_basis"], code >> count)
    if s == 0:
        return [], {"status": "ZERO_SUM_REJECT", "rank": len(pivots)}
    seed_code = oracle.solve(joint["seed_pivots"], s)
    if seed_code is None:
        raise AssertionError("joint inverse returned a sum outside seed span")
    pairs = []
    for bits in oracle.affine_solutions(seed_code, joint["seed_kernel"]):
        a, b = bits & ((1 << oracle.D)-1), bits >> oracle.D
        if a not in candidate.valid or b not in candidate.valid:
            continue
        if candidate.columns[a] == candidate.columns[b]:
            continue
        w1 = oracle.coordinate(joint["left_w"], a)
        w2 = oracle.coordinate(joint["right_w"], b)
        if field.mul(w1, w2) == p:
            pairs.append((a, b))
    return sorted(set(pairs)), {"status": "PAIR" if pairs else "FIXED_SUM_REJECT",
                                "rank": len(pivots), "seed_sum": s,
                                "product": p, "seed_representations": 1 << len(joint["seed_kernel"])}


def raw_outputs(candidate, a, b):
    field = candidate.field
    left = candidate.point_options(a)
    right = [rotate_point(field, point) for point in candidate.point_options(b)]
    values = set()
    for p in left:
        for q in right:
            output = candidate.curve.add(p, q)
            z = candidate.phi_of(output)
            if z is not None:
                values.add(z)
    return sorted(values)


def build_joint(candidate):
    field = candidate.field
    left_w = candidate.basis_w
    right_w = [square(field, w) for w in left_w]
    seed_columns = left_w + right_w
    seed_pivots, seed_kernel = oracle.echelon(seed_columns)
    sum_w_basis = unique_bases(seed_columns)
    sum_u_basis = [oracle.half_trace(field, w) for w in sum_w_basis]
    assert all(square(field, u) ^ u == w for u, w in zip(sum_u_basis, sum_w_basis))
    product_basis = unique_bases([field.mul(a, b) for a in left_w for b in right_w])
    return {"left_w": left_w, "right_w": right_w,
            "seed_pivots": seed_pivots, "seed_kernel": seed_kernel,
            "sum_w_basis": sum_w_basis, "sum_u_basis": sum_u_basis,
            "product_basis": product_basis}


def factor_base_union(candidate):
    field = candidate.field
    source = [oracle.coordinate(candidate.basis_w, mask) for mask in candidate.valid]
    current = source
    seen = set()
    counts = []
    for rotation in range(max(ROTATIONS)+1):
        if rotation in ROTATIONS:
            before = len(seen)
            seen.update(current)
            counts.append({"rotation": rotation, "new_x": len(seen)-before})
        current = [square(field, value) for value in current]
    return len(seen), counts


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    sources = {"run": Path(__file__), "oracle": INVERSE / "oracle.py",
               "support": SUPPORT}
    assert protocol["status"] == "FROZEN_BEFORE_RUN"
    assert protocol["sha256"] == {name: sha(path) for name, path in sources.items()}
    assert not (HERE / "result.json").exists()
    started = time.monotonic_ns()
    candidate = oracle.PairOracle(oracle.load_support(SUPPORT))
    joint = build_joint(candidate)
    rng = random.Random(protocol["seed"])
    positives = []
    while len(positives) < protocol["positive_count"]:
        a, b = rng.sample(sorted(candidate.valid), 2)
        if candidate.columns[a] == candidate.columns[b]:
            continue
        values = raw_outputs(candidate, a, b)
        if values:
            positives.append({"masks": [a, b], "z": values[rng.randrange(len(values))]})
    controls = [rng.getrandbits(oracle.N) for _ in positives]
    records = []
    for kind, items in (("positive", positives), ("uniform_field", controls)):
        for index, item in enumerate(items):
            z = item["z"] if kind == "positive" else item
            t0 = time.monotonic_ns()
            pairs, detail = inverse(candidate, joint, z)
            query_ns = time.monotonic_ns()-t0
            if kind == "positive" and tuple(item["masks"]) not in pairs:
                raise AssertionError("constructed pair lost")
            for a, b in pairs:
                if z not in raw_outputs(candidate, a, b):
                    raise AssertionError("inverse pair failed raw group replay")
            records.append({"kind": kind, "index": index, "z": z,
                            "masks": item["masks"] if kind == "positive" else None,
                            "pairs": pairs, "detail": detail, "query_ns": query_ns})
    union_x, window_counts = factor_base_union(candidate)
    full_rank = len(joint["sum_w_basis"])+len(joint["product_basis"])
    result = {"status": "COMPLETE_EXACT_STAGE", "candidate_id": None,
              "curve_id": protocol["curve_id"], "proposal_id": protocol["proposal_id"],
              "source_sha256": protocol["sha256"], "protocol_sha256": sha(protocol_path),
              "rotation_policy": list(ROTATIONS), "source_masks": len(candidate.valid),
              "folded_columns_K": len(set(candidate.columns.values())),
              "pair_seed_rank": len(joint["sum_w_basis"]),
              "pair_seed_kernel_dim": len(joint["seed_kernel"]),
              "pair_product_rank": len(joint["product_basis"]),
              "joint_upper_bound": full_rank,
              "joint_ranks": [row["detail"]["rank"] for row in records],
              "actual_base_points_B": 2*union_x,
              "unique_x": union_x, "window_new_x": window_counts,
              "records": records, "wall_ns": time.monotonic_ns()-started,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                  (1 if sys.platform == "darwin" else 1024)}
    if result["wall_ns"] > protocol["wall_cap_seconds"]*1_000_000_000:
        result["status"] = "CENSORED_TIME"
    if result["peak_rss_bytes"] > protocol["rss_cap_bytes"]:
        result["status"] = "CENSORED_MEMORY"
    (HERE / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({key: result[key] for key in ("status", "pair_seed_rank",
          "pair_product_rank", "joint_upper_bound", "actual_base_points_B",
          "wall_ns", "peak_rss_bytes")}))


if __name__ == "__main__":
    main()
