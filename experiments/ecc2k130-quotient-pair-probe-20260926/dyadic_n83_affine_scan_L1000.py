#!/usr/bin/env python3
"""Query the complete L1000 two-G witness index on the frozen n83 target."""

import hashlib
import json
import math
import platform
import resource
import time
from pathlib import Path

import numpy as np

import curves
import field
from compare_batch_x_only import CountingField
from dyadic_base_geometry import enumerate_points
from dyadic_n83_affine_scan_stage import second_moment_bound
from dyadic_n83_compact_index import PackedIndex, ROW_DTYPE
from dyadic_n83_five_sum_packed_stage import PackedMapping
from dyadic_n83_five_sum_stage import replay_hit
from dyadic_n83_g_pair_witness_index import hash_file
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1032"
WINDOW = 1000
PREFIX = 4096


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def peak_rss_bytes():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if platform.system() == "Darwin" else rss * 1024


def main():
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    index_receipt_path = HERE / "runs" / "n83_dyadic_G_pair_witness_index_L1000.json"
    input_path = HERE / "runs" / "n83_affine_scan_L32_inputs.json"
    support_path = HERE / "runs" / "n83_dyadic_G_pair_scalar_support_L1000.json"
    geometry_path = HERE / "runs" / "n83_dyadic_target_seed_geometry.json"
    reference = json.loads(reference_path.read_text())
    index_receipt = json.loads(index_receipt_path.read_text())
    inputs = json.loads(input_path.read_text())
    support = json.loads(support_path.read_text())
    geometry = json.loads(geometry_path.read_text())
    assert reference["curve_id"] == index_receipt["curve_id"] == support[
        "curve_id"] == inputs["curve_id"] == geometry["curve_id"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    order = int(reference["subgroup_order"])
    eigenvalue = int(geometry["frobenius_eigenvalue_mod_r"])
    assert curves.isPrimeBig(order)
    started_base = time.perf_counter_ns()
    g_labels, g_reps, _ = enumerate_points(
        curve, onb, [generator], WINDOW, eigenvalue, order)
    q_labels, q_reps, _ = enumerate_points(
        curve, onb, [target], 1, eigenvalue, order)
    assert set(g_labels).isdisjoint(q_labels)
    labels = dict(g_labels)
    labels.update({point: (1, coefficient)
                   for point, (_, coefficient) in q_labels.items()})
    assert labels[target] == (1, 1)
    assert len(labels) == 166 * (WINDOW + 1) == 166166
    base_seconds = (time.perf_counter_ns() - started_base) / 1e9
    encoded_points = json.dumps(sorted(labels), separators=(",", ":")).encode()
    encoded_labels = frozen(sorted((point[0], point[1], label[0], label[1])
                                   for point, label in labels.items()))
    base = {
        "construction": "signed-Frobenius closure of 1000 doublings of G and one public Q orbit",
        "G_doubling_window": WINDOW, "Q_doubling_window": 1,
        "nominal_seed_columns": 2,
        "actual_usable_points_B_before_folding": len(labels),
        "signed_frobenius_columns": len(g_reps) + len(q_reps),
        "effective_unknown_log_columns_after_dyadic_labels": 1,
        "enumerated_set_sha256": hashlib.sha256(encoded_points).hexdigest(),
        "point_coefficient_label_sha256": hashlib.sha256(encoded_labels).hexdigest(),
        "encoded_point_set_bytes": len(encoded_points),
        "encoded_point_label_bytes": len(encoded_labels),
    }
    assert base["signed_frobenius_columns"] == 1001
    # The G side must be exactly the G side of the previously frozen
    # two-seed L1000 base, not a new scalar or curve representation.
    assert set(g_labels).issubset(labels)
    assert geometry["factor_base"]["actual_usable_points_B_before_folding"] == 332000
    sorted_path = Path(index_receipt["local_sorted_rows"])
    assert sorted_path.is_file()
    assert sorted_path.stat().st_size == index_receipt["raw_array_bytes"]
    assert index_receipt["quotient_keys"] == support[
        "L1000_exact_quotient_keys"]
    assert index_receipt["factor_base"]["enumerated_set_sha256"] == support[
        "factor_base"]["enumerated_set_sha256"]
    # The point-witness builder already hashed the whole 2 GB array.  Hash
    # again here so this query cannot silently use a changed local corpus.
    assert hash_file(sorted_path) == index_receipt["sorted_array_sha256"]
    rows = np.memmap(sorted_path, dtype=ROW_DTYPE, mode="r",
                     shape=(index_receipt["unordered_pair_orbit_generators"],))
    canonicalize = XOnlyCycle(onb)
    g_base = sorted(g_labels)
    index = PackedIndex(rows, sorted(g_reps), g_base, curve, canonicalize)
    mapping = PackedMapping(index)
    assert tuple(inputs["target"]) == target
    assert len(inputs["rows"]) == 3
    blocks = []
    for block_number, (alpha0, delta) in enumerate(inputs["rows"], 1):
        assert 0 <= alpha0 < order and 0 < delta < order
        counted_field = CountingField(onb)
        counted_curve = curves.Curve(counted_field)
        canonical_counts = {}
        started = time.perf_counter_ns()
        alpha_point = counted_curve.mul(generator, alpha0)
        step = counted_curve.mul(generator, delta)
        point = counted_curve.add(alpha_point, counted_curve.neg(target))
        alpha = alpha0
        hits = []
        for attempt in range(1, PREFIX + 1):
            key, shift = canonicalize.key_and_shift(
                counted_curve, point, canonical_counts)
            if index.get(key) is not None:
                expected_alpha_point = curve.mul(generator, alpha)
                relation = replay_hit(
                    counted_curve, mapping, point, (target,), key, shift,
                    canonicalize, labels, generator, target,
                    expected_alpha_point, alpha, order)
                assert len(relation["point_witness"]) == 3
                hits.append({"attempt": attempt, "relation": relation})
            point = counted_curve.add(point, step)
            alpha = (alpha + delta) % order
        elapsed = time.perf_counter_ns() - started
        assert point == curve.add(curve.mul(generator, alpha), curve.neg(target))
        blocks.append({
            "block": block_number,
            "status": "bounded_ordinary_affine_progression_queries",
            "attempts_including_failed": PREFIX,
            "quotient_hits": len(hits),
            "verified_relations": hits,
            "wall_ns_including_block_start_scalar_multiplications": elapsed,
            "progression_point_additions": PREFIX,
            "field_api_operations": dict(counted_field.counts),
            "canonical_operations": canonical_counts,
            "final_progression_point_verified": True,
        })
    # Post-solve correctness control only: use the independently recovered
    # rho scalar to plant one first-lookup hit on this exact L1000 index.
    # It is excluded from every ordinary attempt and yield count.
    rho_path = HERE / "runs" / "n83_public_target_rho_solved.json"
    rho = json.loads(rho_path.read_text())
    known_scalar = int(rho["recovered_scalar"])
    assert rho["curve_id"] == reference["curve_id"]
    assert curve.mul(generator, known_scalar) == target
    planted_row = next(row for row in rows if (int(row["hi"]) or
                                          int(row["lo"])))
    representative, pair = index.decode(planted_row)
    assert representative is not None
    pair_coefficient = sum(labels[point][1] for point in pair) % order
    planted_alpha = (pair_coefficient + known_scalar) % order
    planted_alpha_point = curve.mul(generator, planted_alpha)
    planted_complement = curve.add(planted_alpha_point, curve.neg(target))
    assert planted_complement == representative
    planted_key, planted_shift = canonicalize.key_and_shift(
        curve, planted_complement)
    assert index.get(planted_key) is not None
    planted_relation = replay_hit(
        curve, mapping, planted_complement, (target,), planted_key,
        planted_shift, canonicalize, labels, generator, target,
        planted_alpha_point, planted_alpha, order)
    assert planted_relation["recovered_scalar"] == known_scalar
    pair_support = int(support["L1000_exact_distinct_G_pair_sums"])
    length, q_bound, blocks_upper, blocks95 = second_moment_bound(
        order, pair_support)
    expected_scan_additions_upper = length * blocks_upper
    success95_scan_additions_upper = length * blocks95
    measured_attempts = len(blocks) * PREFIX
    measured_wall_ns = sum(
        row["wall_ns_including_block_start_scalar_multiplications"]
        for row in blocks)
    measured_api = {
        name: sum(row["field_api_operations"].get(name, 0)
                  for row in blocks)
        for name in sorted({name for row in blocks
                            for name in row["field_api_operations"]})
    }
    measured_rotations = sum(
        row["canonical_operations"]["word_rotations"] for row in blocks)
    work_estimate = {
        "scope": "rigorous random-input scan-addition bounds plus conditional transfer of measured 12288-prefix operation and wall rates; measured prefix rates include two scalar-multiplication starts per 4096 attempts; index build and full-run effects are separate",
        "expected_upper_scan_point_additions_log2": math.log2(
            expected_scan_additions_upper),
        "success_95pct_scan_point_additions_log2": math.log2(
            success95_scan_additions_upper),
        "packed_binary_search_row_probes_upper_per_lookup":
            len(rows).bit_length() + 1,
        "expected_upper_packed_row_probes_log2": math.log2(
            expected_scan_additions_upper * (len(rows).bit_length() + 1)),
        "measured_prefix_wall_ns_per_attempt":
            measured_wall_ns / measured_attempts,
        "conditional_expected_upper_wall_seconds_log2": math.log2(
            expected_scan_additions_upper * measured_wall_ns /
            measured_attempts / 1e9),
        "conditional_expected_upper_field_api_operations_log2": {
            name: math.log2(expected_scan_additions_upper * count /
                            measured_attempts)
            for name, count in measured_api.items() if count
        },
        "conditional_expected_upper_word_rotations_log2": math.log2(
            expected_scan_additions_upper * measured_rotations /
            measured_attempts),
        "measured_prefix_api_operation_totals": measured_api,
        "measured_prefix_word_rotations": measured_rotations,
        "measured_prefix_attempts": measured_attempts,
    }
    ordinary_relations = [item["relation"] for block in blocks
                          for item in block["verified_relations"]]
    if ordinary_relations:
        assert all(item["recovered_scalar"] == known_scalar
                   for item in ordinary_relations)
    workload = {
        "curve_id": reference["curve_id"], "target": target,
        "target_count": 1, "G_doubling_window": WINDOW,
        "Q_doubling_window": 1, "input_law": inputs["input_law"],
        "frozen_inputs_sha256": sha(input_path),
        "point_witness_index_sha256": index_receipt["sorted_array_sha256"],
        "blocks": 3, "prefix_per_block": PREFIX,
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n83_L1000_three_point_affine_scan_bounded_stage",
        "scope": "complete L1000 point-witness lookup with bounded ordinary prefixes and a separately labeled planted control; no complete IC-work claim",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": base,
        "target_dependent_base_enumeration_seconds": base_seconds,
        "target_independent_G_pair_index": {
            "unordered_pair_orbit_generators": index_receipt[
                "unordered_pair_orbit_generators"],
            "quotient_keys": index_receipt["quotient_keys"],
            "sorted_array_bytes": index_receipt["raw_array_bytes"],
            "sorted_array_sha256": index_receipt["sorted_array_sha256"],
            "point_witness_receipt_sha256": sha(index_receipt_path),
        },
        "ordinary_query_blocks": blocks,
        "ordinary_attempts": 3 * PREFIX,
        "ordinary_quotient_hits": sum(row["quotient_hits"] for row in blocks),
        "ordinary_recovered_scalar": (
            str(ordinary_relations[0]["recovered_scalar"])
            if ordinary_relations else None),
        "planted_positive_control": {
            "scope": "post-rho known-scalar witness check, excluded from ordinary yield",
            "known_query_scalar_alpha": str(planted_alpha),
            "quotient_key": planted_key,
            "quotient_shift": planted_shift,
            "relation": planted_relation,
            "rho_receipt_sha256": sha(rho_path),
        },
        "L1000_exact_G_pair_sum_support": pair_support,
        "L1000_affine_block_length_for_mu_at_least_2": length,
        "L1000_one_block_failure_probability_upper": q_bound,
        "L1000_expected_blocks_upper": blocks_upper,
        "L1000_blocks_for_at_least_95pct_success": blocks95,
        "projected_work": work_estimate,
        "verified_single_target_dlp": bool(ordinary_relations),
        "complete_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "compare_batch_x_only.py", "dyadic_base_geometry.py",
            "dyadic_n83_affine_scan_stage.py", "dyadic_n83_compact_index.py",
            "dyadic_n83_five_sum_packed_stage.py",
            "dyadic_n83_five_sum_stage.py",
            "dyadic_n83_g_pair_witness_index.py", "x_only_cycle.py",
            "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
        "support_receipt_sha256": sha(support_path),
        "frozen_inputs_sha256": sha(input_path),
        "peak_process_rss_bytes": peak_rss_bytes(),
    }
    out = HERE / "runs" / "n83_affine_scan_L1000_stage.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"actual_B": len(labels),
                      "index_keys": index_receipt["quotient_keys"],
                      "ordinary_attempts": report["ordinary_attempts"],
                      "ordinary_hits": report["ordinary_quotient_hits"],
                      "query_wall_seconds": [round(
                          row["wall_ns_including_block_start_scalar_multiplications"] /
                          1e9, 4) for row in blocks]}))


if __name__ == "__main__":
    main()
