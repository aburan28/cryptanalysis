#!/usr/bin/env python3
"""Audit the frozen six-leaf n83 stage and independent replay receipts."""

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_formula_receipt(row):
    compressed = HERE / row["xcnf_gzip"]
    assert sha(compressed) == row["xcnf_gzip_sha256"]
    with gzip.open(compressed, "rb") as stream:
        raw = stream.read()
    assert len(raw) == row["xcnf_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == row["xcnf_raw_sha256"]


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101266"
    assert protocol["candidate_id"] is None
    assert protocol["point_decomposition_summands"] == 6
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["fixed_target_choice"] == 0
    assert protocol["limits"]["wall_seconds_per_base"] == 600
    assert protocol["solver"]["threads"] == 1
    assert protocol["solver"]["max_conflicts"] == 5_000_000
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(Path(protocol["solver"]["path"])) == protocol["solver"]["sha256"]
    width = ROOT / "experiments/koblitz-n83-index-design-20260929/Q20261012_N83_WIDTH_FRONTIER"
    assert sha(width / "frontier.json") == protocol["width11_frontier_sha256"]
    assert sha(width / "independent_sage_replay.json") == protocol[
        "width11_sage_replay_sha256"]
    assert json.loads((width / "independent_sage_replay.json").read_text())["status"] == "PASS"
    row = protocol["base_rows"][0]
    assert row["dimension"] == 11 and row["offset_onb_coordinates"] == 1 << 81
    assert row["B"] == 181936 and row["K"] == 1096
    assert sha(ROOT / row["base_file"]) == row["base_sha256"]
    assert sha(ROOT / row["canonical_x_cache_file"]) == row[
        "canonical_x_cache_sha256"]
    assert (ROOT / row["base_file"]).stat().st_size == 21 * row["K"]
    assert (ROOT / row["canonical_x_cache_file"]).stat().st_size == 11 * row["K"]
    assert sha(HERE / "materialization.json") == protocol[
        "cache_materialization_sha256"]
    assert json.loads((HERE / "materialization.json").read_text())["status"] == "PASS"
    assert sha(HERE / "shape.json") == protocol["shape_sha256"]
    shape = json.loads((HERE / "shape.json").read_text())
    assert shape["status"] == "PASS"
    assert shape["formula_shape"] == protocol["formula_shape"]
    assert shape["target_x_onb"] == protocol["target_x_onb"]
    control_path = HERE / "six_point_control.json"
    control = json.loads(control_path.read_text())
    assert sha(control_path) == protocol["control_sha256"]
    assert control["status"] == "PASS" and control["solver_status"] == "sat"
    assert control["selfcheck"]["status"] == "PASS"
    assert control["m6_source_sha256"] == sha(HERE / "m6.py")
    assert control["control_source_sha256"] == sha(HERE / "control.py")
    assert sha(HERE / "six_point_control.stdout.txt") == control["stdout_sha256"]
    assert sha(HERE / "six_point_control.stderr.txt") == control["stderr_sha256"]
    check_formula_receipt(control)
    prior = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"
    assert sha(prior / "protocol.json") == protocol["parent_protocol_sha256"]
    assert sha(prior / "width18_ordinary.json") == protocol["parent_result_sha256"]
    result_path = HERE / "width11_m6_ordinary.json"
    result = json.loads(result_path.read_text())
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runner_sha256"] == sha(HERE / "ordinary.py")
    assert result["m6_source_sha256"] == sha(HERE / "m6.py")
    assert result["field_multiplier_selfcheck"]["status"] == "PASS"
    assert result["workload_id"] == protocol["workload_id"]
    assert result["B"] == row["B"] and result["K"] == row["K"]
    assert result["base_sha256"] == row["base_sha256"]
    assert result["canonical_x_cache_sha256"] == row["canonical_x_cache_sha256"]
    assert result["formula_target_x"] == protocol["target_x_onb"]
    assert result["formula_shape"] == protocol["formula_shape"]
    assert result["status"] in ("verified_relation", "bounded_unknown",
                                "invalid_models_cap", "restricted_slice_unsat")
    assert (result["verified_relation"] is not None) == (
        result["status"] == "verified_relation")
    assert abs(sum(result["online_pdp_phase_ns"].values()) - result[
        "online_pdp_wall_ns_exploratory"]) < 1_000_000
    for attempt in result["attempts"]:
        assert sha(HERE / attempt["stdout_file"]) == attempt["stdout_sha256"]
        assert sha(HERE / attempt["stderr_file"]) == attempt["stderr_sha256"]
        check_formula_receipt(attempt)
    sage = json.loads((HERE / "independent_sage_replay.json").read_text())
    assert sage["status"] == "PASS"
    assert sage["protocol_sha256"] == sha(protocol_path)
    assert sage["verifier_source_sha256"] == sha(HERE / "verify_sage.py")
    assert sage["rows"][0]["status"] == "PASS"
    assert sage["rows"][0]["result_sha256"] == sha(control_path)
    assert sage["rows"][1]["result_sha256"] == sha(result_path)
    assert sage["rows"][1]["status"] == (
        "PASS" if result["status"] == "verified_relation" else
        "no_relation_to_replay")
    lean = (HERE / "lean-build.txt").read_text()
    assert "error:" not in lean and lean.count("does not depend on any axioms") == 2
    print(json.dumps({"status": "PASS", "proposal_id": protocol["proposal_id"],
                      "ordinary_status": result["status"],
                      "control_status": control["status"],
                      "B": row["B"], "K": row["K"]}, sort_keys=True))


if __name__ == "__main__":
    main()
