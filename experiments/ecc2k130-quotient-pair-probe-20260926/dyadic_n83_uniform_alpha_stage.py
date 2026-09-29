#!/usr/bin/env python3
"""Fresh-alpha five-point quotient queries on the frozen n83 public target.

Fresh independent uniform known-log G multiples make each complement uniform
for any fixed target Q and any Q triple with nonzero coefficient.  The frozen
L32 run is a throughput and correctness control; it is not a solve.
"""

import argparse
import hashlib
import json
import math
import platform
import resource
import secrets
import time
from pathlib import Path

import curves
import field
from compare_batch_x_only import CountingField
from dyadic_base_geometry import enumerate_points
from dyadic_five_sum_batch import batch_add_pairs
from dyadic_n83_five_sum_packed_stage import PackedMapping, packed_positions
from dyadic_n83_five_sum_symmetric_stage import build_symmetric
from dyadic_n83_five_sum_stage import replay_hit
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1030"
WINDOW = 32
BLOCKS = 3
BLOCK_SIZE = 4096
BATCH_SIZE = 512
RADIX_BITS = 8
INPUT_PATH = HERE / "runs" / "n83_uniform_alpha_L32_inputs.json"
REPORT_PATH = HERE / "runs" / "n83_uniform_alpha_L32_stage.json"


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def peak_rss_bytes():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if platform.system() == "Darwin" else rss * 1024


def setup():
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    baseline = json.loads((HERE / "runs" /
                           "n83_dyadic_five_sum_stage.json").read_text())
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert baseline["curve_id"] == reference["curve_id"]
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    eigenvalue = int(baseline["frobenius_eigenvalue_mod_r"])
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target], WINDOW, eigenvalue, order)
    assert digests["enumerated_set_sha256"] == baseline[
        "factor_base"]["enumerated_set_sha256"]
    g_base = [point for point in sorted(labels) if labels[point][0] == 0]
    q_base = [point for point in sorted(labels) if labels[point][0] == 1]
    g_reps = [point for point in sorted(representatives)
              if labels[point][0] == 0]
    assert len(labels) == 10624 and len(g_reps) == 32
    return (reference_path, reference, baseline, onb, curve, order,
            generator, target, labels, g_base, q_base, g_reps, digests)


def freeze_inputs():
    if INPUT_PATH.exists():
        raise FileExistsError(INPUT_PATH)
    (reference_path, reference, _, _, _, order, _, target, labels, _,
     q_base, _, digests) = setup()
    system_random = secrets.SystemRandom()
    rows = []
    rejected_zero_coefficient = 0
    for _ in range(BLOCKS * BLOCK_SIZE):
        while True:
            triple = [system_random.randrange(len(q_base)) for _ in range(3)]
            if sum(labels[q_base[i]][1] for i in triple) % order:
                break
            rejected_zero_coefficient += 1
        rows.append([secrets.randbelow(order), *triple])
    report = {
        "kind": "n83_L32_fresh_uniform_alpha_frozen_query_inputs",
        "curve_id": reference["curve_id"], "target": target,
        "factor_base_sha256": digests["enumerated_set_sha256"],
        "alpha_input_law": "independent secrets.randbelow(r) per trial, OS-backed rejection sampling",
        "triple_input_law": "three independent uniform Q-base indices per trial, resample only if their Q coefficient sums to zero",
        "rejected_zero_coefficient_triples": rejected_zero_coefficient,
        "target_count": 1, "blocks": BLOCKS, "block_size": BLOCK_SIZE,
        "rows": rows, "reference_sha256": sha(reference_path),
        "source_sha256": sha(Path(__file__)),
    }
    INPUT_PATH.write_text(json.dumps(report, separators=(",", ":")) + "\n")
    print(json.dumps({"rows": len(rows),
                      "rejected_zero_coefficient_triples": rejected_zero_coefficient,
                      "input_sha256": sha(INPUT_PATH)}))


def radix_table(curve, generator, order):
    """Target-independent fixed-base table with one row per radix-256 window."""
    started = time.perf_counter_ns()
    radix = 1 << RADIX_BITS
    windows = (order.bit_length() + RADIX_BITS - 1) // RADIX_BITS
    base = generator
    table = []
    for _ in range(windows):
        row = [None]
        point = None
        for _ in range(1, radix):
            point = curve.add(point, base)
            row.append(point)
        table.append(row)
        for _ in range(RADIX_BITS):
            base = curve.add(base, base)
    return table, time.perf_counter_ns() - started


