#!/usr/bin/env python3
"""Check frozen inputs, negative evidence, and the Karatsuba stage receipt."""

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
    assert protocol["proposal_id"] == "Q2026101253"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["limits"]["wall_seconds_per_base"] == 600
    assert protocol["solver"]["threads"] == 1
    assert protocol["solver"]["max_conflicts"] == 5000000
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(Path(protocol["solver"]["path"])) == protocol[
        "solver"]["sha256"]
    parent = HERE.parent / "n83-geometric-m5-fixedtarget16-20261012"
    assert sha(parent / "protocol.json") == protocol[
        "fixedtarget_protocol_sha256"]
    assert sha(parent / "width16_ordinary.json") == protocol[
        "fixedtarget_result_sha256"]
    control_path = HERE / "karatsuba_control.json"
    assert sha(control_path) == protocol["control_receipt_sha256"]
    control = json.loads(control_path.read_text())
    assert control["status"] == "PASS"
    assert control["solver_status"] == "sat"
    assert control["selfcheck"]["status"] == "PASS"
    assert control["replay"]["status"] == "verified_five_point_relation"
    assert control["stdout_sha256"] == sha(
        HERE / "karatsuba_control.stdout.txt")
    assert control["stderr_sha256"] == sha(
        HERE / "karatsuba_control.stderr.txt")
    old_protocol_path = HERE / "protocol_Q2026101252_predriver.json"
    failure = json.loads((HERE / "predriver_failure.json").read_text())
    assert failure["proposal_id"] == "Q2026101252"
    assert failure["phase"] == "formula_build"
    assert failure["solver_started"] is False
    assert failure["protocol_sha256"] == sha(old_protocol_path)
    assert failure["ordinary_source_sha256"] == json.loads(
        old_protocol_path.read_text())["source_sha256"][
            "experiments/n83-geometric-m5-topology16-20261012/ordinary.py"]
    summary = json.loads((HERE / "run_summary.json").read_text())
    result_path = HERE / "width16_ordinary.json"
    result = json.loads(result_path.read_text())
    assert summary["protocol_sha256"] == sha(protocol_path)
    assert summary["result_sha256"]["16"] == sha(result_path)
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runner_sha256"] == sha(HERE / "ordinary.py")
    assert result["field_multiplier_sha256"] == sha(HERE / "karatsuba.py")
    assert result["field_multiplier_selfcheck"]["status"] == "PASS"
    assert result["workload_id"] == protocol["workload_id"]
    assert result["public_point_onb_raw"] == protocol[
        "workload"]["public_point_onb_raw"]
    row = protocol["base_rows"][0]
    assert result["B"] == row["B"] == 5419568
    assert result["K"] == row["K"] == 32648
    assert result["base_sha256"] == row["base_sha256"]
    assert result["raw_target_preimage_count"] == 332
    assert result["formula_target_choice"] == 0
    assert result["formula_shape"]["and_gates"] == 12138
    assert result["formula_shape"]["cnf_clauses"] == 105143
    assert result["status"] in ("verified_relation", "bounded_unknown",
                                "invalid_models_cap", "unsat")
    assert (result["verified_relation"] is not None) == (
        result["status"] == "verified_relation")
    phases = result["online_pdp_phase_ns"]
    assert abs(sum(phases.values()) - result[
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
                      "control_status": control["status"],
                      "predriver_failure_preserved": True}, sort_keys=True))


if __name__ == "__main__":
    main()
