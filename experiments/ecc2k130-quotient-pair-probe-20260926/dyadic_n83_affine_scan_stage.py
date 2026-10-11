#!/usr/bin/env python3
"""Three-point n83 target relation scan with random affine scalar blocks.

The block law is pairwise uniform over the prime subgroup.  It gives an
exact second-moment success bound for any fixed G-pair support, while each
new trial costs only one point addition after block setup.
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
from dyadic_n83_five_sum_packed_stage import PackedMapping
from dyadic_n83_five_sum_symmetric_stage import build_symmetric
from dyadic_n83_five_sum_stage import replay_hit
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1031"
WINDOW = 32
BLOCKS = 3
PREFIX = 4096
INPUT_PATH = HERE / "runs" / "n83_affine_scan_L32_inputs.json"
REPORT_PATH = HERE / "runs" / "n83_affine_scan_L32_stage.json"


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def peak_rss_bytes():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if platform.system() == "Darwin" else rss * 1024


def setup():
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    previous = json.loads((HERE / "runs" /
                           "n83_dyadic_five_sum_stage.json").read_text())
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    assert curves.isPrimeBig(order)
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert reference["curve_id"] == previous["curve_id"]
    eigenvalue = int(previous["frobenius_eigenvalue_mod_r"])
    g_labels, g_reps, _ = enumerate_points(
        curve, onb, [generator], WINDOW, eigenvalue, order)
    q_labels, q_reps, _ = enumerate_points(
        curve, onb, [target], 1, eigenvalue, order)
    assert set(g_labels).isdisjoint(q_labels)
    labels = dict(g_labels)
    labels.update({point: (1, coefficient)
                   for point, (_, coefficient) in q_labels.items()})
    assert len(g_labels) == 166 * WINDOW
    assert len(q_labels) == 166
    assert labels[target] == (1, 1)
    assert len(labels) == 166 * (WINDOW + 1)
    encoded_points = json.dumps(sorted(labels), separators=(",", ":")).encode()
    encoded_labels = frozen(sorted((point[0], point[1], label[0], label[1])
                                   for point, label in labels.items()))
    base = {
        "construction": "signed-Frobenius closure of 32 doublings of G and one public Q orbit",
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
    return (reference_path, reference, previous, onb, curve, order,
            generator, target, labels, sorted(g_labels), sorted(g_reps), base)


def freeze_inputs():
    if INPUT_PATH.exists():
        raise FileExistsError(INPUT_PATH)
    (reference_path, reference, _, _, _, order, _, target, _, _, _,
     base) = setup()
    rows = []
    for _ in range(BLOCKS):
        alpha0 = secrets.randbelow(order)
        delta = 1 + secrets.randbelow(order - 1)
        rows.append([alpha0, delta])
    report = {
        "kind": "n83_L32_affine_scan_frozen_block_inputs",
        "curve_id": reference["curve_id"], "target": target,
        "factor_base_sha256": base["enumerated_set_sha256"],
        "input_law": "independent OS-backed alpha0 uniform in Z_r and delta uniform in Z_r^* per block",
        "target_count": 1, "blocks": BLOCKS, "prefix_per_block": PREFIX,
        "rows": rows,
        "reference_sha256": sha(reference_path),
        "source_sha256": sha(Path(__file__)),
    }
    INPUT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"blocks": len(rows), "input_sha256": sha(INPUT_PATH)}))


def second_moment_bound(order, support):
    """Sharp pairwise-sampling variance, followed by a second-moment tail."""
    block_length = (2 * order + support - 1) // support
    assert 1 <= block_length < order
    # For a random affine map j -> alpha0+j*delta, any two distinct positions
    # are uniform over the ordered distinct scalar pairs.
    numerator = (order - support) * (order - block_length)
    denominator = (order - 1) * block_length * support
    assert numerator * 2 < denominator
    q = numerator / denominator
    expected_blocks_upper = 1 / (1 - q)
    blocks95 = math.ceil(math.log(0.05) / math.log(q))
    assert blocks95 <= 5
    return block_length, q, expected_blocks_upper, blocks95


def run():
    (reference_path, reference, previous, onb, curve, order,
     generator, target, labels, g_base, g_reps, base) = setup()
    inputs = json.loads(INPUT_PATH.read_text())
    assert inputs["source_sha256"] == sha(Path(__file__))
    assert inputs["reference_sha256"] == sha(reference_path)
    assert inputs["curve_id"] == reference["curve_id"]
    assert tuple(inputs["target"]) == target
    assert inputs["factor_base_sha256"] == base["enumerated_set_sha256"]
    assert len(inputs["rows"]) == BLOCKS
    for alpha0, delta in inputs["rows"]:
        assert 0 <= alpha0 < order and 0 < delta < order
    canonicalize = XOnlyCycle(onb)
    index, build = build_symmetric(curve, g_reps, g_base, canonicalize)
    assert build["quotient_keys"] == previous["index_build"]["quotient_keys"]
    previous_symmetric = json.loads((HERE / "runs" /
                                     "n83_dyadic_five_sum_symmetric_stage.json").read_text())
    assert build["key_sha256"] == previous_symmetric["build"]["key_sha256"]
    mapping = PackedMapping(index)
    blocks = []
    for block_number, (alpha0, delta) in enumerate(inputs["rows"], 1):
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
    support = json.loads((HERE / "runs" /
                          "n83_dyadic_G_pair_scalar_support_L1000.json").read_text())
    assert support["curve_id"] == reference["curve_id"]
    pair_support = int(support["L1000_exact_distinct_G_pair_sums"])
    length, q_bound, blocks_upper, blocks95 = second_moment_bound(
        order, pair_support)
    index_additions = int(support["L1000_unordered_pair_orbit_generators"])
    expected_scan_adds_upper = length * blocks_upper
    workload = {"curve_id": reference["curve_id"], "target": target,
                "target_count": 1, "G_doubling_window": WINDOW,
                "Q_doubling_window": 1, "input_law": inputs["input_law"],
                "frozen_inputs_sha256": sha(INPUT_PATH),
                "blocks": BLOCKS, "prefix_per_block": PREFIX}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    receipt = {
        "kind": "n83_three_point_affine_scan_bounded_stage",
        "scope": "random-affine three-point target relation query throughput and rigorous second-moment work bound; no measured n83 relation or IC DLP",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": base,
        "target_independent_G_pair_index_build": build,
        "ordinary_query_blocks": blocks,
        "ordinary_attempts": BLOCKS * PREFIX,
        "ordinary_quotient_hits": sum(row["quotient_hits"] for row in blocks),
        "L1000_exact_G_pair_sum_support": pair_support,
        "subgroup_order": str(order),
        "L1000_affine_block_length_for_mu_at_least_2": length,
        "L1000_one_block_failure_probability_upper": q_bound,
        "L1000_expected_blocks_upper": blocks_upper,
        "L1000_blocks_for_at_least_95pct_success": blocks95,
        "L1000_expected_scan_point_additions_upper_log2": math.log2(
            expected_scan_adds_upper),
        "L1000_95pct_scan_point_additions_upper_log2": math.log2(
            blocks95 * length),
        "L1000_index_pair_additions": index_additions,
        "L1000_expected_point_additions_including_index_upper_log2": math.log2(
            index_additions + expected_scan_adds_upper),
        "proof_boundary": "For prime r and 0<T<r, alpha_j=alpha0+j*delta with independent uniform alpha0 in Z_r and delta in Z_r^* maps every two distinct positions uniformly to ordered distinct scalars. For the fixed translated G-pair support of size M, X hits in T trials has E[X]=TM/r and Var[X]=T*(M/r)*(1-M/r)*(r-T)/(r-1). Thus P(X=0)<=Var[X]/E[X]^2=(r-M)*(r-T)/((r-1)*T*M). At T=ceil(2r/M) this is below 1/2. Independent restarted blocks need at most two blocks in expectation and five blocks for at least 95% success under this bound. One point addition advances each queried complement after block setup. A hit yields k=alpha-a mod r from a verified two-G witness.",
        "work_scope": "Point-addition bounds include one progression update per trial and all 83,083,000 L1000 G-pair index additions. Block-start scalar multiplications, factor-base construction, quotient canonicalization, binary index probes, field-operation conversion, and replay are separate and not included; complete IC work remains unknown.",
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "compare_batch_x_only.py", "dyadic_base_geometry.py",
            "dyadic_n83_five_sum_packed_stage.py",
            "dyadic_n83_five_sum_symmetric_stage.py",
            "dyadic_n83_five_sum_stage.py", "dyadic_n83_compact_index.py",
            "x_only_cycle.py", "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
        "frozen_inputs_sha256": sha(INPUT_PATH),
        "peak_process_rss_bytes": peak_rss_bytes(),
    }
    REPORT_PATH.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"B": base["actual_usable_points_B_before_folding"],
                      "ordinary_attempts": receipt["ordinary_attempts"],
                      "ordinary_hits": receipt["ordinary_quotient_hits"],
                      "L1000_expected_scan_additions_upper_log2": receipt[
                          "L1000_expected_scan_point_additions_upper_log2"],
                      "L1000_95pct_scan_additions_upper_log2": receipt[
                          "L1000_95pct_scan_point_additions_upper_log2"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze-inputs", "run"))
    args = parser.parse_args()
    if args.mode == "freeze-inputs":
        freeze_inputs()
    else:
        run()
