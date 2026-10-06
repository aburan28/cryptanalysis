#!/usr/bin/env python3
"""Stratified geometry estimate for Q1303's proposed N131 weight-six base.

This estimates rational sparse x supports. It does not enumerate the full
factor base, assign an IC candidate ID, or measure relation yield or solving.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import resource
import time
from pathlib import Path

from run_probe import HERE, curves, field, sha


N = 131
SAMPLE_SIZES = {1: None, 2: None, 3: 20_000, 4: 30_000,
                5: 50_000, 6: 100_000}
SEED_BASE = 2026100300


def supports(weight, population, size, seed):
    if size is None or size == population:
        for positions in itertools.combinations(range(N), weight):
            yield sum(1 << i for i in positions)
        return
    rng = random.Random(seed)
    seen = set()
    while len(seen) < size:
        mask = sum(1 << i for i in rng.sample(range(N), weight))
        if mask not in seen:
            seen.add(mask)
            yield mask


def main():
    output = HERE / "runs/n131_weight6_stratified_sample.json"
    assert not output.exists()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    design = protocol["degree_131_design"]
    assert design["proposal_id"] == "Q1303"
    assert design["candidate_id"] is None
    assert design["field"]["n"] == N
    assert design["factor_base"]["normal_basis_weight_bound"] == 6
    assert design["factor_base"]["actual_usable_points_B_before_folding"] is None
    assert design["isogeny"] == "none"
    runtime_path = HERE / "n131_sample_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    assert curves.curveOrder(N) == design["curve"]["order"]
    subgroup_order = design["curve"]["subgroup_order"]
    cofactor = design["curve"]["cofactor"]
    assert cofactor * subgroup_order == design["curve"]["order"]

    strata = []
    exact_w2_base = set()
    total_started = time.perf_counter()
    for weight, requested in SAMPLE_SIZES.items():
        population = math.comb(N, weight)
        sample_size = population if requested is None else requested
        assert sample_size <= population
        seed = SEED_BASE + weight
        digest = hashlib.sha256()
        rational = 0
        group_controls = 0
        nonrational_controls = 0
        control_masks = []
        control_rational = 0
        control_nonrational = 0
        started = time.perf_counter()
        for mask in supports(weight, population, requested, seed):
            x = onb.fromCoords(mask)
            assert onb.trace(x) == weight & 1
            is_rational = onb.trace(onb.inv(x)) == weight & 1
            digest.update(mask.to_bytes(17, "little"))
            digest.update(bytes((int(is_rational),)))
            rational += is_rational
            if is_rational and control_rational < 8:
                control_masks.append({"normal_x_mask": mask,
                                      "rational": True})
                control_rational += 1
            elif not is_rational and control_nonrational < 8:
                control_masks.append({"normal_x_mask": mask,
                                      "rational": False})
                control_nonrational += 1
            if weight == 2 and is_rational:
                point = curve.pointFromX(x)
                assert point is not None
                projected = curve.mul(point, cofactor)
                assert projected is not None
                exact_w2_base.add(projected)
                exact_w2_base.add(curve.neg(projected))
            elif is_rational and group_controls < 3:
                point = curve.pointFromX(x)
                assert point is not None
                projected = curve.mul(point, cofactor)
                assert projected is not None
                assert curve.onCurve(projected)
                assert curve.mul(projected, subgroup_order) is None
                group_controls += 1
            elif not is_rational and nonrational_controls < 3:
                assert curve.pointFromX(x) is None
                nonrational_controls += 1
        elapsed = time.perf_counter() - started
        p = rational / sample_size
        estimate = population * p
        if sample_size == population:
            variance = 0.0
        else:
            variance = (population ** 2 * p * (1 - p) / sample_size
                        * ((population - sample_size) / (population - 1)))
        strata.append({
            "weight": weight,
            "support_population": population,
            "sampling_mode": ("exhaustive" if sample_size == population
                              else "seeded_distinct_uniform_supports"),
            "seed": seed if sample_size != population else None,
            "sample_size": sample_size,
            "rational_x_count_in_sample": rational,
            "rational_x_rate": p,
            "estimated_rational_x_count": estimate,
            "estimated_count_variance": variance,
            "support_classification_sha256": digest.hexdigest(),
            "independent_replay_control_masks": control_masks,
            "group_controls": group_controls,
            "nonrational_controls": nonrational_controls,
            "wall_seconds": elapsed,
        })
        print(json.dumps({"weight": weight, "sample": sample_size,
                          "rational": rational, "seconds": elapsed}),
              flush=True)
    assert strata[0]["rational_x_count_in_sample"] == 0
    assert len(exact_w2_base) == 2 * strata[1]["rational_x_count_in_sample"]
    assert len(exact_w2_base) % (2 * N) == 0
    rational_est = sum(row["estimated_rational_x_count"] for row in strata)
    variance = sum(row["estimated_count_variance"] for row in strata)
    lower = rational_est - 1.96 * math.sqrt(variance)
    upper = rational_est + 1.96 * math.sqrt(variance)
    b_est = 2 * rational_est
    k_est = rational_est / N
    expected_subsets = math.comb(round(b_est), 4) / subgroup_order
    probability = -math.expm1(-expected_subsets)
    ideal_queries = k_est / probability
    receipt = {
        "kind": "stratified_n131_weight6_rational_support_geometry_estimate",
        "proposal_id": "Q1303", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "curve_id": design["curve"]["curve_id"],
        "isogeny": "none", "n": N,
        "weight_bound": 6,
        "method": "all supports of weights one and two; seeded uniform distinct support samples for weights three through six; rational iff Tr(x)+Tr(x^-1)=0",
        "strata": strata,
        "rational_x_count_estimate": rational_est,
        "rational_x_count_normal_95_percent_interval": [lower, upper],
        "exact_weight_at_most_two_projected_B": len(exact_w2_base),
        "exact_weight_at_most_two_folded_columns": len(exact_w2_base) // (2 * N),
        "conditional_B_estimate": b_est,
        "conditional_B_normal_95_percent_interval": [2 * lower, 2 * upper],
        "conditional_folded_columns_estimate": k_est,
        "conditional_B_assumptions": "every rational nonzero x has two distinct lifts; cofactor projection is nonidentity and injective on the proposed sparse-x set; signed Frobenius orbits have length 262",
        "uniform_subset_sum_planning_heuristic": {
            "expected_unordered_four_point_subsets_per_target": expected_subsets,
            "poisson_probability_at_least_one": probability,
            "ideal_queries_for_one_rank_per_hit": ideal_queries,
            "log2_ideal_queries": math.log2(ideal_queries),
            "optimistic_max_mean_field_ops_per_query_log2_under_2pow61":
                61 - math.log2(ideal_queries),
            "assumptions": "each distinct four-subset sums independently uniformly; each hit adds one rank; all factor-base construction, matrix, descent, replay and conversion costs are set to zero for this screening ceiling",
            "is_measured_relation_yield": False,
            "is_complete_solve_projection": False,
        },
        "total_sample_wall_seconds": time.perf_counter() - total_started,
        "peak_parent_rss_raw": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "peak_parent_rss_units": "bytes on Darwin, KiB on Linux",
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "source_sha256": sha(Path(__file__)),
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"B_estimate": b_est,
                      "B_95_percent_interval": [2 * lower, 2 * upper],
                      "K_estimate": k_est,
                      "optimistic_per_query_log2": receipt[
                          "uniform_subset_sum_planning_heuristic"][
                              "optimistic_max_mean_field_ops_per_query_log2_under_2pow61"]}),
          flush=True)


if __name__ == "__main__":
    main()
