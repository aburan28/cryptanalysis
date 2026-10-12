#!/usr/bin/env python3
"""Audit frozen width-18 ordered-leaf stage receipts and exact inputs."""

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101264"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["fixed_target_choice"] == 0
    assert protocol["limits"]["wall_seconds_per_base"] == 600
    assert protocol["solver"]["threads"] == 1
    assert protocol["solver"]["max_conflicts"] == 5000000
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(Path(protocol["solver"]["path"])) == protocol[
        "solver"]["sha256"]
    width = ROOT / "experiments/n83-geometric-width17-18-20261012"
    frontier_path = width / "frontier.json"
    replay_path = width / "independent_sage_replay.json"
    assert sha(frontier_path) == protocol["parent_frontier_sha256"]
    assert sha(replay_path) == protocol["parent_sage_replay_sha256"]
    assert json.loads(replay_path.read_text())["status"] == "PASS"
    row = protocol["base_rows"][0]
    assert row["dimension"] == 18
    assert row["B"] == 21714958 and row["K"] == 130813
    base = ROOT / row["base_file"]
    assert sha(base) == row["base_sha256"]
    assert base.stat().st_size == 21 * row["K"]
    cache = ROOT / row["canonical_x_cache_file"]
    assert sha(cache) == row["canonical_x_cache_sha256"]
    assert cache.stat().st_size == 11 * row["K"]
    prior = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"
    assert sha(prior / "protocol.json") == protocol["parent_protocol_sha256"]
    assert sha(prior / "width18_ordinary.json") == protocol["parent_result_sha256"]
    cache_receipt_path = prior / "materialization.json"
    assert sha(cache_receipt_path) == protocol[
        "cache_materialization_sha256"]
    assert json.loads(cache_receipt_path.read_text())["status"] == "PASS"
    parent = ROOT / "experiments/n83-geometric-m5-topology16-20261012"
    assert sha(parent / "protocol.json") == protocol[
        "parent_karatsuba_protocol_sha256"]
    assert sha(parent / "width16_ordinary.json") == protocol[
        "parent_karatsuba_result_sha256"]
    control_path = HERE / "ordered_control.json"
    control = json.loads(control_path.read_text())
    assert sha(control_path) == protocol["control_sha256"]
    assert control["status"] == "PASS"
    assert control["solver_status"] == "sat"
    assert control["selfcheck"]["status"] == "PASS"
    assert control["replay"]["status"] == "verified_five_point_relation"
    assert control["sorted_raw_leaf_x"][1:] == sorted(
        control["sorted_raw_leaf_x"][1:])
    assert control["stdout_sha256"] == sha(
        HERE / "ordered_control.stdout.txt")
    assert control["stderr_sha256"] == sha(
        HERE / "ordered_control.stderr.txt")
    compressed_control = HERE / control["xcnf_gzip"]
    assert control["xcnf_gzip_sha256"] == sha(compressed_control)
    with gzip.open(compressed_control, "rb") as stream:
        control_raw = stream.read()
    assert len(control_raw) == control["xcnf_raw_bytes"]
    assert hashlib.sha256(control_raw).hexdigest() == control["xcnf_raw_sha256"]
    summary = json.loads((HERE / "run_summary.json").read_text())
    result_path = HERE / "width18_ordinary.json"
    result = json.loads(result_path.read_text())
    assert summary["protocol_sha256"] == sha(protocol_path)
    assert summary["result_sha256"]["18"] == sha(result_path)
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runner_sha256"] == sha(HERE / "ordinary.py")
    assert result["ordered_source_sha256"] == sha(HERE / "ordered.py")
    assert result["field_multiplier_selfcheck"]["status"] == "PASS"
    assert result["workload_id"] == protocol["workload_id"]
    assert result["public_point_onb_raw"] == protocol[
        "workload"]["public_point_onb_raw"]
    assert result["B"] == row["B"] and result["K"] == row["K"]
    assert result["base_sha256"] == row["base_sha256"]
    assert result["raw_target_preimage_count"] == 332
    assert result["formula_target_choice"] == 0
    assert result["formula_shape"]["and_gates"] > 12174
    assert result["formula_shape"]["cnf_clauses"] > 105251
    assert result["status"] in ("verified_relation", "bounded_unknown",
                                "invalid_models_cap", "unsat")
    assert (result["verified_relation"] is not None) == (
        result["status"] == "verified_relation")
    assert abs(sum(result["online_pdp_phase_ns"].values()) - result[
        "online_pdp_wall_ns_exploratory"]) < 1_000_000
    for attempt in result["attempts"]:
        assert attempt["stdout_sha256"] == sha(HERE / attempt["stdout_file"])
        assert attempt["stderr_sha256"] == sha(HERE / attempt["stderr_file"])
        compressed = HERE / attempt["xcnf_gzip"]
        assert attempt["xcnf_gzip_sha256"] == sha(compressed)
        with gzip.open(compressed, "rb") as stream:
            raw = stream.read()
        assert len(raw) == attempt["xcnf_raw_bytes"]
        assert hashlib.sha256(raw).hexdigest() == attempt["xcnf_raw_sha256"]
    replay = json.loads((HERE / "sage_relation_replay.json").read_text())
    assert replay["status"] == "PASS"
    assert replay["protocol_sha256"] == sha(protocol_path)
    assert replay["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert replay["rows"][0]["status"] == "PASS"
    assert replay["rows"][0]["result_sha256"] == sha(control_path)
    assert replay["rows"][1]["result_sha256"] == sha(result_path)
    assert replay["rows"][1]["status"] == (
        "PASS" if result["status"] == "verified_relation" else
        "no_relation_to_replay")
    lean_build = (HERE / "lean-build.txt").read_text()
    assert "error:" not in lean_build
    assert lean_build.count("does not depend on any axioms") == 3
    print(json.dumps({"status": "PASS", "proposal_id": protocol["proposal_id"],
                      "ordinary_status": result["status"],
                      "control_status": control["status"],
                      "B": row["B"], "K": row["K"]}, sort_keys=True))


if __name__ == "__main__":
    main()
