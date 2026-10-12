#!/usr/bin/env python3
"""Read-only validation of Q1505 archived scans and model arithmetic."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    p, build, result, control, analysis, probe = (
        read(HERE / name) for name in ("protocol.json", "build_receipt.json",
                                      "result.json", "control_result.json",
                                      "analysis.json", "paired_probe.json"))
    source = HERE / "native_deferred_y.cpp"
    base = PARENT / "bases/n83_weight5_full_point_orbits.bin"
    inputs = PARENT / "q20261012_n83_complement_pair_probe/frozen_inputs.json"
    baseline = PARENT / "q20261012_n83_signed_pair_batch/result.json"
    q1504 = PARENT / "q20261012_n131_w6_direct_scan_budget/analysis.json"
    q1447 = PARENT / "q20261011_weight7_screen/measurement.json"
    assert sha(source) == p["native_source_sha256"] == build["native_source_sha256"]
    assert sha(base) == p["base_point_file_sha256"] == control["base_sha256"]
    assert sha(inputs) == p["frozen_inputs_sha256"] == probe["inputs_sha256"]
    assert sha(baseline) == p["baseline_result_sha256"]
    assert sha(HERE / "protocol.json") == result["protocol_sha256"]
    assert sha(HERE / "result.json") == analysis["result_sha256"]
    assert sha(q1504) == analysis["q1504_analysis_sha256"]
    assert sha(q1447) == analysis["q1447_measurement_sha256"]
    assert sha(HERE / "control.py") == control["control_source_sha256"]
    assert sha(HERE / "paired_probe.py") == probe["source_sha256"]
    assert result["candidate_id"] is None and result["run_id"] is None
    assert analysis["complete_n131_solve_work_log2"] is None
    assert len(result["rows"]) == 12
    assert sum(r["batch_pairs"] == 512 for r in result["rows"]) == 8
    assert {r["batch_pairs"] for r in result["rows"]} == {128, 512, 2048}
    baseline_rows = read(baseline)["rows"]
    for row in result["rows"]:
        assert row["status"] == "COMPLETE" and row["return_code"] == 0
        ref = next(r for r in baseline_rows if r["input"] == row["input"]
                   and r["complement_index"] == row["complement_index"])
        assert row["baseline_checksum_hex"] == ref["result"]["checksum_hex"]
        assert row["result"]["checksum_hex"] == row["baseline_checksum_hex"]
        assert row["result"]["hits"] == row["baseline_hits"] == 0
        assert row["result"]["exceptional_pairs"] == 0
        assert row["result"]["scanned"] == p["factor_base_actual_B"]
        assert row["hits"] == []
    assert {r["sign"] for r in control["controls"]} == {0, 1}
    for row in control["controls"]:
        assert f'hit 0 {row["sign"]} ' in row["native_stdout"]
        assert row["native_result"]["hits"] >= 1
    assert len(probe["rows"]) == 4
    assert [r["binary"] for r in probe["rows"]] == [
        "native_signed", "native_deferred_y", "native_deferred_y", "native_signed"]
    assert len({r["checksum_hex"] for r in probe["rows"]}) == 1
    b83 = p["factor_base_actual_B"]
    assert analysis["n83_four_sign_full_scan_mul_calls_before"] == 14 * b83
    assert analysis["n83_four_sign_full_scan_mul_calls_after_zero_hits"] == 10 * b83
    b = read(q1504)["actual_usable_points_B_before_folding"]
    k = read(q1504)["folded_columns_K"]
    assert analysis["n131_four_sign_scan_batch_mul_calls_zero_hits"] == 10 * b
    assert analysis["n131_four_sign_scan_batch_sqr_calls_zero_hits"] == 4 * b
    assert analysis["n131_four_sign_scan_batch_inversions_at_512_pairs"] == 4 * math.ceil((b // 2) / 512)
    order = int(analysis["independent_uniform_first_pair_model"]["subgroup_order"])
    assert order == int(read(q1447)["subgroup_order_r"])
    pair_ceiling = b * (b + 1) // 2
    model = analysis["independent_uniform_first_pair_model"]
    assert model["unordered_second_pairs_ceiling"] == pair_ceiling
    assert model["four_sign_hit_probability_upper_numerator"] == 4 * pair_ceiling
    assert model["four_sign_hit_probability_upper_denominator"] == str(order - 1)
    exponent = math.log2(k) + math.log2(order - 1) - math.log2(4 * pair_ceiling) + math.log2(10 * b)
    assert math.isclose(model["expected_batch_mul_calls_for_K_hits_lower_log2"], exponent, abs_tol=1e-12)
    print("PASS Q1505 deferred-y scans, signed controls, frozen inputs, N131 scenarios")


if __name__ == "__main__":
    main()
