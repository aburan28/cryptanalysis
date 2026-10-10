#!/usr/bin/env python3
"""Check frozen permutation, full chart model, and bounded paired runs."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_n131_zero_sum_forward_20261009"
JOINT = HERE.parent / "n41_n131_zero_sum_joint_20261009"
sys.path.insert(0, str(JOINT))
from run import verify_formula


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(relative):
    return json.loads((HERE / relative).read_text())


def main():
    protocol = load("protocol.json")
    assert protocol["status"] == "FROZEN_PRIMARY_ORDER"
    for key, relative in protocol["files"].items():
        assert protocol["sha256"][key] == sha(HERE / relative), key
    build = load("build.json")
    assert build["status"] == "BUILT_EXACT_REINDEX"
    assert build["primary_variable_count"] == 68
    original = (SOURCE / "chart/model_bits.txt").read_text().strip()
    ordered = (HERE / "known_model_bits.txt").read_text().strip()
    n = build["formula_variables"]
    primary = build["primary_old_wires"]
    selected = set(primary)
    new_to_old = primary + [i for i in range(1, n + 1)
                            if i not in selected]
    assert len(original) == len(ordered) == len(new_to_old) == n
    assert ordered == "".join(original[old-1] for old in new_to_old)
    for mode in ("control", "public"):
        assert verify_formula(SOURCE / f"{mode}.xcnf", original)[0]
        assert verify_formula(HERE / f"ordered_{mode}.xcnf", ordered)[0]
    statuses = {}
    for mode in protocol["paired_run_order"]:
        receipt = load(f"{mode}/result.json")
        assert receipt["sha256"]["protocol"] == sha(HERE / "protocol.json")
        formula = (SOURCE / "control.xcnf" if mode == "original_control"
                   else HERE / "ordered_control.xcnf")
        assert receipt["sha256"]["formula"] == sha(formula)
        assert receipt["sha256"]["stdout"] == sha(HERE / mode / "stdout.txt")
        assert receipt["sha256"]["stderr"] == sha(HERE / mode / "stderr.txt")
        assert receipt["command"][1:7] == ["--threads=1", "--verb=1",
                                             "--printsol=1", "--renumber=0",
                                             "--branchstr=vmtf", "--maxtime=60"]
        stdout = (HERE / mode / "stdout.txt").read_text()
        assert "c rst " in stdout and "c [branch]" in stdout
        assert receipt["solver_wall_ns"] <= 70_000_000_000
        assert receipt["peak_combined_rss_bytes_sampled"] < 4_294_967_296
        if receipt["status"] == "BOUNDED_UNKNOWN":
            assert receipt["stop_reason"] == "WALL_CAP"
            assert not receipt["solver_status_lines"]
        elif receipt["status"] == "SAT_MODEL":
            bits = (HERE / mode / "model_bits.txt").read_text().strip()
            assert receipt["sha256"]["model_bits.txt"] == sha(HERE / mode / "model_bits.txt")
            assert verify_formula(formula, bits)[0]
            assert load(f"{mode}/audit.json")["status"] == "VERIFIED_RAW_ROW"
        else:
            raise AssertionError((mode, receipt["status"]))
        statuses[mode] = receipt["status"]
    if statuses["ordered_control"] != "SAT_MODEL":
        assert not (HERE / "ordered_public").exists()
    failure = load("audit_launch_failure.json")
    assert failure["status"] == "PRODUCER_FAILURE_AUDIT_CLI"
    assert failure["exit_code"] == 2
    assert "invalid choice" in failure["observed_error"]
    print("PASS_PRIMARY_ORDER_GATE " + json.dumps(statuses, sort_keys=True))


if __name__ == "__main__":
    main()
