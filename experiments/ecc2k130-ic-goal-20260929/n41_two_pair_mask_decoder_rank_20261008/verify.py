#!/usr/bin/env python3
"""Independent low-pivot and monomial audit of the pair-sum equation."""

from __future__ import annotations

import hashlib
import json
import math
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from run_n41_disjoint_s5_sat import Curve, Field  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_vector(mask: int, variable_count: int) -> int:
    answer = 1
    for i in range(variable_count):
        if mask & (1 << i):
            answer |= 1 << (i + 1)
    position = variable_count + 1
    for i in range(variable_count):
        if mask & (1 << i):
            for j in range(i + 1, variable_count):
                if mask & (1 << j):
                    answer |= 1 << position
                position += 1
        else:
            position += variable_count - i - 1
    assert position == 1 + variable_count + variable_count * (variable_count - 1) // 2
    return answer


def insert_low(basis: dict[int, int], value: int) -> bool:
    while value:
        low = value & -value
        pivot = low.bit_length() - 1
        previous = basis.get(pivot)
        if previous is None:
            basis[pivot] = value
            return True
        value ^= previous
    return False


def rank(values) -> tuple[int, dict[int, int]]:
    basis: dict[int, int] = {}
    for value in values:
        insert_low(basis, value)
    return len(basis), basis


def interval(successes: int, trials: int) -> list[float]:
    z = 1.959963984540054
    p = successes / trials
    den = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / den
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / den
    return [center - radius, center + radius]


def main() -> None:
    output = HERE / "verification.json"
    if output.exists():
        raise FileExistsError("preserve first audit")
    start = time.monotonic_ns()
    protocol = json.loads((HERE / "protocol_verify.json").read_text())
    names = ("initial_rows", "holdout_rows", "curve_control_rows", "relation",
             "analysis_result", "exhaustive_result", "exhaustive_binary",
             "geometry", "curve_arithmetic")
    paths = {name: (HERE / protocol[name]).resolve() for name in names}
    for name, path in paths.items():
        assert sha(path) == protocol[f"{name}_sha256"], name
    initial = json.loads(paths["initial_rows"].read_text())["rows"]
    holdout = json.loads(paths["holdout_rows"].read_text())["rows"]
    control = json.loads(paths["curve_control_rows"].read_text())["points"]
    relation = json.loads(paths["relation"].read_text())
    analysis = json.loads(paths["analysis_result"].read_text())
    exhaustive = json.loads(paths["exhaustive_result"].read_text())
    assert len(initial) == len(holdout) == len(control) == 8192
    assert exhaustive["status"] == "COMPLETE_SUPPORT_EQUATION"
    assert exhaustive["checked_combinations"] == 1956 * 1956
    assert exhaustive["violations"] == exhaustive["identity_combinations"] == exhaustive["odd_x_combinations"] == 0
    assert relation["feature_count"] == 3322
    eq = sum(1 << i for i in relation["term_indices"])
    assert len(relation["term_indices"]) == relation["term_count"]
    assert relation["term_indices"] == sorted(set(relation["term_indices"]))
    assert eq.bit_length() <= 3322

    def coordinate_mask(point):
        x, y = point
        assert 0 <= x < (1 << 41) and x % 2 == 0
        assert 0 <= y < (1 << 41)
        return (x >> 1) | (y << 40)

    pair_points = [row["sum_point"] for row in initial + holdout]
    pair_vectors = [feature_vector(coordinate_mask(point), 81) for point in pair_points]
    control_vectors = [feature_vector(coordinate_mask(point), 81) for point in control]
    pair_nonzero = sum(bin(eq & vector).count("1") & 1 for vector in pair_vectors)
    control_nonzero = sum(bin(eq & vector).count("1") & 1 for vector in control_vectors)
    assert pair_nonzero == 0
    assert (bin(eq & control_vectors[relation["control_witness_index"]]).count("1") & 1) == 1

    pair_rank, pair_basis = rank(reversed(pair_vectors))
    control_rank, control_basis = rank(reversed(control_vectors))
    combined = dict(pair_basis)
    for vector in control_basis.values():
        insert_low(combined, vector)
    full_vectors = []
    for row in initial:
        s2, s3 = row["pair_seed_sums"]
        packed = s2 | (s3 << 6) | (coordinate_mask(row["sum_point"]) << 12)
        assert packed.bit_length() <= 93
        full_vectors.append(feature_vector(packed, 93))
    full_rank, _ = rank(reversed(full_vectors))
    initial_coordinate_rank, _ = rank(reversed(pair_vectors[:8192]))
    assert (pair_rank, control_rank, len(combined), full_rank, initial_coordinate_rank) == (3198, 3199, 3199, 4248, 3198)
    assert (pair_rank, control_rank, len(combined)) == (analysis["pair_rank"], analysis["control_rank"], analysis["union_rank"])

    geometry = json.loads(paths["geometry"].read_text())["n41"]
    curve = Curve(Field(41, [0, 3]), 0)
    domains = []
    for rotation in (20, 30):
        points = geometry["point_rows_by_unique_rotation"][str(rotation)]
        sums = [curve.add(tuple(points[i][:2]), tuple(points[j][:2]))
                for i in range(64) for j in range(i + 1, 64)
                if points[i][2] != points[j][2]]
        assert len(sums) == 1956
        domains.append(sums)
    rng = random.Random(protocol["pair_spotcheck_seed"])
    sampled_indices = set()
    while len(sampled_indices) < protocol["pair_spotcheck_count"]:
        sampled_indices.add((rng.randrange(1956), rng.randrange(1956)))
    for i, j in sorted(sampled_indices):
        point = curve.add(domains[0][i], domains[1][j])
        assert point is not None and curve.on_curve(point)
        assert bin(eq & feature_vector(coordinate_mask(point), 81)).count("1") % 2 == 0
    assert all(curve.on_curve(tuple(point)) for point in control)
    result = {
        "kind": protocol["kind"],
        "status": "PASS",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "pair_sample_rows": len(pair_vectors),
        "pair_low_pivot_rank": pair_rank,
        "control_sample_rows": len(control_vectors),
        "control_low_pivot_rank": control_rank,
        "combined_low_pivot_rank": len(combined),
        "initial_full_feature_rank": full_rank,
        "initial_coordinate_feature_rank": initial_coordinate_rank,
        "pair_sample_equation_violations": pair_nonzero,
        "curve_control_equation_rejections": control_nonzero,
        "curve_control_rejection_fraction": control_nonzero / len(control_vectors),
        "curve_control_rejection_wilson95": interval(control_nonzero, len(control_vectors)),
        "independent_pair_sum_spotchecks": len(sampled_indices),
        "exhaustive_checked_combinations": exhaustive["checked_combinations"],
        "exhaustive_violations": exhaustive["violations"],
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{name: sha(path) for name, path in paths.items()},
                          "protocol": sha(HERE / "protocol_verify.json"),
                          "verify": sha(Path(__file__))},
    }
    output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": "PASS", "pair_rank": pair_rank,
                      "control_rank": control_rank, "full_rank": full_rank,
                      "control_rejections": control_nonzero,
                      "wall_s": result["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
