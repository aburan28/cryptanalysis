#!/usr/bin/env python3
"""Check frozen inputs, bounded statuses, and independently replayed row."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "n41_n131_zero_sum_joint_20261009"))
from run import verify_formula


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(relative):
    return json.loads((HERE / relative).read_text())


def check_hashes(receipt, paths):
    for key, relative in paths.items():
        assert receipt["sha256"][key] == sha(HERE / relative), key


def main():
    protocol = load("protocol.json")
    assert protocol["status"] == "FROZEN_FORWARD"
    for key, relative in protocol["files"].items():
        assert protocol["sha256"][key] == sha(HERE / relative), key
    chart = load("forward_chart.json")
    assert chart["status"] == "PASS_FORWARD_ROOT_CHART"
    assert chart["target"] == protocol["target"]
    for mode in ("public", "control", "chart"):
        build = load(f"{mode}_build.json")
        assert build["sha256"]["formula"] == sha(HERE / f"{mode}.xcnf")
    recovered = load("chart/recovered_result.json")
    assert recovered["status"] == "RECOVERED_CHART_MODEL"
    check_hashes(recovered, {"source": "recover_chart.py",
                             "protocol": "protocol.json",
                             "forward_chart": "forward_chart.json",
                             "formula": "chart.xcnf",
                             "stdout": "chart/stdout.txt",
                             "model_bits": "chart/model_bits.txt"})
    assert recovered["model_masks"] == chart["source_masks"]
    assert recovered["model_pair_u"] == chart["pair_u"]
    assert recovered["model_block_u"] == chart["block_u"]
    assert recovered["model_root_branch_bits"] == chart["root_branch_bits"]
    assert recovered["model_target_fiber_index"] == chart["target_fiber_index"]
    bits = (HERE / "chart/model_bits.txt").read_text().strip()
    assert verify_formula(HERE / "chart.xcnf", bits)[0]
    audit = load("chart/recovered_audit.json")
    assert audit["status"] == "VERIFIED_RAW_ROW"
    assert len(audit["row"]) == 12
    assert len({item["column"] for item in audit["row"]}) == 12
    check_hashes(audit, {"source": "audit_recovered_chart.py",
                         "runtime": "sage_runtime_info.json",
                         "protocol": "protocol.json",
                         "producer_result": "chart/recovered_result.json"})
    control = load("control/result.json")
    assert control["status"] == "BOUNDED_UNKNOWN"
    assert control["stop_reason"] == "WALL_CAP"
    assert control["solver_wall_ns"] <= 70_000_000_000
    check_hashes(control, {"protocol": "protocol.json",
                           "formula": "control.xcnf",
                           "stdout": "control/stdout.txt",
                           "stderr": "control/stderr.txt"})
    control_audit = load("control/audit.json")
    assert control_audit["status"] == "NO_MODEL"
    assert control_audit["producer_status"] == "BOUNDED_UNKNOWN"
    check_hashes(control_audit, {"source": "audit_forward.py",
                                 "runtime": "sage_runtime_info.json",
                                 "protocol": "protocol.json",
                                 "producer_result": "control/result.json"})
    branch_build = load("branch_probe_build.json")
    assert branch_build["pinned_root_bits"] == 8
    check_hashes(branch_build, {"source": "branch_probe_build.py",
                                "runner": "branch_probe_run.py",
                                "parent_protocol": "protocol.json",
                                "control_formula": "control.xcnf",
                                "control_build": "control_build.json",
                                "chart": "forward_chart.json",
                                "formula": "branch_probe.xcnf"})
    branch = load("branch_probe/result.json")
    assert branch["status"] == "SAT_MODEL" and branch["chart_match"]
    check_hashes(branch, {"source": "branch_probe_run.py",
                          "parent_protocol": "protocol.json",
                          "build": "branch_probe_build.json",
                          "formula": "branch_probe.xcnf",
                          "stdout": "branch_probe/stdout.txt",
                          "stderr": "branch_probe/stderr.txt",
                          "model_bits": "branch_probe/model_bits.txt"})
    bits = (HERE / "branch_probe/model_bits.txt").read_text().strip()
    assert verify_formula(HERE / "branch_probe.xcnf", bits)[0]
    assert not (HERE / "public").exists()
    print("PASS_FROZEN_FORWARD_DIAGNOSTICS")


if __name__ == "__main__":
    main()
