#!/usr/bin/env python3
"""Audit frozen N83 flattened-XOR control and paired solver pilot."""

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101257"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["run_order"] == ["pairwise", "flattened",
                                     "flattened", "pairwise"]
    assert protocol["solver"]["max_conflicts"] == 300000
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(Path(protocol["solver"]["path"])) == protocol[
        "solver"]["sha256"]
    assert sha(PARENT / "protocol.json") == protocol["parent_protocol_sha256"]
    parent_result_path = PARENT / "width18_ordinary.json"
    parent_result = json.loads(parent_result_path.read_text())
    assert sha(parent_result_path) == protocol["parent_result_sha256"]
    assert sha(PARENT / "karatsuba_control.json") == protocol[
        "parent_control_sha256"]
    assert sha(PARENT / "sage_relation_replay.json") == protocol[
        "parent_sage_replay_sha256"]
    assert sha(HERE / "shape_screen.json") == protocol[
        "shape_screen_sha256"]
    screen = json.loads((HERE / "shape_screen.json").read_text())
    assert screen["selfcheck"]["status"] == "PASS"
    assert screen["karatsuba"]["variables"] == 40905
    assert screen["reference"]["variables"] == 75783
    control_path = HERE / "karatsuba_control.json"
    assert sha(control_path) == protocol["control_receipt_sha256"]
    control = json.loads(control_path.read_text())
    assert control["status"] == "PASS"
    assert control["solver_status"] == "sat"
    assert control["replay"]["status"] == "verified_five_point_relation"
    assert control["stdout_sha256"] == sha(HERE /
                                             "karatsuba_control.stdout.txt")
    assert control["stderr_sha256"] == sha(HERE /
                                             "karatsuba_control.stderr.txt")
    result_path = HERE / "pilot_result.json"
    result = json.loads(result_path.read_text())
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runner_sha256"] == sha(HERE / "pilot.py")
    assert result["field_selfcheck"]["status"] == "PASS"
    assert result["workload_id"] == protocol["workload_id"]
    assert result["public_point_onb_raw"] == protocol[
        "workload"]["public_point_onb_raw"]
    assert result["B"] == 21714958 and result["K"] == 130813
    assert result["target_choice"] == 0
    assert result["target_x"] == parent_result["formula_target_x"]
    assert result["shapes"] == {
        "pairwise": screen["reference"],
        "flattened": screen["karatsuba"],
    }
    assert result["run_order"] == protocol["run_order"]
    assert result["status"] in ("verified_relation", "bounded_unknown")
    assert (result["verified_relation"] is not None) == (
        result["status"] == "verified_relation")
    for variant, metadata in result["formula_inputs"].items():
        assert variant in ("pairwise", "flattened")
        assert metadata["raw_sha256"] == metadata["xcnf_raw_sha256"]
        compressed = HERE / metadata["xcnf_gzip"]
        assert metadata["xcnf_gzip_sha256"] == sha(compressed)
        with gzip.open(compressed, "rb") as stream:
            raw = stream.read()
        assert len(raw) == metadata["bytes"] == metadata["xcnf_raw_bytes"]
        assert hashlib.sha256(raw).hexdigest() == metadata["raw_sha256"]
    assert result["formula_inputs"]["pairwise"]["raw_sha256"] == (
        parent_result["attempts"][0]["xcnf_raw_sha256"])
    assert [a["variant"] for a in result["arms"]] == protocol[
        "run_order"][:len(result["arms"])]
    for arm in result["arms"]:
        assert arm["stdout_sha256"] == sha(HERE / arm["stdout_file"])
        assert arm["stderr_sha256"] == sha(HERE / arm["stderr_file"])
    print(json.dumps({"status": "PASS", "proposal_id": protocol["proposal_id"],
                      "pilot_status": result["status"],
                      "arm_count": len(result["arms"])}, sort_keys=True))


if __name__ == "__main__":
    main()
