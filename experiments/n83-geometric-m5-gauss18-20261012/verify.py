#!/usr/bin/env python3
"""Audit the frozen one-matrix pilot, control and raw solver outputs."""

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
    assert protocol["proposal_id"] == "Q2026101262"
    assert protocol["candidate_id"] is None
    assert protocol["workload_id"] == "df4396f4d8fc"
    assert protocol["max_conflicts"] == 300000
    assert protocol["run_order"] == ["default", "gauss", "gauss", "default"]
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for config in protocol["solvers"].values():
        assert sha(Path(config["path"])) == config["sha256"]
    assert sha(PARENT / "protocol.json") == protocol[
        "parent_protocol_sha256"]
    assert sha(PARENT / "width18_ordinary.json") == protocol[
        "parent_result_sha256"]
    compressed = PARENT / "width18.attempt0.xcnf.gz"
    assert sha(compressed) == protocol["formula_gzip_sha256"]
    with gzip.open(compressed, "rb") as stream:
        assert hashlib.sha256(stream.read()).hexdigest() == protocol[
            "formula_raw_sha256"]
    assert sha(HERE / "preflight.stdout.txt") == protocol[
        "preflight_stdout_sha256"]
    assert "Using 1 matrices" in (HERE / "preflight.stdout.txt").read_text()
    result = json.loads((HERE / "pilot_result.json").read_text())
    assert result["status"] in ("bounded_unknown", "verified_relation")
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["runner_sha256"] == sha(HERE / "pilot.py")
    assert result["formula_raw_sha256"] == protocol["formula_raw_sha256"]
    assert result["run_order"] == protocol["run_order"]
    assert result["B"] == 21714958 and result["K"] == 130813
    for arm in result["arms"]:
        assert arm["variant"] == protocol["run_order"][arm["index"]]
        stdout = HERE / arm["stdout_file"]
        assert sha(stdout) == arm["stdout_sha256"]
        assert sha(HERE / arm["stderr_file"]) == arm["stderr_sha256"]
        if arm["variant"] == "gauss":
            assert "Using 1 matrices" in stdout.read_text()
    control = json.loads((HERE / "karatsuba_control.json").read_text())
    assert control["status"] == "PASS"
    assert control["solver_variant"] == "gauss"
    assert control["replay"]["status"] == "verified_five_point_relation"
    assert control["control_wrapper_source_sha256"] == sha(
        HERE / "control.py")
    assert control["solver_wrapper_sha256"] == sha(HERE / "gauss_one.sh")
    assert control["stdout_sha256"] == sha(
        HERE / "karatsuba_control.stdout.txt")
    assert control["stderr_sha256"] == sha(
        HERE / "karatsuba_control.stderr.txt")
    sage = json.loads((HERE / "sage_relation_replay.json").read_text())
    assert sage["status"] == "PASS"
    assert sage["protocol_sha256"] == sha(protocol_path)
    print(json.dumps({"status": "PASS", "proposal_id": protocol["proposal_id"],
                      "arm_count": len(result["arms"]),
                      "pilot_status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
