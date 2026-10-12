#!/usr/bin/env python3
"""Read-only validation of Q1506 sources, arithmetic and proof receipt."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCES = {
    "w5": PARENT / "runs/n131_q1413_projected_x_w5.json",
    "w6": PARENT / "runs/n131_q1413_projected_x_w6.json",
    "w7_w8": PARENT / "q20261011_weight7_screen/measurement.json",
    "kernel": PARENT / "q20261012_n83_deferred_y_scan/analysis.json",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    protocol, analysis = read(HERE / "protocol.json"), read(HERE / "analysis.json")
    proof = read(HERE / "lean/proof_receipt.json")
    assert {key: sha(path) for key, path in SOURCES.items()} == protocol["source_sha256"]
    assert analysis["source_sha256"] == protocol["source_sha256"]
    assert analysis["protocol_sha256"] == sha(HERE / "protocol.json")
    assert analysis["candidate_id"] is None and analysis["run_id"] is None
    assert analysis["complete_n131_solve_work_log2"] is None
    assert analysis["challenge_dispatch_allowed"] is False
    exact = [read(SOURCES[key]) for key in ("w5", "w6")]
    sampled = read(SOURCES["w7_w8"])
    kernel = read(SOURCES["kernel"])
    order = int(sampled["subgroup_order_r"])
    assert str(order) == protocol["subgroup_order_r"] == analysis["subgroup_order_r"]
    assert [row["weight_bound"] for row in analysis["rows"]] == [5, 6, 7, 8]
    for i, row in enumerate(analysis["rows"]):
        b, k = row["B"], row["K"]
        assert b == 262 * k
        if i < 2:
            source = exact[i]
            assert row["base_status"] == "exact_enumerated"
            assert b == source["actual_usable_points_B_before_folding"]
            assert k == source["signed_frobenius_columns_K"]
            assert row["enumerated_set_sha256"] == source["enumerated_set_sha256"]
        else:
            source = sampled["rows"][i - 1]
            assert row["base_status"] == "sampled_conditional_projection_count"
            assert b == source["conditional_B"] and k == source["conditional_folded_K"]
            assert row["enumerated_set_sha256"] is None
            endpoints = row["conditional_K_interval_endpoints"]
            assert [e["K"] for e in endpoints] == source["conditional_K_interval_from_componentwise_wilson95"]
            assert all(e["B"] == 262 * e["K"] for e in endpoints)
        pair_count = b * (b + 1) // 2
        assert row["four_sign_full_scan_batch_mul_calls_zero_hits"] == 10 * b
        assert row["four_sign_hit_probability_upper_numerator"] == 4 * pair_count
        assert row["four_sign_hit_probability_upper_denominator"] == str(order - 1)
        exponent = math.log2(k) + math.log2(order - 1) - math.log2(4 * pair_count) + math.log2(10 * b)
        assert math.isclose(row["expected_K_unordered_pair_matches_batch_mul_lower_log2_independent_uniform_first_pair"], exponent, abs_tol=1e-12)
        assert row["scalar_sparse_matrix_proxy_modular_operations"] == 4 * k * k
        assert row["four_sign_batch_inversions"] == {
            str(batch): 4 * math.ceil((b // 2) / batch)
            for batch in (128, 512, 2048, 8192)}
    assert analysis["rows"][1]["B"] == kernel["n131_exact_weight6_B"]
    lean = HERE / "lean/ScanWork.lean"
    text = lean.read_text()
    assert sha(lean) == proof["module_sha256"]
    assert all(word not in text for word in ("sorry", "admit", "sorryAx"))
    assert (HERE / "lean/lean-toolchain").read_text().strip() == proof["toolchain"]
    lakefile = HERE / "lean/lakefile.toml"
    assert sha(lakefile) == proof["lakefile_sha256"]
    assert proof["mathlib_git_revision"] in lakefile.read_text()
    assert proof["build_exit_code"] == 0 and proof["proof_status"] == "checked"
    assert sha(HERE / "lean/build.stdout.txt") == proof["build_stdout_sha256"]
    assert sha(HERE / "lean/build.stderr.txt") == proof["build_stderr_sha256"]
    build_output = (HERE / "lean/build.stdout.txt").read_text()
    assert "Q1506.scan_work_identity" in build_output
    assert "Q1506.full_orbit_scan_work" in build_output
    assert "sorryAx" not in build_output
    olean = Path("/private/tmp/q1506_ScanWork.olean")
    if olean.exists():
        assert sha(olean) == proof["olean_sha256"]
    print("PASS Q1506 exact/conditional weight surface and checked Lean receipt")


if __name__ == "__main__":
    main()
