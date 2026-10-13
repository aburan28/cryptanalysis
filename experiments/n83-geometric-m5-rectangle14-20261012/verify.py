#!/usr/bin/env python3
"""Verify normalized N83 rectangle PDP receipts and frozen input hashes."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODEGEN = ROOT / "ecc2k130/runner/codegen"
sys.path.insert(0, str(CODEGEN))

import curves  # noqa: E402
import field  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101291"
    assert protocol["candidate_id"] is None
    parent_path = ROOT / "experiments/n83-geometric-m5-normalized14-20261012/protocol.json"
    parent = json.loads(parent_path.read_text())
    assert protocol["parent_protocol_sha256"] == sha(parent_path)
    assert protocol["workload_id"] == parent["workload_id"]
    assert protocol["workload"] == parent["workload"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    base = ROOT / "experiments/n83-geometric-rectangle14-20261012"
    receipt_path = ROOT / protocol["base_receipt_file"]
    basis_path = ROOT / protocol["basis_manifest_file"]
    assert sha(receipt_path) == protocol["base_receipt_sha256"]
    assert sha(basis_path) == protocol["basis_manifest_sha256"]
    assert sha(base / "independent_sage_replay.json") == protocol["base_replay_sha256"]
    identity_path = ROOT / "experiments/koblitz-pair-claw-20260929/runs/n83_knownlog_orbit_base_k48194.json"
    assert sha(identity_path) == protocol["curve_identity_sha256"]
    model = json.loads(identity_path.read_text())["curve_identity_record"]["curve"]
    order = model["subgroup_order"]
    replay = json.loads((base / "independent_sage_replay.json").read_text())
    assert replay["status"] == "PASS"
    assert replay["folded_columns_K"] == 8532
    basis = json.loads(basis_path.read_text())
    assert basis["effective_columns_K"] == 8532
    assert basis["actual_subgroup_points_B"] == 1416312
    prior_result = json.loads((parent_path.parent / "width14_ordinary.json").read_text())
    assert sha(parent_path.parent / "width14_ordinary.json") == protocol["parent_ordinary_result_sha256"]
    assert prior_result["workload_id"] == protocol["workload_id"]
    assert prior_result["public_point_onb_raw"] == protocol["workload"]["public_point_onb_raw"]
    workload = protocol["workload"]
    assert hashlib.sha256(canonical(workload)).hexdigest()[:12] == protocol[
        "workload_id"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    public = tuple(workload["public_point_onb_raw"])
    assert curve.onCurve(public)
    assert curve.mul(public, order) is None
    summary = json.loads((HERE / "run_summary.json").read_text())
    assert summary["protocol_sha256"] == sha(protocol_path)
    assert summary["run_order"] == protocol["run_order"]
    observed = {}
    for dimension in protocol["run_order"]:
        row = next(row for row in protocol["base_rows"]
                   if row["dimension"] == dimension)
        base = ROOT / row["base_file"]
        assert sha(base) == row["base_sha256"]
        assert base.stat().st_size == 21 * row["K"]
        result_path = HERE / f"width{dimension}_ordinary.json"
        assert sha(result_path) == summary["result_sha256"][str(dimension)]
        result = json.loads(result_path.read_text())
        assert result["status"] in ("verified_relation", "bounded_unknown",
                                    "invalid_models_cap", "unsat")
        assert result["proposal_id"] == protocol["proposal_id"]
        assert result["curve_id"] == protocol["curve_id"]
        assert result["workload_id"] == protocol["workload_id"]
        assert result["dimension"] == dimension
        assert result["K"] == row["K"] and result["B"] == row["B"]
        assert result["basis_onb_coordinates"] == row["basis_onb_coordinates"]
        assert result["formula_shape"]["and_gates"] > prior_result["formula_shape"]["and_gates"]
        assert result["formula_shape"]["variables"] > prior_result["formula_shape"]["variables"]
        assert result["base_sha256"] == row["base_sha256"]
        assert result["public_point_onb_raw"] == workload[
            "public_point_onb_raw"]
        assert result["raw_target_preimage_count"] == 332
        assert result["raw_target_x_sha256"] == prior_result["raw_target_x_sha256"]
        assert result["protocol_sha256"] == sha(protocol_path)
        assert result["runner_sha256"] == sha(HERE / "run.py")
        assert (result["verified_relation"] is not None) == (
            result["status"] == "verified_relation")
        phases = result["online_pdp_phase_ns"]
        assert abs(sum(phases.values()) - result[
            "online_pdp_wall_ns_exploratory"]) < 1_000_000
        assert len(result["attempts"]) <= protocol["limits"][
            "max_models_per_base"]
        for attempt in result["attempts"]:
            assert attempt["stdout_sha256"] == sha(HERE / attempt["stdout_file"])
            assert attempt["stderr_sha256"] == sha(HERE / attempt["stderr_file"])
            compressed = HERE / attempt["xcnf_gzip"]
            assert attempt["xcnf_gzip_sha256"] == sha(compressed)
            with gzip.open(compressed, "rb") as stream:
                raw = stream.read()
            assert len(raw) == attempt["xcnf_raw_bytes"]
            assert hashlib.sha256(raw).hexdigest() == attempt["xcnf_raw_sha256"]
        observed[dimension] = {"status": result["status"],
                               "attempt_statuses": [a["status"] for a in result["attempts"]],
                               "online_seconds": result[
                                   "online_pdp_wall_ns_exploratory"] / 1e9}
    control_path = HERE / "locked_control.json"
    control = json.loads(control_path.read_text())
    assert control["status"] == "PASS"
    assert control["protocol_sha256"] == sha(protocol_path)
    assert control["source_sha256"] == sha(HERE / "control.py")
    assert control["solver_status"] == "sat"
    assert control["replay"]["status"] == "verified_five_point_relation"
    assert control["replay"]["raw_leaf_x"] == control["raw_leaf_x"]
    assert control["replay"]["normalized_raw_leaf_x"] == control[
        "normalized_raw_leaf_x"]
    assert control["replay"]["normalizing_frobenius_power"] == control[
        "normalizing_frobenius_power"]
    assert control["replay"]["public_target"] == control[
        "public_point_onb_raw"]
    onb = field.Onb(83)
    for seed, power, leaf in zip(control["seed_x"],
                                 control["frobenius_powers"],
                                 control["raw_leaf_x"]):
        assert onb.toCoords(onb.frob(onb.fromCoords(seed), power)) == leaf
    row = protocol["base_rows"][0]
    assert [coefficient >> 12 for coefficient in control["seed_coefficients"]] == [0, 1, 2, 3, 0]
    for seed, coefficient in zip(control["seed_x"], control["seed_coefficients"]):
        expected = row["offset_onb_coordinates"] ^ (coefficient & 4095)
        if coefficient & (1 << 12):
            expected ^= row["basis_onb_coordinates"][12]
        if coefficient & (1 << 13):
            expected ^= row["basis_onb_coordinates"][13]
        assert seed == expected
    for original, normalized in zip(control["raw_leaf_x"],
                                    control["normalized_raw_leaf_x"]):
        assert onb.toCoords(onb.frob(
            onb.fromCoords(original),
            control["normalizing_frobenius_power"])) == normalized
    assert control["stdout_sha256"] == sha(HERE / "locked_control.stdout.txt")
    assert control["stderr_sha256"] == sha(HERE / "locked_control.stderr.txt")
    compressed = HERE / control["xcnf_gzip"]
    assert control["xcnf_gzip_sha256"] == sha(compressed)
    with gzip.open(compressed, "rb") as stream:
        raw = stream.read()
    assert len(raw) == control["xcnf_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == control["xcnf_raw_sha256"]
    failed = HERE / "attempt1"
    failed_receipt = json.loads((failed / "locked_control.json").read_text())
    assert failed_receipt["status"] == "FAIL"
    assert failed_receipt["solver_status"] == "sat"
    assert failed_receipt["replay"]["status"] == "invalid_leaf_support"
    assert failed_receipt["protocol_sha256"] == sha(failed / "protocol.json")
    assert failed_receipt["source_sha256"] == sha(failed / "control.py")
    for kind in ("stdout", "stderr"):
        assert failed_receipt[f"{kind}_sha256"] == sha(
            failed / f"locked_control.{kind}.txt")
    assert failed_receipt["xcnf_gzip_sha256"] == sha(
        failed / "locked_control.xcnf.gz")
    domain = json.loads((HERE / "domain_check.json").read_text())
    assert domain["status"] == "PASS"
    assert domain["protocol_sha256"] == sha(protocol_path)
    assert domain["source_sha256"] == sha(HERE / "domain_check.py")
    assert domain["runner_sha256"] == sha(HERE / "run.py")
    assert domain["distinct_affine_seeds"] == 16384
    assert domain["all_affine_seed_memberships"] == "PASS"
    assert domain["sampled_rotated_seed_memberships"] == 83 * len(range(0, 16384, 257))
    assert control["formula_shape"]["and_gates"] == result["formula_shape"]["and_gates"]
    assert control["formula_shape"]["variables"] == result["formula_shape"]["variables"]
    sage = json.loads((HERE / "sage_relation_replay.json").read_text())
    assert sage["status"] == "PASS"
    assert sage["protocol_sha256"] == sha(protocol_path)
    assert sage["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert sage["rows"][-1]["status"] == "PASS"
    print(json.dumps({"status": "PASS", "workload_id": protocol["workload_id"],
                      "widths": observed, "locked_control": "PASS"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
