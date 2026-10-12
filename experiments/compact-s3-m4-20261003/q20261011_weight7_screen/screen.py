#!/usr/bin/env python3
"""Q1447: sample N131 W7/W8 rationality and screen conditional m4 costs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import sys
import time
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
from run_probe import curves, field  # noqa: E402

OUT = HERE / "measurement.json"
EXACT = PARENT / "runs/n131_q1413_projected_x_w6.json"
DESIGN = PARENT / "protocol.json"
N = 131
MASK = (1 << N) - 1
CAP = 1 << 61
Z95 = 1.959963984540054


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_rotation(value: int) -> int:
    least = value
    for _ in range(1, N):
        value = ((value << 1) | (value >> (N - 1))) & MASK
        least = min(least, value)
    return least


def wilson(hits: int, total: int) -> tuple[float, float]:
    p = hits / total
    z2 = Z95 * Z95
    center = (p + z2 / (2 * total)) / (1 + z2 / total)
    radius = Z95 * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / (1 + z2 / total)
    return max(0.0, center - radius), min(1.0, center + radius)


def sample_stratum(onb, curve, weight: int, count: int, seed: int, r: int,
                   rational_controls: int, projection_controls: int) -> dict:
    rng = random.Random(seed)
    seen = set()
    digest = hashlib.sha256()
    rational = 0
    trace_controls = 0
    projected = 0
    nonidentity = 0
    subgroup_controls = 0
    projected_x_orbits = set()
    started = time.perf_counter_ns()
    while len(seen) < count:
        positions = rng.sample(range(N), weight)
        mask = sum(1 << pos for pos in positions)
        orbit = canonical_rotation(mask)
        if orbit in seen:
            continue
        seen.add(orbit)
        digest.update(orbit.to_bytes(17, "little"))
        x = onb.fromCoords(orbit)
        assert onb.trace(x) == (weight & 1)
        is_rational = onb.trace(onb.inv(x)) == (weight & 1)
        rational += is_rational
        if trace_controls < rational_controls:
            point = curve.pointFromX(x)
            assert (point is not None) == is_rational
            trace_controls += 1
        if is_rational and projected < projection_controls:
            point = curve.pointFromX(x)
            assert point is not None and curve.onCurve(point)
            mapped = curve.mul(point, 4)
            projected += 1
            nonidentity += mapped is not None
            if mapped is not None:
                key = min(onb.toCoords(curve.frob(mapped, k)[0])
                          for k in range(N))
                projected_x_orbits.add(key)
                if subgroup_controls < 4:
                    assert curve.mul(mapped, r) is None
                    subgroup_controls += 1
    low, high = wilson(rational, count)
    return {
        "weight": weight,
        "sampled_unique_frobenius_orbits": count,
        "seed": seed,
        "sample_stream_sha256": digest.hexdigest(),
        "rational_x_orbits": rational,
        "rational_fraction": rational / count,
        "rational_fraction_wilson95": [low, high],
        "trace_vs_point_from_x_controls": trace_controls,
        "cofactor_projected_controls": projected,
        "nonidentity_projection_controls": nonidentity,
        "distinct_projected_x_orbits_in_controls": len(projected_x_orbits),
        "subgroup_order_controls": subgroup_controls,
        "sample_wall_ns": time.perf_counter_ns() - started,
    }


def model(k: int, r: int) -> dict:
    b = 2 * N * k
    multisets = math.comb(b + 3, 4)
    mean = Fraction(multisets, r - 1)
    # Markov on rank with all representations returned and optimistically novel.
    all_return_queries = (19 * k * (r - 1) + 20 * multisets - 1) // (20 * multisets)
    # With at most one returned row per query, retain both the rank-one cap
    # and the uniform-marginal representation bound (important at W<=6).
    one_return_queries = max((19 * k + 19) // 20, all_return_queries)
    matrix = 4 * k * k
    index_states = N * k * k
    pair_probes = Fraction(k * 2 * r, b * b)
    pair_actions = Fraction(index_states) + pair_probes
    return {
        "conditional_B": b,
        "conditional_folded_K": k,
        "mean_unordered_four_point_multisets_per_uniform_nonidentity_target_model_log2": (
            math.log2(mean.numerator) - math.log2(mean.denominator)),
        "all_representations_returned_95pct_rank_query_floor": all_return_queries,
        "all_representations_returned_query_floor_log2": math.log2(all_return_queries),
        "one_relation_returned_per_query_95pct_rank_query_floor": one_return_queries,
        "one_relation_returned_query_floor_log2": math.log2(one_return_queries),
        "scalar_sparse_matrix_proxy_operations": matrix,
        "scalar_sparse_matrix_proxy_log2": math.log2(matrix),
        "matrix_proxy_fraction_of_2pow61": matrix / CAP,
        "zero_other_cost_per_query_ceiling_log2_all_return": 61 - math.log2(all_return_queries),
        "zero_other_cost_per_query_ceiling_log2_one_return": 61 - math.log2(one_return_queries),
        "post_matrix_proxy_per_query_ceiling_log2_all_return": (
            math.log2(CAP - matrix) - math.log2(all_return_queries)
            if matrix < CAP else None),
        "post_matrix_proxy_per_query_ceiling_log2_one_return": (
            math.log2(CAP - matrix) - math.log2(one_return_queries)
            if matrix < CAP else None),
        "pure_pair_index_states_log2": math.log2(index_states),
        "pure_pair_index_plus_K_rows_actions_model_log2": (
            math.log2(pair_actions.numerator) - math.log2(pair_actions.denominator)),
    }


def build() -> dict:
    protocol = json.loads((HERE / "protocol.json").read_text())
    exact = json.loads(EXACT.read_text())
    design = json.loads(DESIGN.read_text())["degree_131_design"]
    assert protocol["proposal_id"] == "Q1447"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == exact["isogeny"] == design["isogeny"] == "none"
    assert protocol["curve_id"] == exact["curve_id"] == design["curve"]["curve_id"]
    assert exact["normal_basis_weight_bound"] == 6
    assert exact["actual_usable_points_B_before_folding"] == (
        2 * N * exact["signed_frobenius_columns_K"])
    r = design["curve"]["subgroup_order"]
    assert design["curve"]["order"] == 4 * r
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    samples = []
    rows = [{"weight_bound": 6, "base_status": "exact_enumerated",
             "B": exact["actual_usable_points_B_before_folding"],
             "K": exact["signed_frobenius_columns_K"],
             "model": model(exact["signed_frobenius_columns_K"], r)}]
    cumulative_k = exact["signed_frobenius_columns_K"]
    for spec in protocol["sampled_new_strata"]:
        weight = spec["weight"]
        sample = sample_stratum(
            onb, curve, weight, spec["unique_frobenius_orbits"], spec["seed"], r,
            protocol["rationality_control_masks_per_stratum"],
            protocol["cofactor_projection_controls_per_stratum"])
        samples.append(sample)
        nominal_masks = math.comb(N, weight)
        assert nominal_masks % N == 0
        nominal_orbits = nominal_masks // N
        estimate_new_k = nominal_orbits * sample["rational_fraction"]
        low_new_k = nominal_orbits * sample["rational_fraction_wilson95"][0]
        high_new_k = nominal_orbits * sample["rational_fraction_wilson95"][1]
        # Retain the previous stratum's interval in later rows.
        if weight == 7:
            low_k = exact["signed_frobenius_columns_K"] + low_new_k
            high_k = exact["signed_frobenius_columns_K"] + high_new_k
        else:
            low_k += low_new_k
            high_k += high_new_k
        cumulative_k += round(estimate_new_k)
        rows.append({
            "weight_bound": weight,
            "base_status": "sampled_conditional_projection_count",
            "nominal_new_x_masks": nominal_masks,
            "nominal_new_x_orbits": nominal_orbits,
            "conditional_B": 2 * N * cumulative_k,
            "conditional_folded_K": cumulative_k,
            "conditional_K_interval_from_componentwise_wilson95": [
                math.floor(low_k), math.ceil(high_k)],
            "model": model(cumulative_k, r),
            "model_at_K_interval_endpoints": [model(math.floor(low_k), r),
                                              model(math.ceil(high_k), r)],
        })
    return {
        "kind": "q1447_n131_weight7_weight8_conditional_m4_screen",
        "proposal_id": "Q1447",
        "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "field_degree_n": N, "summands_m": 4,
        "subgroup_order_r": str(r),
        "exact_weight6_base_set_sha256": exact["enumerated_set_sha256"],
        "exact_weight6_B": exact["actual_usable_points_B_before_folding"],
        "exact_weight6_K": exact["signed_frobenius_columns_K"],
        "samples": samples,
        "rows": rows,
        "assumptions": protocol["screen_models"],
        "python_version": platform.python_version(),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "exact_base_receipt_sha256": sha(EXACT),
        "parent_design_sha256": sha(DESIGN),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "source_sha256": sha(Path(__file__)),
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.check:
        saved = json.loads(OUT.read_text())
        # Timing is descriptive and varies; all deterministic values must match.
        for sample in saved["samples"]:
            sample.pop("sample_wall_ns")
        for sample in result["samples"]:
            sample.pop("sample_wall_ns")
        assert saved == result
        print("PASS Q1447 sampled geometry and conditional work screen")
    else:
        assert not OUT.exists()
        OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(OUT)


if __name__ == "__main__":
    main()
