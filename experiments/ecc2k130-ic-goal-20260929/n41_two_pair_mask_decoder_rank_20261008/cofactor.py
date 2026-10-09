#!/usr/bin/env python3
"""Identify the extracted N41 quadratic with the four-divisibility character."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from run_n41_disjoint_s5_sat import Curve, Field  # noqa: E402
from holdout import feature_vector  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "cofactor_result.json"
    if output.exists():
        raise FileExistsError("preserve first cofactor check")
    start = time.monotonic_ns()
    protocol_path = HERE / "protocol_cofactor.json"
    protocol = json.loads(protocol_path.read_text())
    names = ("geometry", "initial_rows", "holdout_rows", "curve_control_rows",
             "relation", "feature_script", "curve_arithmetic")
    paths = {name: (HERE / protocol[name]).resolve() for name in names}
    assert all(sha(path) == protocol[f"{name}_sha256"] for name, path in paths.items())
    geometry = json.loads(paths["geometry"].read_text())["n41"]
    initial = json.loads(paths["initial_rows"].read_text())["rows"]
    holdout = json.loads(paths["holdout_rows"].read_text())["rows"]
    controls = json.loads(paths["curve_control_rows"].read_text())["points"]
    relation = json.loads(paths["relation"].read_text())
    eq = sum(1 << i for i in relation["term_indices"])
    field = Field(41, [0, 3])
    curve = Curve(field, 0)
    r = protocol["subgroup_order"]
    assert protocol["curve_order"] == 4 * r
    target = tuple(protocol["target"])
    assert curve.on_curve(target) and curve.mul(r, target) is None

    def trace(value):
        z = value
        acc = value
        for _ in range(40):
            z = field.mul(z, z)
            acc ^= z
        assert acc in (0, 1)
        return acc

    trace_basis = [i for i in range(41) if trace(1 << i)]
    assert trace_basis == [0]
    half_basis = []
    for i in range(41):
        term = 1 << i
        half = 0
        for _ in range(21):
            half ^= term
            term = field.mul(field.mul(term, term), field.mul(term, term))
        assert field.mul(half, half) ^ half == (1 << i) ^ trace(1 << i)
        half_basis.append(half)

    def character(point):
        x, y = point
        assert x & 1 == 0
        lam = 0
        for i in range(41):
            if x >> i & 1:
                lam ^= half_basis[i]
        assert field.mul(lam, lam) ^ lam == x
        # Tr(z) is bit 0 in the frozen polynomial basis.
        return (y ^ field.mul(lam ^ 1, x)) & 1

    def extracted(point):
        x, y = point
        vec = feature_vector(x, y)
        return bin(vec & eq).count("1") & 1

    pair_points = [row["sum_point"] for row in initial + holdout]
    pair_mismatches = sum(character(point) != extracted(point) for point in pair_points)
    control_mismatches = sum(character(point) != extracted(point) for point in controls)
    control_ones = sum(character(point) for point in controls)
    assert pair_mismatches == control_mismatches == 0
    assert control_ones == 4064
    seed_torsion = {}
    for rotation in (0, 10, 20, 30):
        points = geometry["point_rows_by_unique_rotation"][str(rotation)]
        assert len(points) == 64
        non_subgroup = sum(curve.mul(r, tuple(row[:2])) is not None for row in points)
        seed_torsion[str(rotation)] = {"seeds": 64, "non_subgroup": non_subgroup}
        assert non_subgroup == 0
    control_mul_mismatches = 0
    for point in controls[:256]:
        image = curve.mul(r, tuple(point))
        expected = None if character(point) == 0 else (0, 1)
        control_mul_mismatches += image != expected
    assert control_mul_mismatches == 0
    result = {
        "kind": protocol["kind"],
        "status": "PASS",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "trace_basis_one_bits": trace_basis,
        "pair_sample_points": len(pair_points),
        "pair_sample_character_equation_mismatches": pair_mismatches,
        "control_points": len(controls),
        "control_character_equation_mismatches": control_mismatches,
        "control_character_one_count": control_ones,
        "control_scalar_replays": 256,
        "control_scalar_replay_mismatches": control_mul_mismatches,
        "seed_torsion_by_rotation": seed_torsion,
        "target_in_subgroup": True,
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{name: sha(path) for name, path in paths.items()},
                          "protocol": sha(protocol_path),
                          "cofactor": sha(Path(__file__))},
    }
    output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": "PASS", "pair_mismatches": pair_mismatches,
                      "control_mismatches": control_mismatches,
                      "seed_non_subgroup": sum(x["non_subgroup"] for x in seed_torsion.values()),
                      "wall_s": result["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