def batch_fixed_base_multiples(curve, table, scalars):
    points = [None] * len(scalars)
    group_additions = 0
    mask = (1 << RADIX_BITS) - 1
    for window, row in enumerate(table):
        terms = [row[(scalar >> (window * RADIX_BITS)) & mask]
                 for scalar in scalars]
        group_additions += sum(left is not None and right is not None
                               for left, right in zip(points, terms))
        points = batch_add_pairs(curve, list(zip(points, terms)))
    return points, group_additions


def run():
    (reference_path, reference, baseline, onb, curve, order,
     generator, target, labels, g_base, q_base, g_reps, digests) = setup()
    inputs = json.loads(INPUT_PATH.read_text())
    assert inputs["curve_id"] == reference["curve_id"]
    assert tuple(inputs["target"]) == target
    assert inputs["factor_base_sha256"] == digests["enumerated_set_sha256"]
    assert inputs["source_sha256"] == sha(Path(__file__))
    assert inputs["reference_sha256"] == sha(reference_path)
    assert len(inputs["rows"]) == BLOCKS * BLOCK_SIZE
    for alpha, i, j, k in inputs["rows"]:
        assert 0 <= alpha < order
        assert all(0 <= item < len(q_base) for item in (i, j, k))
        assert sum(labels[q_base[item]][1] for item in (i, j, k)) % order
    canonicalize = XOnlyCycle(onb)
    table, table_ns = radix_table(curve, generator, order)
    for alpha in (0, 1, order - 1, *[row[0] for row in inputs["rows"][:16]]):
        multiples, _ = batch_fixed_base_multiples(curve, table, [alpha])
        assert multiples[0] == curve.mul(generator, alpha)
    index, build = build_symmetric(curve, g_reps, g_base, canonicalize)
    assert build["quotient_keys"] == baseline["index_build"]["quotient_keys"]
    mapping = PackedMapping(index)
    counted_field = CountingField(onb)
    counted_curve = curves.Curve(counted_field)
    canonical_counts = {}
    results = []
    for block_number in range(BLOCKS):
        rows = inputs["rows"][block_number * BLOCK_SIZE:
                              (block_number + 1) * BLOCK_SIZE]
        start_counts = dict(counted_field.counts)
        start_canonical = dict(canonical_counts)
        started = time.perf_counter_ns()
        group_additions = 0
        relations = []
        quotient_hits = 0
        for batch_number in range(BLOCK_SIZE // BATCH_SIZE):
            batch = rows[batch_number * BATCH_SIZE:
                         (batch_number + 1) * BATCH_SIZE]
            alphas = [row[0] for row in batch]
            triples = [tuple(q_base[i] for i in row[1:]) for row in batch]
            alpha_points, fixed_base_adds = batch_fixed_base_multiples(
                counted_curve, table, alphas)
            group_additions += fixed_base_adds + 3 * len(batch)
            if batch_number == 0:
                assert alpha_points[0] == curve.mul(generator, alphas[0])
            first = batch_add_pairs(
                counted_curve, [(a, b) for a, b, _ in triples])
            sums = batch_add_pairs(
                counted_curve, list(zip(first, (t[2] for t in triples))))
            complements = batch_add_pairs(
                counted_curve, list(zip(
                    alpha_points, (counted_curve.neg(point) for point in sums))))
            keys_shifts = [canonicalize.key_and_shift(
                counted_curve, point, canonical_counts)
                for point in complements]
            _, found = packed_positions(index, [key for key, _ in keys_shifts])
            for offset, hit in enumerate(found):
                if not hit:
                    continue
                quotient_hits += 1
                key, shift = keys_shifts[offset]
                relation = replay_hit(
                    counted_curve, mapping, complements[offset],
                    triples[offset], key, shift, canonicalize, labels,
                    generator, target, alpha_points[offset], alphas[offset],
                    order)
                relations.append({"attempt": batch_number * BATCH_SIZE +
                                  offset + 1, "relation": relation})
        elapsed = time.perf_counter_ns() - started
        results.append({
            "block": block_number + 1,
            "status": "bounded_ordinary_uniform_alpha_queries",
            "attempts_including_failed": BLOCK_SIZE,
            "quotient_hits": quotient_hits,
            "verified_relations": relations,
            "wall_ns": elapsed,
            "logical_group_additions": group_additions,
            "field_api_operations": {key: value - start_counts.get(key, 0)
                                     for key, value in counted_field.counts.items()},
            "canonical_operations": {key: value - start_canonical.get(key, 0)
                                     for key, value in canonical_counts.items()},
        })
    support = int(baseline["exact_two_G_pair_sum_support"])
    expected_trials_log2 = math.log2(order) - math.log2(support)
    support_l1000 = json.loads((HERE / "runs" /
                                "n83_dyadic_G_pair_scalar_support_L1000.json").read_text())
    assert support_l1000["curve_id"] == reference["curve_id"]
    l1000_support = int(support_l1000["L1000_exact_distinct_G_pair_sums"])
    l1000_expected_trials_log2 = math.log2(order) - math.log2(l1000_support)
    l1000_expected_adds_bound = 83 * 1000 * 1001 + 13 * order / l1000_support
    workload = {"curve_id": reference["curve_id"], "target": target,
                "target_count": 1, "doubling_window": WINDOW,
                "alpha_input_law": inputs["alpha_input_law"],
                "triple_input_law": inputs["triple_input_law"],
                "frozen_inputs_sha256": sha(INPUT_PATH),
                "blocks": BLOCKS, "block_size": BLOCK_SIZE,
                "batch_size": BATCH_SIZE, "radix_bits": RADIX_BITS}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    receipt = {
        "kind": "n83_fresh_alpha_five_sum_bounded_stage",
        "scope": "fresh-alpha ordinary query throughput and exact ideal-random hit law; no measured n83 relation or IC DLP",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": baseline["factor_base"],
        "target_independent_fixed_base_table_seconds": table_ns / 1e9,
        "target_independent_fixed_base_table_entries": len(table) * len(table[0]),
        "target_dependent_two_G_index_build": build,
        "ordinary_query_blocks": results,
        "ordinary_attempts": BLOCKS * BLOCK_SIZE,
        "ordinary_quotient_hits": sum(row["quotient_hits"] for row in results),
        "L32_exact_pair_sum_support": support,
        "L32_ideal_independent_alpha_hit_probability": f"{support}/{order}",
        "L32_ideal_expected_attempts_log2": expected_trials_log2,
        "L1000_exact_pair_sum_support": l1000_support,
        "L1000_ideal_independent_alpha_hit_probability": f"{l1000_support}/{order}",
        "L1000_ideal_expected_attempts_log2": l1000_expected_trials_log2,
        "L1000_expected_logical_group_additions_upper_bound_log2": math.log2(
            l1000_expected_adds_bound),
        "probability_scope": "For each trial, choose the Q triple with nonzero coefficient before an independent uniform alpha in Z_r. Conditional on the fixed public Q, triple, and all past trials, alpha*G - triple_sum is uniform on the order-r subgroup. Its chance to lie in the complete G-pair support is exactly |S|/r; on a hit the nonzero Q coefficient recovers the target log. The expected trial count is exactly r/|S| under this random-input law. The logged finite OS-random sample is a throughput control, not an observed yield estimate.",
        "work_scope": "L1000 bound counts at most ten fixed-base group additions, two triple additions, and one complement addition per trial, plus all 83,083,000 index pair additions. It omits quotient canonicalization, memory lookup, base/table setup, and operation-unit conversion; it is not complete IC work.",
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "batch_x_only.py", "compare_batch_x_only.py",
            "dyadic_base_geometry.py", "dyadic_five_sum_batch.py",
            "dyadic_n83_five_sum_packed_stage.py",
            "dyadic_n83_five_sum_symmetric_stage.py",
            "dyadic_n83_five_sum_stage.py", "dyadic_n83_compact_index.py",
            "x_only_cycle.py", "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
        "baseline_sha256": sha(HERE / "runs" /
                               "n83_dyadic_five_sum_stage.json"),
        "frozen_inputs_sha256": sha(INPUT_PATH),
        "peak_process_rss_bytes": peak_rss_bytes(),
    }
    REPORT_PATH.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"ordinary_attempts": receipt["ordinary_attempts"],
                      "ordinary_quotient_hits": receipt["ordinary_quotient_hits"],
                      "L1000_ideal_expected_attempts_log2": l1000_expected_trials_log2,
                      "L1000_expected_logical_group_additions_upper_bound_log2":
                      receipt["L1000_expected_logical_group_additions_upper_bound_log2"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze-inputs", "run"))
    args = parser.parse_args()
    if args.mode == "freeze-inputs":
        freeze_inputs()
    else:
        run()
