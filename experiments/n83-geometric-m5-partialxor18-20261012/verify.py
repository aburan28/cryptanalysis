#!/usr/bin/env python3
"""Audit the frozen partial-XOR pilot and locked relation control."""

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
    assert protocol["proposal_id"] == "Q2026101259"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["solver"]["max_conflicts"] == 1000000
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(Path(protocol["solver"]["path"])) == protocol[
        "solver"]["sha256"]
    assert sha(HERE / "shape_screen.json") == protocol["screen_sha256"]
    assert sha(HERE / "karatsuba_control.json") == protocol[
        "control_sha256"]
    control = json.loads((HERE / "karatsuba_control.json").read_text())
    assert control["status"] == "PASS"
    assert control["replay"]["status"] == "verified_five_point_relation"
    assert sha(ROOT / protocol["base_rows"][0]["base_file"]) == protocol[
        "base_rows"][0]["base_sha256"]
    result = json.loads((HERE / "pilot_result.json").read_text())
    assert result["status"] in ("bounded_unknown", "verified_relation")
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runner_sha256"] == sha(HERE / "pilot.py")
    assert result["run_order"] == protocol["run_order"]
    assert result["B"] == 21714958 and result["K"] == 130813
    assert result["public_point_onb_raw"] == protocol[
        "workload"]["public_point_onb_raw"]
    assert result["shapes"]["partial21"]["variables"] == 45162
    assert result["shapes"]["partial21"]["xor_rows"] == 32316
    assert result["shapes"]["partial21"][
        "xor_literal_occurrences"] == 292011
    assert len(result["arms"]) <= len(protocol["run_order"])
    for arm in result["arms"]:
        assert arm["stdout_sha256"] == sha(HERE / arm["stdout_file"])
        assert arm["stderr_sha256"] == sha(HERE / arm["stderr_file"])
        assert arm["variant"] == protocol["run_order"][arm["index"]]
    for entry in result["formula_inputs"].values():
        compressed = HERE / entry["xcnf_gzip"]
        assert sha(compressed) == entry["xcnf_gzip_sha256"]
        with gzip.open(compressed, "rb") as stream:
            raw = stream.read()
        assert len(raw) == entry["xcnf_raw_bytes"] == entry["bytes"]
        assert hashlib.sha256(raw).hexdigest() == entry["raw_sha256"]
    sage = json.loads((HERE / "sage_relation_replay.json").read_text())
    assert sage["status"] == "PASS"
    assert sage["protocol_sha256"] == sha(protocol_path)
    print(json.dumps({"status": "PASS", "proposal_id": protocol["proposal_id"],
                      "pilot_status": result["status"],
                      "arm_count": len(result["arms"])}, sort_keys=True))


if __name__ == "__main__":
    main()
