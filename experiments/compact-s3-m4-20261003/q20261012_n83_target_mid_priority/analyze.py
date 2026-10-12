#!/usr/bin/env python3
"""Replay Q1507 first pairs against S3 and the exact usable N83 base."""
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent.parent
Q1488 = PARENT / "q20261012_n83_first_pair_restart"
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BASE_MANIFEST = PARENT / "bases/n83_weight5_full_orbits.json"
sys.path[:0] = [str(PARENT), str(PARENT / "q20261011_operation_account"),
                str(ROOT / "ecc2k130/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929")]
from counted_onb import CountedOnb  # noqa: E402
from curves import Curve  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def replay(bits, onb, curve, orbit, keys, order):
    coords = [int(bits[i * 83:(i + 1) * 83][::-1], 2) for i in (0, 1)]
    onb.reset_counts()
    a, b = (onb.fromCoords(x) for x in coords)
    roots = s3_roots(onb, a, b) if a and b else ()
    root_coords = [onb.toCoords(x) for x in roots]
    root_calls = onb.snapshot_counts()
    leaves = []
    for c in coords:
        onb.reset_counts()
        raw = curve.pointFromX(onb.fromCoords(c)) if c else None
        projected = curve.mul(raw, 4) if raw is not None else None
        key = orbit.canonical(projected)[0] if projected is not None else None
        filter_calls = onb.snapshot_counts()
        onb.reset_counts()
        if projected is not None:
            assert curve.onCurve(projected)
            assert curve.mul(projected, order) is None
        subgroup_calls = onb.snapshot_counts()
        leaves.append({"coords": c, "weight": c.bit_count(),
                       "rational_lift": raw is not None,
                       "projected_identity": raw is not None and projected is None,
                       "projected_orbit_key": key,
                       "exact_base_member": key in keys if key is not None else False,
                       "filter_field_api_entries": sum(filter_calls.values()),
                       "subgroup_replay_field_api_entries": sum(subgroup_calls.values())})
    return {"root_count": len(root_coords), "root_coords": root_coords,
            "root_field_api_entries": sum(root_calls.values()),
            "leaves": leaves, "both_exact_base_usable":
                all(x["exact_base_member"] for x in leaves)}


