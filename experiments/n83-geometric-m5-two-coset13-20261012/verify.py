#!/usr/bin/env python3
"""Verify two-coset orbit-complete N83 PDP receipts and frozen inputs."""

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
    assert protocol["proposal_id"] == "Q2026101290"
    assert protocol["candidate_id"] is None
    parent_path = ROOT / "experiments/n83-geometric-m5-orbit-20261012/protocol.json"
    parent = json.loads(parent_path.read_text())
    assert protocol["parent_protocol_sha256"] == sha(parent_path)
    assert protocol["workload_id"] == parent["workload_id"]
    assert protocol["workload"] == parent["workload"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    parent_run = ROOT / "experiments/n83-geometric-m5-orbit-20261012/width13_ordinary.json"
    assert sha(parent_run) == protocol["parent_ordinary_result_sha256"]
    prior_result = json.loads(parent_run.read_text())
    base_manifest_path = ROOT / protocol["basis_manifest_file"]
    union_path = ROOT / protocol["union_receipt_file"]
    assert sha(base_manifest_path) == protocol["basis_manifest_sha256"]
    assert sha(union_path) == protocol["union_receipt_sha256"]
    base_manifest = json.loads(base_manifest_path.read_text())
    union = json.loads(union_path.read_text())
    assert base_manifest["effective_columns_K"] == union["best_K"] == 4349
    assert base_manifest["actual_subgroup_points_B"] == union["best_B"] == 721934
    base = ROOT / "experiments/n83-geometric-two-shift12-20261012"
    assert sha(base / "independent_union_sage_replay.json") == protocol[
        "union_replay_sha256"]
    identity_path = ROOT / "experiments/koblitz-pair-claw-20260929/runs/n83_knownlog_orbit_base_k48194.json"
    assert sha(identity_path) == protocol["curve_identity_sha256"]
    model = json.loads(identity_path.read_text())["curve_identity_record"]["curve"]
    order = model["subgroup_order"]
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
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
        assert result["formula_shape"] == prior_result["formula_shape"]
        assert result["base_sha256"] == row["base_sha256"]
        assert result["public_point_onb_raw"] == workload[
            "public_point_onb_raw"]
        assert result["raw_target_preimage_count"] == 4
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
    assert control["replay"]["public_target"] == control[
        "public_point_onb_raw"]
    onb = field.Onb(83)
    row = protocol["base_rows"][0]
    assert [coefficient >> 12 for coefficient in control[
        "seed_coefficients"]] == [0, 1, 0, 1, 0]
    for seed, coefficient, power, leaf in zip(
            control["seed_x"], control["seed_coefficients"],
            control["frobenius_powers"], control["raw_leaf_x"]):
        expected = row["offset_onb_coordinates"] ^ (coefficient & 4095)
        if coefficient & 4096:
            expected ^= row["basis_onb_coordinates"][12]
        assert seed == expected
        assert onb.toCoords(onb.frob(onb.fromCoords(seed), power)) == leaf
    assert control["stdout_sha256"] == sha(HERE / "locked_control.stdout.txt")
    assert control["stderr_sha256"] == sha(HERE / "locked_control.stderr.txt")
    compressed = HERE / control["xcnf_gzip"]
    assert control["xcnf_gzip_sha256"] == sha(compressed)
    with gzip.open(compressed, "rb") as stream:
        raw = stream.read()
    assert len(raw) == control["xcnf_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == control["xcnf_raw_sha256"]
    domain = json.loads((HERE / "domain_check.json").read_text())
    assert domain["status"] == "PASS"
    assert domain["protocol_sha256"] == sha(protocol_path)
    assert domain["source_sha256"] == sha(HERE / "domain_check.py")
    assert domain["runner_sha256"] == sha(HERE / "run.py")
    assert domain["distinct_affine_seeds"] == 8192
    assert domain["all_affine_seed_memberships"] == "PASS"
    assert domain["sampled_rotated_seed_memberships"] == 2656
    prior_control = json.loads((ROOT / "experiments/n83-geometric-m5-orbit-20261012/"
                                "locked_control.json").read_text())
    assert control["formula_shape"] == prior_control["formula_shape"]
    sage = json.loads((HERE / "sage_relation_replay.json").read_text())
    assert sage["status"] == "PASS"
    assert sage["protocol_sha256"] == sha(protocol_path)
    assert sage["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert [row["status"] for row in sage["rows"]][-1] == "PASS"
    print(json.dumps({"status": "PASS", "workload_id": protocol["workload_id"],
                      "widths": observed, "locked_control": "PASS"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
