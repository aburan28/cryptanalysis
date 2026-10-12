#!/usr/bin/env python3
"""Audit all forty exact phase-three N83 complements and continuation receipts."""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1518 = PARENT / "q20261012_q1518_inprocess_mask_sweep"
Q1512 = PARENT / "q20261012_n83_raw_x_prefilter"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    p, result = read(HERE / "protocol.json"), read(HERE / "result.json")
    old, first_pairs = read(Q1518 / "scan_result.json"), read(Q1518 / "result.json")
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["source_sha256"] == sha(HERE / "run.py")
    assert sha(Q1518 / "scan_result.json") == p["q1518_scan_result_sha256"]
    assert sha(Q1518 / "result.json") == p["q1518_first_pair_result_sha256"]
    assert sha(Q1512 / "build_receipt.json") == p["q1512_build_receipt_sha256"]
    assert sha(Path(read(Q1512 / "build_receipt.json")["binary_path"])) == p["binary_sha256"]
    assert result["curve_id"] == p["curve_id"]
    assert result["candidate_id"] is None and result["isogeny"] == "none"
    assert len(result["rows"]) == 26 and len(old["rows"]) == 16
    old_complete = [r for r in old["rows"] if r["status"] == "COMPLETE"]
    old_caps = [r for r in old["rows"] if r["status"] == "TIMEOUT"]
    assert len(old_complete) == 14 and len(old_caps) == 2
    complete_keys = {(r["input"], r["pair_index"], *r["signs"])
                     for r in old_complete}
    new_keys = {(r["input"], r["pair_index"], *r["signs"])
                for r in result["rows"]}
    assert len(new_keys) == 26 and not complete_keys & new_keys
    expected = set()
    for label in ("selected", "holdout"):
        stage = next(r for r in first_pairs["rows"] if r["input"] == label
                     and r["phase"] == 3)
        assert stage["status"] == "EIGHT_PAIRS_TERMINATED"
        assert stage["exact_base_usable_pairs"] == 5
        for index, item in enumerate(stage["exact_base_outcomes"]):
            if item["both_exact_base_usable"]:
                expected.update((label, index, a, b)
                                for a in (1, -1) for b in (1, -1))
    assert len(expected) == 40 and expected == complete_keys | new_keys
    assert {(r["input"], r["pair_index"], *r["signs"])
            for r in old_caps} <= new_keys
    q1518_run = module("q1518_run_for_replay", Q1518 / "run.py")
    raw_base = q1518_run.BASE.read_bytes()
    assert sha(q1518_run.BASE) == p["factor_base_point_file_sha256"]
    assert sha(q1518_run.BASE_MANIFEST) == p["factor_base_manifest_sha256"]
    keys = {int.from_bytes(raw_base[i:i+21], "little")
            for i in range(0, len(raw_base), 21)}
    onb = q1518_run.base_runner.CountedOnb(83)
    curve = q1518_run.base_runner.Curve(onb)
    orbit = q1518_run.base_runner.OrbitKey(onb)
    order = int(read(q1518_run.BASE_MANIFEST)["curve"]["subgroup_order"])
    for row in result["rows"]:
        target = tuple(read(q1518_run.base_runner.TARGETS[row["input"]])["public_target"])
        stage = next(r for r in first_pairs["rows"] if r["input"] == row["input"]
                     and r["phase"] == 3)
        item = stage["exact_base_outcomes"][row["pair_index"]]
        leaves = q1518_run.base_runner.base_pair(item["bits"], onb, curve,
                                                  orbit, keys, order)
        signed = [leaf["point"] if sign == 1 else curve.neg(leaf["point"])
                  for leaf, sign in zip(leaves, row["signs"])]
        complement = curve.add(target, curve.neg(curve.add(*signed)))
        assert complement is not None and curve.onCurve(complement)
        assert curve.add(curve.add(*signed), complement) == target
        assert row["complement_x_onb_hex"] == format(onb.toCoords(complement[0]), "x")
        assert row["complement_y_onb_hex"] == format(onb.toCoords(complement[1]), "x")
    total_mul = 0
    total_hits = 0
    checked_rows = []
    for row in result["rows"]:
        assert row["status"] == "COMPLETE" and row["return_code"] == 0
        folder = HERE / "runs" / row["input"] / f"pair{row['pair_index']}" / (
            f"sign{row['signs'][0]}_{row['signs'][1]}")
        assert row == read(folder / "receipt.json")
        assert sha(folder / "stdout.txt") == row["stdout_sha256"]
        assert sha(folder / "stderr.txt") == row["stderr_sha256"]
        lines = (folder / "stdout.txt").read_text().splitlines()
        assert json.loads(lines[-1]) == row["native_result"]
        assert lines[:-1] == row["native_hit_lines"]
        native = row["native_result"]
        assert native["actual_B"] == native["scanned"] == p["factor_base_actual_B"]
        assert native["hits"] == native["exceptional_pairs"] == 0
        assert row["native_hit_lines"] == []
        assert row["batch_mul_calls_excluding_inversion_internals"] == (
            5 * p["scan_pairs_per_complement"])
        assert row["child_user_cpu_seconds"] > 0
        assert row["child_peak_rss_bytes_darwin"] > 0
        total_mul += row["batch_mul_calls_excluding_inversion_internals"]
        total_hits += native["hits"]
        checked_rows.append(row)
    for row in old_complete:
        assert row["native_result"]["hits"] == 0
        assert row["batch_mul_calls_excluding_inversion_internals"] == (
            5 * p["scan_pairs_per_complement"])
        total_mul += row["batch_mul_calls_excluding_inversion_internals"]
    assert total_hits == 0
    assert total_mul == 40 * 5 * p["scan_pairs_per_complement"]
    return {
        "proposal_id": "Q1520", "candidate_id": None,
        "curve_id": p["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "ordinary_workload_ids": ["2eb250a29072", "394256b9f901"],
        "first_pair_usable_per_target": 5,
        "original_complete_zero_hit_scans": len(old_complete),
        "original_capped_scans_retained": len(old_caps),
        "continuation_complete_zero_hit_scans": len(result["rows"]),
        "unique_complete_signed_complements": len(expected),
        "verified_exact_base_hits": 0,
        "novel_rank_rows_from_this_panel": 0,
        "complete_scan_batch_mul_calls_excluding_inversion_internals": total_mul,
        "complete_scan_batch_mul_log2": math.log2(total_mul),
        "continuation_child_user_cpu_seconds": sum(
            r["child_user_cpu_seconds"] for r in checked_rows),
        "continuation_child_system_cpu_seconds": sum(
            r["child_system_cpu_seconds"] for r in checked_rows),
        "continuation_wall_seconds_exploratory": sum(
            r["wall_seconds_exploratory"] for r in checked_rows),
        "maximum_continuation_peak_rss_bytes_darwin": max(
            r["child_peak_rss_bytes_darwin"] for r in checked_rows),
        "cost_per_verified_relation_in_this_panel": None,
        "complete_n131_solve_work_log2": None,
    }


if __name__ == "__main__":
    analysis = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2,
                                                       sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert analysis == read(HERE / "analysis.json")
    print("PASS Q1520 forty complete N83 signed complements and censored retry audit")
