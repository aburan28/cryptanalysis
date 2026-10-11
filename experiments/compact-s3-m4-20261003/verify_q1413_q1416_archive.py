#!/usr/bin/env python3
"""Portable archive check for Q1413-Q1416; no solver or full enumeration run."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from pathlib import Path

from build_q1415_stage_comparison import build as build_q1415
from derive_q1413_base_calls import build as build_calls
from run_probe import HERE, ROOT, sha
from screen_q1414_exact_uniform_query_bound import build as build_q1414
from screen_q1416_exact_pair_index import build as build_q1416


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    q13_path = HERE / "q1413_projected_x_protocol.json"
    q13 = read(q13_path)
    runtime = HERE / "q1413_sage_runtime_info.json"
    source = HERE / "enumerate_q1413_projected_x.py"
    assert q13["proposal_id"] == "Q1413" and q13["candidate_id"] is None
    assert q13["source_sha256"] == sha(source)
    assert q13["runtime_info_sha256"] == sha(runtime)
    assert read(runtime)["status"] == "verified"
    assert q13["parent_protocol_sha256"] == sha(HERE / "protocol.json")
    assert q13["reference_artifact_sha256"] == {
        "q1302": sha(HERE / "bases/n83_weight4_orbits.json.gz"),
        "q1325": sha(HERE / "bases/n83_weight5_full_point_orbits.bin"),
    }
    for relative, digest in q13["dependency_sha256"].items():
        assert sha(ROOT / relative) == digest

    bases = {}
    for grid in q13["run_grid"]:
        n, weight = grid["n"], grid["weight"]
        path = HERE / "runs" / f"n{n}_q1413_projected_x_w{weight}.json"
        row = read(path)
        bases[n, weight] = row
        assert row["proposal_id"] == "Q1413"
        assert row["candidate_id"] is None and row["isogeny"] == "none"
        assert row["curve_id"] == q13["instances"][str(n)]["curve_id"]
        assert row["field_degree_n"] == n
        assert row["normal_basis_weight_bound"] == weight
        assert row["source_sha256"] == q13["source_sha256"]
        assert row["protocol_sha256"] == sha(q13_path)
        assert row["runtime_info_sha256"] == sha(runtime)
        assert row["actual_usable_points_B_before_folding"] == (
            2 * n * row["signed_frobenius_columns_K"])
        assert len(row["strata"]) == weight
        assert row["nominal_x_mask_count"] == sum(
            math.comb(n, w) for w in range(1, weight + 1))
        assert sum(s["rational_x_orbits"] - s["identity_projection_orbits"]
                   - s["duplicate_projection_orbits"] for s in row["strata"]) == (
            row["signed_frobenius_columns_K"])
        for w, stratum in enumerate(row["strata"], 1):
            assert stratum["weight"] == w
            assert stratum["x_orbits"] == math.comb(n, w) // n
        assert row["n83_reference_set_equal"] == (n == 83)
        if n == 83:
            reference = "q1302" if weight == 4 else "q1325"
            assert row["n83_reference_artifact_sha256"] == q13[
                "reference_artifact_sha256"][reference]

    assert bases[83, 4]["signed_frobenius_columns_K"] == 11651
    assert bases[83, 5]["signed_frobenius_columns_K"] == 186612
    prefix, full = bases[131, 5], bases[131, 6]
    assert full["strata"][:5] == prefix["strata"]
    assert full["actual_usable_points_B_before_folding"] == 6559634788
    assert full["signed_frobenius_columns_K"] == 25036774
    assert full["enumerated_set_sha256"] == (
        "e5f66c3944069924b9af7b8c22887e216702c8ac11a3a2ad072437e7d81ecb3b")
    replay = read(HERE / "runs/n131_q1413_sage_projection_replay.json")
    assert replay["status"] == "PASS" and replay["proposal_id"] == "Q1413"
    assert replay["producer_source_sha256"] == sha(source)
    assert replay["source_sha256"] == sha(HERE / "verify_q1413_projection_sage.py")
    assert replay["q1413_protocol_sha256"] == sha(q13_path)
    assert replay["runtime_info_sha256"] == sha(runtime)
    assert sum(s["sampled_supports"] for s in replay["rows"]) == 80
    assert replay["independent_subgroup_checks"] == 16

    for filename, builder in (
        ("q1413_exact_base_api_call_vectors.json", build_calls),
        ("n131_q1414_exact_uniform_query_bound.json", build_q1414),
        ("n131_q1416_exact_base_pair_index_screen.json", build_q1416),
    ):
        assert read(HERE / "runs" / filename) == builder()
    q14 = read(HERE / "runs/n131_q1414_exact_uniform_query_bound.json")
    q16 = read(HERE / "runs/n131_q1416_exact_base_pair_index_screen.json")
    for row in (q14, q16):
        assert row["base_set_sha256"] == full["enumerated_set_sha256"]
        assert row["base_receipt_sha256"] == sha(
            HERE / "runs/n131_q1413_projected_x_w6.json")
        assert row["complete_solve_work_log2"] is None
        assert row["challenge_dispatch_allowed"] is False

    q15_path = HERE / "q1415_gauss_n53_protocol.json"
    q15 = read(q15_path)
    receipt_path = HERE / "runs/n53_q1415_gauss_ordinary.json"
    receipt = read(receipt_path)
    parent = read(HERE / "runs/n53_q1410_ordinary.json")
    stdout_path = HERE / "runs/n53_q1415_gauss_ordinary.stdout.txt"
    stderr_path = HERE / "runs/n53_q1415_gauss_ordinary.stderr.txt"
    formula = HERE / "runs/n53_q1410_ordinary.xcnf.gz"
    assert q15["proposal_id"] == receipt["proposal_id"] == "Q1415"
    assert receipt["candidate_id"] is None and receipt["run_id"] is None
    assert q15["source_sha256"] == sha(HERE / "run_q1415_gauss_n53.py")
    assert q15["parent_protocol_sha256"] == sha(
        HERE / "q1410_balanced_s3_n53_protocol.json")
    assert q15["parent_run_sha256"] == sha(HERE / "runs/n53_q1410_ordinary.json")
    assert q15["solver_binary_sha256"] == receipt["solver_binary_sha256"] == (
        parent["solver_binary_sha256"])
    assert q15["formula_archive_sha256"] == receipt["formula_archive_sha256"] == sha(formula)
    assert receipt["protocol_sha256"] == sha(q15_path)
    assert receipt["runtime_info_sha256"] == q15["runtime_info_sha256"] == sha(
        HERE / "q1415_sage_runtime_info.json")
    assert receipt["solver_stdout_sha256"] == sha(stdout_path)
    assert receipt["solver_stderr_sha256"] == sha(stderr_path)
    digest = hashlib.sha256()
    length = 0
    with gzip.open(formula, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            length += len(chunk)
    assert digest.hexdigest() == q15["formula_raw_sha256"]
    assert length == q15["formula_raw_bytes"]
    assert receipt["solver_status"] == "external_timeout"
    assert receipt["solver_wall_seconds_exploratory"] >= 120
    assert receipt["observed_verified_relation_count"] == 0
    assert receipt["complete_solve_work_log2"] is None
    stdout = stdout_path.read_text()
    assert re.search(r"Using [1-9][0-9]* matrices recovered", stdout)
    assert not re.search(r"^s (UN)?SATISFIABLE", stdout, re.MULTILINE)
    assert read(HERE / "runs/n53_q1410_q1415_named_stage_comparison.json") == (
        build_q1415())
    print(json.dumps({"status": "PASS", "base_receipts": len(bases),
                      "n131_full_B": full["actual_usable_points_B_before_folding"],
                      "q1415_status": receipt["solver_status"]}))


if __name__ == "__main__":
    main()
