#!/usr/bin/env python3
"""Replay Q1521 input, positive controls, and exact Q1520 scan vectors."""
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1512 = PARENT / "q20261012_n83_raw_x_prefilter"
Q1520 = PARENT / "q20261012_q1520_phase3_scan_completion"
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    p, result = read(HERE / "protocol.json"), read(HERE / "result.json")
    old, control = read(Q1520 / "result.json"), read(Q1512 / "result.json")
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["source_sha256"] == sha(HERE / "run.py")
    assert result["curve_id"] == p["curve_id"]
    assert result["candidate_id"] is None and result["isogeny"] == "none"
    assert sha(BASE) == p["factor_base_point_file_sha256"]
    assert sha(Q1520 / "result.json") == p["q1520_result_sha256"]
    assert sha(Q1512 / "result.json") == p["q1512_result_sha256"]
    assert sha(Q1512 / "native_prefilter.cpp") == p["parent_native_source_sha256"]
    assert sha(HERE / "native_fused.cpp") == p["native_fused_source_sha256"]
    assert sha(Path(p["compiler_command"][-1])) == p["native_fused_binary_sha256"]
    assert sha(HERE / "control_xy.txt") == p["control_xy_sha256"]
    assert [r["label"] for r in result["rows"]] == p["panel_order"]
    exact_fields = ("actual_B", "folded_K", "scanned", "batch_pairs", "hits",
                    "exceptional_pairs", "bloom_log2_bits", "bloom_hashes",
                    "bloom_bytes", "bloom_build_bit_sets", "bloom_scan_bit_probes",
                    "bloom_positives", "canonical_calls", "raw_x_checksum_hex",
                    "hit_key_checksum_hex")
    panels = {}
    for row in result["rows"]:
        assert row["status"] == "COMPLETE" and row["return_code"] == 0
        folder = HERE / "runs" / row["label"]
        assert read(folder / "receipt.json") == row
        assert sha(folder / "stdout.txt") == row["stdout_sha256"]
        assert sha(folder / "stderr.txt") == row["stderr_sha256"]
        lines = (folder / "stdout.txt").read_text().splitlines()
        assert [json.loads(line) for line in lines if line.startswith("{")] == row["native"]
        assert [line for line in lines if line.startswith("hit ")] == row["hit_lines"]
        assert [x["complement_index"] for x in row["native"]] == list(range(4))
        assert len({x["setup_seconds"] for x in row["native"]}) == 1
        if row["label"] == "control":
            parent = control["controls"][0]
            assert row["hit_lines"] == ["hit 0 0 1cec2d365a677c81"] * 4
            for item in row["native"]:
                assert all(item[field] == parent["native"][field]
                           for field in exact_fields)
        else:
            label = row["label"]
            xy = HERE / f"{label}_xy.txt"
            assert sha(xy) == p["inputs"][label]["xy_sha256"]
            baseline = [item for item in old["rows"] if item["input"] == label
                        and item["pair_index"] == p["inputs"][label]["pair_index"]]
            assert len(baseline) == 4
            assert [(x["complement_x_onb_hex"], x["complement_y_onb_hex"])
                    for x in baseline] == [tuple(line.split()) for line in xy.read_text().splitlines()]
            assert [x["signs"] for x in baseline] == p["inputs"][label]["ordered_signs"]
            assert [x["stdout_sha256"] for x in baseline] == p["inputs"][label]["baseline_q1520_stdout_sha256"]
            assert row["hit_lines"] == []
            for item, prior in zip(row["native"], baseline):
                assert all(item[field] == prior["native_result"][field]
                           for field in exact_fields)
            panels[label] = {
                "fused_base_decodes_and_bloom_builds": 1,
                "baseline_base_decodes_and_bloom_builds": 4,
                "fused_child_cpu_seconds_exploratory": row["child_user_cpu_seconds"] + row["child_system_cpu_seconds"],
                "baseline_child_cpu_seconds_exploratory": sum(
                    r["child_user_cpu_seconds"] + r["child_system_cpu_seconds"]
                    for r in baseline),
                "fused_wall_seconds_exploratory": row["wall_seconds_exploratory"],
                "baseline_wall_seconds_exploratory": sum(
                    r["wall_seconds_exploratory"] for r in baseline),
                "fused_reported_setup_seconds_exploratory": row["native"][0]["setup_seconds"],
                "baseline_reported_setup_seconds_exploratory": sum(
                    r["native_result"]["setup_seconds"] for r in baseline),
                "fused_peak_rss_bytes_darwin": row["child_peak_rss_bytes_darwin"],
                "exact_base_hits": sum(item["hits"] for item in row["native"]),
                "complete_scan_batch_mul_calls_excluding_inversion_internals":
                    4 * 5 * p["full_pair_limit"],
            }
    assert set(panels) == {"selected", "holdout"}
    return {"proposal_id": "Q1521", "candidate_id": None,
            "curve_id": p["curve_id"], "isogeny": "none",
            "point_decomposition_stage_code": "PDP4hybrid", "panels": panels,
            "positive_controls_verified": 4,
            "ordinary_complete_complements": 8,
            "total_batch_mul_calls_unchanged": 8 * 5 * p["full_pair_limit"],
            "total_batch_mul_log2_unchanged": math.log2(8 * 5 * p["full_pair_limit"]),
            "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    analysis = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2,
                                                       sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert analysis == read(HERE / "analysis.json")
    print("PASS Q1521 four positive controls and eight exact ordinary scan matches")
