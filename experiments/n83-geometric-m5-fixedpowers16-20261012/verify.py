#!/usr/bin/env python3
"""Verify fixed-power N83 width-16 PDP receipts and input hashes."""

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
    assert protocol["proposal_id"] == "Q2026101246"
    assert protocol["candidate_id"] is None
    parent_path = ROOT / "experiments/n83-geometric-m5-normalized15-16-20261012/protocol.json"
    parent = json.loads(parent_path.read_text())
    assert protocol["parent_protocol_sha256"] == sha(parent_path)
    assert protocol["workload_id"] == parent["workload_id"]
    assert protocol["workload"] == parent["workload"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    frontier = ROOT / "experiments/n83-geometric-width15-16-20261012"
    assert sha(frontier / "frontier.json") == protocol["parent_frontier_sha256"]
    assert sha(frontier / "independent_sage_replay.json") == protocol[
        "parent_sage_replay_sha256"]
    identity_path = ROOT / "experiments/koblitz-pair-claw-20260929/runs/n83_knownlog_orbit_base_k48194.json"
    assert sha(identity_path) == protocol["curve_identity_sha256"]
    model = json.loads(identity_path.read_text())["curve_identity_record"]["curve"]
    order = model["subgroup_order"]
    replay = json.loads((frontier / "independent_sage_replay.json").read_text())
    assert replay["status"] == "PASS"
    assert [row["dimension"] for row in replay["results"]] == [15, 16]
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
        assert result["base_sha256"] == row["base_sha256"]
        assert result["fixed_relative_frobenius_powers"] == protocol[
            "fixed_relative_frobenius_powers"]
        assert result["public_point_onb_raw"] == workload[
            "public_point_onb_raw"]
        assert result["raw_target_preimage_count"] == 332
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
    onb = field.Onb(83)
    for dimension in (16,):
        control_path = HERE / "locked_control.json"
        control = json.loads(control_path.read_text())
        assert control["dimension"] == dimension
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
        assert [(power - control["frobenius_powers"][0]) % 83
                for power in control["frobenius_powers"]] == protocol[
                    "fixed_relative_frobenius_powers"]
        for seed, power, leaf in zip(control["seed_x"],
                                     control["frobenius_powers"],
                                     control["raw_leaf_x"]):
            assert onb.toCoords(onb.frob(onb.fromCoords(seed), power)) == leaf
        for original, normalized in zip(control["raw_leaf_x"],
                                        control["normalized_raw_leaf_x"]):
            assert onb.toCoords(onb.frob(
                onb.fromCoords(original),
                control["normalizing_frobenius_power"])) == normalized
        assert control["stdout_sha256"] == sha(
            HERE / "locked_control.stdout.txt")
        assert control["stderr_sha256"] == sha(
            HERE / "locked_control.stderr.txt")
        compressed = HERE / control["xcnf_gzip"]
        assert control["xcnf_gzip_sha256"] == sha(compressed)
        with gzip.open(compressed, "rb") as stream:
            raw = stream.read()
        assert len(raw) == control["xcnf_raw_bytes"]
        assert hashlib.sha256(raw).hexdigest() == control["xcnf_raw_sha256"]
    print(json.dumps({"status": "PASS", "workload_id": protocol["workload_id"],
                      "widths": observed, "locked_control": "PASS"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
