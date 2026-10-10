#!/usr/bin/env python3
"""Independent receipt and S3 algebra replay for the native scan grid."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import experiment

HERE = Path(__file__).resolve().parent


def gf_mul(a: int, b: int, n: int, low_terms: list[int]) -> int:
    modulus = (1 << n) | sum(1 << degree for degree in low_terms)
    product = 0
    while b:
        if b & 1:
            product ^= a
        b >>= 1
        a <<= 1
        if a >> n:
            a ^= modulus
    return product


def exact_s3(left: int, output: int, right: int,
             n: int, low_terms: list[int]) -> int:
    pair = gf_mul(left, output, n, low_terms)
    triple = gf_mul(pair, right, n, low_terms)
    linear = gf_mul(left ^ output, right, n, low_terms) ^ pair
    return gf_mul(linear, linear, n, low_terms) ^ triple ^ 1


def to_cycle(onb: int, positions: list[int]) -> int:
    return sum(((onb >> position) & 1) << index
               for index, position in enumerate(positions))


def one(name: str, frozen: dict) -> dict:
    input_path = HERE / "inputs" / f"{name}.json"
    result_path = HERE / "runs" / f"{name}.scan.json"
    receipt_path = HERE / "runs" / f"{name}.receipt.json"
    inp = json.loads(input_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    assert receipt["schema"] == "q20261010111900-run-receipt-v1"
    assert receipt["cell"] == name
    assert receipt["freeze_sha256"] == experiment.sha(HERE / "freeze.json")
    assert receipt["input_sha256"] == frozen["input_sha256"][name]
    assert receipt["binary_sha256"] == inp["binary_sha256"]
    assert receipt["curve_id"] == inp["curve_id"]
    assert receipt["workload_id"] == inp["workload_id"]
    assert receipt["producer_status"] == "PASS" and receipt["exit_code"] == 0
    assert receipt["result_sha256"] == experiment.sha(result_path)
    result = json.loads(result_path.read_text())
    assert receipt["scan_status"] == result["status"]
    assert result["schema"] == "q20261010111900-quadratic-root-scan-v1"
    assert result["proposal_id"] == "Q20261010111900"
    assert result["candidate_id"] is None and result["run_id"] is None
    assert result["isogeny"] == "none"
    for input_key, result_key in (
            ("field_degree", "field_degree"), ("curve_id", "curve_id"),
            ("kind", "kind"), ("workload_id", "workload_id"),
            ("normal_basis_weight_bound", "normal_basis_weight_bound"),
            ("right_output_x_poly_decimal", "right_output_x_poly_decimal"),
            ("factor_base_actual_B", "factor_base_actual_B"),
            ("factor_base_folded_columns_K", "factor_base_folded_columns_K"),
            ("factor_base_enumerated_set_sha256",
             "factor_base_enumerated_set_sha256"),
            ("scan_window_size", "scan_window_size"),
            ("scan_mask_cap", "scan_mask_cap")):
        assert inp[input_key] == result[result_key], input_key
    n = inp["field_degree"]
    weight = inp["normal_basis_weight_bound"]
    mask_count = sum(math.comb(n, k) for k in range(1, weight + 1))
    assert mask_count == result["eligible_nonzero_masks"] == inp["scan_mask_cap"]
    scanned = result["scanned_masks"]
    assert 0 < scanned <= mask_count
    ops = result["operation_counts"]["scan"]
    assert ops["s3_root_calls"] == scanned
    assert ops["field_inv_calls"] <= result["scan_windows"]
    assert ops["field_mul_calls"] >= scanned
    assert ops["basis_conversions"] >= n
    assert result["peak_rss_bytes"] <= inp["peak_rss_cap_mib"] * 2**20
    assert int(result["timing_ns"]["scan"]) > 0
    assert int(receipt["process_wall_ns"]) >= int(result["timing_ns"]["scan"])
    assert result["n131_complete_cold_work_log2"] is None
    assert result["n131_complete_online_one_target_work_log2"] is None
    assert result["stop_reason"] in ("complete", "wall_cap_exceeded",
                                      "memory_cap_exceeded")
    if result["stop_reason"] == "complete":
        assert scanned == mask_count
        assert result["scan_windows"] == sum(
            math.ceil(math.comb(n, k) / inp["scan_window_size"])
            for k in range(1, weight + 1))
        assert result["status"] == ("WEIGHT_PAIR_FOUND" if
                                    result["unique_unordered_weight_pairs"] else
                                    "EXHAUSTIVE_NO_WEIGHT_PAIR")
    else:
        assert result["status"] == "BOUNDED_UNKNOWN"

    bridge_path = experiment.OLD / "field_bridges" / f"n{n}_onb_poly.json"
    assert experiment.sha(bridge_path) == inp["bridge_sha256"]
    bridge = json.loads(bridge_path.read_text())
    assert bridge["curve_id"] == inp["curve_id"]
    positions = bridge["onb_gamma_frobenius_coordinate_cycle"]
    assert sorted(positions) == list(range(n))
    left_images = bridge["onb_to_poly_basis_images"]
    right_images = bridge["poly_to_onb_basis_images"]
    output_poly = int(inp["right_output_x_poly_decimal"])
    assert experiment.xor_images(int(inp["right_output_x_onb_decimal"]),
                                 left_images) == output_poly
    assert experiment.xor_images(output_poly, right_images) == int(
        inp["right_output_x_onb_decimal"])
    seen: set[tuple[int, int]] = set()
    hits = result["recorded_hits"]
    assert len(hits) == min(inp["max_recorded_hits"], result[
        "unique_unordered_weight_pairs"])
    for hit in hits:
        left = int(hit["left_x_poly_decimal"])
        right = int(hit["right_x_poly_decimal"])
        left_mask = int(hit["left_cycle_mask_decimal"])
        right_mask = int(hit["right_cycle_mask_decimal"])
        assert 0 < left < 1 << n and 0 < right < 1 << n
        assert 0 < left_mask <= right_mask < 1 << n
        assert left_mask.bit_count() <= weight
        assert right_mask.bit_count() <= weight
        assert to_cycle(experiment.xor_images(left, right_images), positions) == left_mask
        assert to_cycle(experiment.xor_images(right, right_images), positions) == right_mask
        assert exact_s3(left, output_poly, right, n,
                        inp["polynomial_low_terms"]) == 0
        pair = (left_mask, right_mask)
        assert pair not in seen
        seen.add(pair)
    assert result["unique_unordered_weight_pairs"] >= len(hits)
    baseline = json.loads((experiment.BASELINE / "runs" /
                           f"{name}.scan.json").read_text())
    for key in ("field_degree", "curve_id", "workload_id", "kind",
                "right_output_x_poly_decimal", "eligible_nonzero_masks",
                "scan_window_size", "scanned_masks", "status",
                "unique_unordered_weight_pairs"):
        assert result[key] == baseline[key], (name, key)
    assert {(hit["left_x_poly_decimal"], hit["right_x_poly_decimal"])
            for hit in result["recorded_hits"]} == {
                (hit["left_x_poly_decimal"], hit["right_x_poly_decimal"])
                for hit in baseline["recorded_hits"]}
    return {
        "cell": name, "curve_id": inp["curve_id"],
        "workload_id": inp["workload_id"],
        "status": result["status"], "stop_reason": result["stop_reason"],
        "scanned_masks": scanned, "eligible_masks": mask_count,
        "scan_wall_seconds": int(result["timing_ns"]["scan"]) / 1e9,
        "root_calls": ops["s3_root_calls"],
        "field_mul_calls": ops["field_mul_calls"],
        "field_inv_calls": ops["field_inv_calls"],
        "unique_weight_pairs": result["unique_unordered_weight_pairs"],
        "recorded_hits": len(hits),
        "peak_rss_bytes": result["peak_rss_bytes"],
    }


def main() -> None:
    frozen = experiment.check_freeze()
    rows = [one(experiment.cell_name(n, kind, window), frozen)
            for n in experiment.DEGREES
            for kind in experiment.KINDS
            for window in experiment.WINDOWS]
    assert len(rows) == 8
    summary = {
        "schema": "q20261010111900-verification-v1",
        "freeze_sha256": experiment.sha(HERE / "freeze.json"),
        "all_eight_cells_checked": True,
        "rows": rows,
    }
    experiment.write_json(HERE / "verification.json", summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
