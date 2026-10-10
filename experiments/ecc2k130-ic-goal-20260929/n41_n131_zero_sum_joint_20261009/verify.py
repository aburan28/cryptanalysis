#!/usr/bin/env python3
"""Check all frozen joint-formula identities, statuses, and replay receipts."""

import hashlib
import json
from pathlib import Path

from run import verify_formula

HERE = Path(__file__).resolve().parent
CAP = 4*1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check_protocol(name, expected):
    protocol = read(HERE / name)
    assert protocol["status"] == expected
    for key, path in protocol["files"].items():
        assert sha(HERE / path) == protocol["sha256"][key], (name, key)
    return protocol


def check_model(formula, model_file, variable_count, receipt):
    assert sha(model_file) == receipt["sha256"]["model_bits"]
    bits = model_file.read_text().strip()
    assert len(bits) == variable_count
    valid, counts = verify_formula(formula, bits)
    assert valid and counts == receipt["formula_assignment_check"]


def main():
    first = check_protocol("protocol.json", "FROZEN")
    s5 = check_protocol("s5_protocol.json", "FROZEN_S5")
    assert first["target"] == s5["target"] == [1458168294740, 1672312028033]
    assert first["limits"]["combined_rss_bytes"] == CAP
    assert s5["limits"]["combined_rss_bytes"] == CAP
    assert first["limits"]["workers"] == s5["limits"]["workers"] == 1
    chart = read(HERE / "witness_chart.json")
    identity = read(HERE / "s5_identity.json")
    assert chart["status"] == "PASS_EXACT_ALGEBRAIC_CHART"
    assert identity["status"] == "PASS_EXACT_S5_CHART"
    assert chart["sha256"]["source"] == sha(HERE / "algebra_audit.py")
    assert identity["sha256"]["source"] == sha(HERE / "s5_identity_audit.py")
    assert identity["sha256"]["chart"] == sha(HERE / "witness_chart.json")
    assert chart["target_fiber_index"] == identity["target_fiber_index"] == 2
    assert len(chart["source_masks"]) == 4

    for mode in ("public", "control"):
        build = read(HERE / f"{mode}_build.json")
        assert build["status"] == "BUILT" and build["mode"] == mode
        assert build["sha256"]["source"] == sha(HERE / "build_n41.py")
        assert build["sha256"]["xcnf"] == sha(HERE / f"{mode}.xcnf")
        assert build["formula_variables"] == 34394
        assert build["and_gates"] == 19714
        s5_build = read(HERE / f"s5_{mode}_build.json")
        assert s5_build["status"] == "BUILT" and s5_build["mode"] == mode
        assert s5_build["sha256"]["source"] == sha(HERE / "build_s5.py")
        assert s5_build["sha256"]["formula"] == sha(HERE / f"s5_{mode}.xcnf")
        assert s5_build["formula_variables"] == 48126
        assert s5_build["and_gates"] == 28117
        if mode == "public":
            assert build["control_masks"] is None
            assert s5_build["control_masks"] is None
        else:
            assert build["control_masks"] == chart["source_masks"]
            assert s5_build["control_masks"] == chart["source_masks"]

    first_control = read(HERE / "control/result.json")
    s5_control = read(HERE / "s5_control/result.json")
    for mode, result, protocol_name, formula in (
        ("control", first_control, "protocol.json", "control.xcnf"),
        ("s5_control", s5_control, "s5_protocol.json", "s5_control.xcnf")):
        assert result["status"] == "BOUNDED_UNKNOWN"
        assert result["stop_reason"] == "WALL_CAP"
        assert result["model_masks"] is None
        assert result["returncode"] == -15
        assert 60*10**9 < result["solver_wall_ns"] < 70*10**9
        assert result["peak_combined_rss_bytes_sampled"] < CAP
        assert result["sha256"]["protocol"] == sha(HERE / protocol_name)
        assert result["sha256"]["formula"] == sha(HERE / formula)
        stdout = HERE / mode / "stdout.txt"
        assert result["sha256"]["stdout"] == sha(stdout)
        assert result["sha256"]["stderr"] == sha(HERE / mode / "stderr.txt")
        assert any(line.startswith("c rst") for line in stdout.read_text().splitlines())
        audit = read(HERE / mode / "audit.json")
        assert audit["status"] == "NO_MODEL"
        assert audit["producer_status"] == result["status"]
        assert audit["sha256"]["producer_result"] == sha(HERE / mode / "result.json")

    check_protocol("chart_protocol.json", "FROZEN_CHART_CONTROL")
    chart_result = read(HERE / "chart_control/result.json")
    assert chart_result["status"] == "SAT_MODEL_PASS"
    check_model(HERE / "chart_control.xcnf",
                HERE / "chart_control/model_bits.txt", 34394, chart_result)

    for mode in ("blocks", "middle"):
        check_protocol(f"{mode}_protocol.json", "FROZEN_PARTIAL_CONTROL")
        result = read(HERE / f"{mode}_control/result.json")
        assert result["status"] == "BOUNDED_UNKNOWN" and result["timed_out"]
        assert result["sha256"]["formula"] == sha(HERE / f"{mode}_control.xcnf")

    s5_chart = read(HERE / "s5_chart/result.json")
    assert s5_chart["status"] == "SAT_MODEL"
    assert s5_chart["model_masks"] == chart["source_masks"]
    assert s5_chart["model_block_u"] == chart["block_u"]
    assert s5_chart["model_target_fiber_index"] == 2
    assert s5_chart["peak_combined_rss_bytes_sampled"] < CAP
    check_model(HERE / "s5_chart.xcnf",
                HERE / "s5_chart/model_bits.txt", 48126, s5_chart)
    sage_audit = read(HERE / "s5_chart/audit.json")
    assert sage_audit["status"] == "VERIFIED_RAW_ROW"
    assert sage_audit["sha256"]["source"] == sha(HERE / "s5_audit.py")
    assert sage_audit["sha256"]["producer_result"] == sha(HERE / "s5_chart/result.json")
    assert len(sage_audit["row"]) == 12
    assert len({leaf["column"] for leaf in sage_audit["row"]}) == 12
    check_protocol("s5_blocks_protocol.json", "FROZEN_BLOCK_OUTPUT_CONTROL")
    block_result = read(HERE / "s5_blocks_control/result.json")
    assert block_result["status"] == "SAT_MODEL_PASS"
    assert block_result["target_fiber_index"] == 2
    check_model(HERE / "s5_blocks_control.xcnf",
                HERE / "s5_blocks_control/model_bits.txt", 48126,
                block_result)
    assert block_result["sha256"]["model_bits"] == \
        s5_chart["sha256"]["model_bits"]
    assert block_result["wall_ns"] < 30*10**9

    print(json.dumps({"status": "PASS_FROZEN_JOINT_DIAGNOSTICS",
                      "s3_control": first_control["status"],
                      "s5_control": s5_control["status"],
                      "s5_chart": sage_audit["status"],
                      "s5_block_output_control": block_result["status"],
                      "s5_block_output_wall_ns": block_result["wall_ns"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