def main():
    protocol, result, build = (read(HERE / name) for name in
                               ("protocol.json", "result.json", "build_receipt.json"))
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert result["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
    manifest = read(BASE_MANIFEST)
    assert manifest["curve"]["curve_id"] == protocol["curve_id"]
    assert manifest["factor_base"]["enumerated_set_sha256"] == sha(BASE)
    assert manifest["factor_base"]["actual_usable_points_B_before_folding"] == protocol["factor_base_actual_B"]
    assert manifest["factor_base"]["signed_frobenius_columns"] == protocol["factor_base_folded_columns_K"]
    raw_base = BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i + 21], "little")
            for i in range(0, len(raw_base), 21)}
    assert len(keys) == protocol["factor_base_folded_columns_K"]
    onb = CountedOnb(83)
    curve, orbit = Curve(onb), OrbitKey(onb)
    order = int(manifest["curve"]["subgroup_order"])
    pair_replays = {}
    rows = []
    for item in result["rows"]:
        label, phase, mode = item["input"], item["phase"], item["mode"]
        folder = HERE / "runs" / f"{label}_phase{phase}_{mode}"
        receipt = folder / "receipt.json"
        assert sha(receipt) == item["receipt_sha256"]
        row = read(receipt)
        log = (folder / "solver.stderr.txt").read_text()
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        checkpoints = [(int(a), int(b), int(c)) for a, b, c in
                       re.findall(r"^Q1473_WORK (\d+) (\d+) (\d+)$", log, re.M)]
        last = checkpoints[-1] if checkpoints else None
        replay_result = None
        if row["first_pair_bits"] is not None:
            bits = row["first_pair_bits"]
            if bits not in pair_replays:
                pair_replays[bits] = replay(bits, onb, curve, orbit, keys, order)
            replay_result = pair_replays[bits]
            q1488 = read(Q1488 / "runs" /
                         f"{label}_phase{phase}" / "receipt.json")
            assert bits == q1488["first_pair_bits"]
            assert replay_result["root_count"] == read(Q1488 / "root_samples.json")[
                f"{label}_phase{phase}"]["root_count"]
        rows.append({"input": label, "workload_id": row["workload_id"],
                     "phase": phase, "mode": mode, "status": row["status"],
                     "first_pair_branch": row["first_pair_branch"],
                     "first_pair_combined_calls": row["first_pair_combined_calls"],
                     "first_pair_bits_sha256":
                         hashlib.sha256(row["first_pair_bits"].encode()).hexdigest()
                         if row["first_pair_bits"] else None,
                     "pair_replay": replay_result,
                     "last_work_checkpoint": last,
                     "child_peak_rss_bytes_darwin": row["child_peak_rss_bytes_darwin"],
                     "child_user_cpu_seconds": row["child_user_cpu_seconds"],
                     "solver_wall_seconds_exploratory": row["solver_wall_seconds_exploratory"],
                     "receipt_sha256": sha(receipt)})
    phase2 = [r for r in rows if r["phase"] == 2 and
              r["mode"] == "q1507_target_leaf_first"]
    assert len(phase2) == 2 and all(r["pair_replay"]["both_exact_base_usable"]
                                    and r["pair_replay"]["root_count"] == 2 for r in phase2)
    baseline = {label: read(Q1488 / "runs" / f"{label}_phase2" / "receipt.json")
                for label in ("selected", "holdout")}
    improvement = {r["input"]: {
        "q1488_first_pair_combined_calls": baseline[r["input"]]["first_pair_combined_calls"],
        "q1507_first_pair_combined_calls": r["first_pair_combined_calls"],
        "combined_call_ratio": baseline[r["input"]]["first_pair_combined_calls"] /
                               r["first_pair_combined_calls"],
        "saved_log2_bits": math.log2(baseline[r["input"]]["first_pair_combined_calls"] /
                                    r["first_pair_combined_calls"])}
        for r in phase2}
    continuation_result = read(HERE / "continuation_result.json")
    assert continuation_result["protocol_sha256"] == sha(HERE / "protocol.json")
    full_rows = []
    for item in continuation_result["rows"]:
        folder = HERE / "continuation" / f"{item['input']}_{item['mode']}"
        receipt = folder / "receipt.json"
        assert sha(receipt) == item["receipt_sha256"]
        row = read(receipt)
        assert row["status"] == "BRANCH_CAP_SEARCH_STARTED"
        assert row["first_pair_bits"] == read(Q1488 / "runs" /
            f"{row['input']}_phase2" / "receipt.json")["first_pair_bits"]
        log = (folder / "solver.stderr.txt").read_text()
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        summaries = [tuple(map(int, entry)) for entry in re.findall(
            r"^Q1479_SUMMARY (\d+) (\d+) (\d+) (\d+)$", log, re.M)]
        assert summaries and summaries[-1][0] == 1048576
        full_rows.append({"input": row["input"], "mode": row["mode"],
                          "status": row["status"],
                          "last_work_checkpoint": row["last_work_checkpoint"],
                          "distinct_first_pairs_at_cap": summaries[-1][1],
                          "duplicate_first_pair_snapshots_at_cap": summaries[-1][2],
                          "child_peak_rss_bytes_darwin": row["child_peak_rss_bytes_darwin"],
                          "child_user_cpu_seconds": row["child_user_cpu_seconds"],
                          "solver_wall_seconds_exploratory": row["solver_wall_seconds_exploratory"],
                          "receipt_sha256": sha(receipt)})
    same_cap_work = all(
        next(r for r in full_rows if r["input"] == label and
             r["mode"] == "q1507_target_leaf_first")["last_work_checkpoint"] ==
        next(r for r in full_rows if r["input"] == label and
             r["mode"] == "selector_leaf_interleave")["last_work_checkpoint"]
        for label in ("selected", "holdout"))
    assert same_cap_work and all(r["distinct_first_pairs_at_cap"] == 1
                                 for r in full_rows)
    output = {"proposal_id": "Q1507", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"],
              "factor_base_actual_B": protocol["factor_base_actual_B"],
              "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
              "factor_base_enumerated_set_sha256": sha(BASE),
              "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
              "protocol_sha256": sha(HERE / "protocol.json"),
              "result_sha256": sha(HERE / "result.json"),
              "continuation_result_sha256": sha(HERE / "continuation_result.json"),
              "build_receipt_sha256": sha(HERE / "build_receipt.json"),
              "source_sha256": sha(Path(__file__)),
              "rows": rows, "phase2_usable_pair_call_improvement": improvement,
              "full_continuation_rows": full_rows,
              "full_continuation_identical_cap_work_between_leaf_orders": same_cap_work,
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None}
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2,
                                                  sort_keys=True) + "\n")
    for label, item in improvement.items():
        print(label, item["combined_call_ratio"], item["saved_log2_bits"])


if __name__ == "__main__":
    main()
