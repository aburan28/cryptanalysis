#!/usr/bin/env python3
"""Audit Q1512 source, ordinary rows, controls, and named-unit accounting."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
Q1505 = PARENT / "q20261012_n83_deferred_y_scan"
INPUTS = PARENT / "q20261012_n83_complement_pair_probe/frozen_inputs.json"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1512-native-prefilter")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    control = json.loads((HERE / "deep_control.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    rebuild = json.loads((HERE / "rebuild_check.json").read_text())
    assert p["proposal_id"] == result["proposal_id"] == analysis["proposal_id"] == "Q1512"
    assert p["candidate_id"] is p["run_id"] is None
    assert result["candidate_id"] is result["run_id"] is None
    assert p["curve_id"] == result["curve_id"] == control["curve_id"] == analysis["curve_id"]
    assert p["isogeny"] == result["isogeny"] == control["isogeny"] == "none"
    assert sha(BASE) == p["base_point_file_sha256"] == p["factor_base_enumerated_set_sha256"]
    assert sha(INPUTS) == p["frozen_inputs_sha256"]
    assert sha(Q1505 / "result.json") == p["q1505_result_sha256"]
    assert sha(Q1505 / "native_deferred_y.cpp") == p["parent_native_source_sha256"]
    assert sha(HERE / "native_prefilter.cpp") == p["source_sha256"]
    assert BINARY.exists() and sha(BINARY) == p["binary_sha256"]
    assert build["binary_sha256"] == p["binary_sha256"]
    assert build["source_sha256"] == p["source_sha256"]
    assert build["included_native_sha256"] == sha(PARENT / "q20261012_native_rational_guard/native_n83_pairs.cpp")
    assert build["included_eccF83_sha256"] == sha(PARENT / "q20261012_native_rational_guard/eccF83.h")
    assert rebuild["checked_status"] == "PASS"
    assert rebuild["source_sha256"] == p["source_sha256"]
    assert rebuild["frozen_binary_sha256"] == p["binary_sha256"]
    assert len(rebuild["rows"]) == 3
    for row in rebuild["rows"]:
        assert json.loads(row["stdout"].splitlines()[-1]) == row["native"]
    if Path("/private/tmp/q1512-rebuild").exists():
        assert sha(Path("/private/tmp/q1512-rebuild")) == rebuild["rebuild_binary_sha256"]
    assert result["protocol_sha256"] == analysis["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["run_source_sha256"] == sha(HERE / "run.py")
    assert analysis["source_sha256"] == sha(HERE / "analyze.py")
    assert analysis["result_sha256"] == sha(HERE / "result.json")
    assert analysis["deep_control_sha256"] == sha(HERE / "deep_control.json")
    assert analysis["q1505_analysis_sha256"] == sha(Q1505 / "analysis.json")
    assert control["source_sha256"] == sha(HERE / "deep_control.py")
    assert control["binary_sha256"] == p["binary_sha256"]
    assert len(control["rows"]) == 4 and control["base_scan_position"] == 11823
    for row in control["rows"]:
        assert row["native"]["hits"] >= 1
        assert any(line.startswith(f"hit 11823 {row['sign']} ") for line in row["stdout"].splitlines())
    assert len(result["controls"]) == 2
    for row in result["controls"]:
        assert row["status"] == "COMPLETE" and row["native"]["hits"] >= 1
        assert any(line.startswith(f"hit 0 {row['expected_sign']} ") for line in row["stdout"].splitlines())
    assert len(result["rows"]) == len(p["screen_modes"]) + len(p["full_modes_in_run_order"])
    for row in result["rows"]:
        assert row["status"] == "COMPLETE" and row["exit_code"] == 0
        assert json.loads(row["stdout"].splitlines()[-1]) == row["native"]
        native = row["native"]
        assert native["actual_B"] == p["factor_base_actual_B"]
        assert native["folded_K"] == p["factor_base_folded_columns_K"]
        assert native["hits"] == native["exceptional_pairs"] == 0
        assert native["scanned"] == 2 * p["screen_pair_count"] if row["panel"] == "screen" else native["scanned"] == 2 * p["full_pair_count"]
        assert native["canonical_calls"] == native["bloom_positives"]
        assert native["bloom_build_bit_sets"] == p["factor_base_folded_columns_K"] * 83 * row["bloom_hashes"]
        if row["bloom_log2_bits"] == 0:
            assert native["canonical_calls"] == native["scanned"]
            assert native["bloom_bytes"] == native["bloom_scan_bit_probes"] == 0
        else:
            assert native["bloom_bytes"] == (1 << row["bloom_log2_bits"]) // 8
            assert native["canonical_calls"] < native["scanned"]
            assert native["scanned"] <= native["bloom_scan_bit_probes"] <= native["scanned"] * row["bloom_hashes"]
    for label in ("selected", "holdout"):
        rows = [row for row in result["rows"] if row["panel"] == "full" and row["input"] == label]
        assert {row["bloom_log2_bits"] for row in rows} == {0, 27, 28}
        assert len({row["native"]["raw_x_checksum_hex"] for row in rows}) == 1
        assert len({row["native"]["hits"] for row in rows}) == 1
    assert analysis["n131_w6_four_sign_zero_hit_batch_mul_calls_unchanged"] == 65596347880
    assert math.isclose(analysis["n131_w6_independent_uniform_first_pair_relation_supply_batch_mul_log2_unchanged"],
                        123.28850509312997)
    assert analysis["complete_n131_solve_operation_log2"] is None
    print("PASS Q1512 source-bound ordinary sweep, signed controls, and work accounting")


if __name__ == "__main__":
    main()
