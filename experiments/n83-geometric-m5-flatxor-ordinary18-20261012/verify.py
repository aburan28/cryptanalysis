#!/usr/bin/env python3
"""Audit frozen flattened-XOR ordinary N83 stage and all attempts."""

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"
FLAT = ROOT / "experiments/n83-geometric-m5-flatxor18-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101258"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["fixed_target_choice"] == 0
    assert protocol["solver"]["max_conflicts"] == 5000000
    assert protocol["limits"]["wall_seconds_per_base"] == 600
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(Path(protocol["solver"]["path"])) == protocol[
        "solver"]["sha256"]
    assert sha(PARENT / "protocol.json") == protocol[
        "parent_karatsuba_protocol_sha256"]
    assert sha(PARENT / "width18_ordinary.json") == protocol[
        "parent_karatsuba_result_sha256"]
    assert sha(FLAT / "protocol.json") == protocol[
        "flat_pilot_protocol_sha256"]
    assert sha(FLAT / "pilot_result.json") == protocol[
        "flat_pilot_result_sha256"]
    assert sha(FLAT / "karatsuba_control.json") == protocol[
        "flat_control_sha256"]
    assert sha(FLAT / "sage_relation_replay.json") == protocol[
        "flat_sage_replay_sha256"]
    assert json.loads((FLAT / "karatsuba_control.json").read_text())[
        "status"] == "PASS"
    assert json.loads((FLAT / "sage_relation_replay.json").read_text())[
        "status"] == "PASS"
    row = protocol["base_rows"][0]
    assert row["dimension"] == 18
    assert row["B"] == 21714958 and row["K"] == 130813
    assert sha(ROOT / row["base_file"]) == row["base_sha256"]
    assert sha(ROOT / row["canonical_x_cache_file"]) == row[
        "canonical_x_cache_sha256"]
    summary = json.loads((HERE / "run_summary.json").read_text())
    result_path = HERE / "width18_ordinary.json"
    result = json.loads(result_path.read_text())
    assert summary["protocol_sha256"] == sha(protocol_path)
    assert summary["result_sha256"]["18"] == sha(result_path)
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runner_sha256"] == sha(HERE / "ordinary.py")
    assert result["field_multiplier_sha256"] == sha(
        FLAT / "flat_karatsuba.py")
    assert result["field_multiplier_selfcheck"]["status"] == "PASS"
    assert result["workload_id"] == protocol["workload_id"]
    assert result["public_point_onb_raw"] == protocol[
        "workload"]["public_point_onb_raw"]
    assert result["B"] == row["B"] and result["K"] == row["K"]
    assert result["base_sha256"] == row["base_sha256"]
    assert result["raw_target_preimage_count"] == 332
    assert result["formula_target_choice"] == 0
    shape = result["formula_shape"]
    assert shape["and_gates"] == 12174
    assert shape["cnf_clauses"] == 105251
    assert shape["variables"] == 40905
    assert shape["xor_rows"] == 28059
    assert shape["xor_literal_occurrences"] == 615561
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
    print(json.dumps({"status": "PASS", "proposal_id": protocol["proposal_id"],
                      "ordinary_status": result["status"],
                      "B": row["B"], "K": row["K"]}, sort_keys=True))


if __name__ == "__main__":
    main()
