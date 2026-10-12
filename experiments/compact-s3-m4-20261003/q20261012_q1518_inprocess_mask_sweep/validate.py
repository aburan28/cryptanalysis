#!/usr/bin/env python3
"""Read-only audit of Q1518 mask cells and phase-three exact scans."""
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
Q1512 = run.PARENT / "q20261012_n83_raw_x_prefilter"


def check():
    p = run.read(HERE / "protocol.json")
    result = run.read(HERE / "result.json")
    s = run.read(HERE / "scan_protocol.json")
    scans = run.read(HERE / "scan_result.json")
    assert result["protocol_sha256"] == run.sha(HERE / "protocol.json")
    assert result["run_source_sha256"] == run.sha(HERE / "run.py")
    assert scans["scan_protocol_sha256"] == run.sha(HERE / "scan_protocol.json")
    assert scans["scan_source_sha256"] == run.sha(HERE / "scan_phase3.py")
    assert scans["status"] == "INTERRUPTED_HOST_CONTENTION"
    assert scans["partial_sha256"] == run.sha(HERE / "scan_result.partial.json")
    assert scans["rows"] == run.read(HERE / "scan_result.partial.json")["rows"]
    assert scans["salvage_source_sha256"] == run.sha(HERE / "salvage_scan.py")
    assert run.sha(HERE / "result.json") == s["q1518_result_sha256"]
    assert run.sha(run.Q1488 / "freeze.json") == p["q1488_freeze_sha256"]
    assert run.sha(run.Q1517 / "build_receipt.json") == p["q1517_build_receipt_sha256"]
    assert run.sha(run.BASE) == p["factor_base_point_file_sha256"]
    assert run.sha(run.BASE_MANIFEST) == p["factor_base_manifest_sha256"]
    assert run.sha(Q1512 / "build_receipt.json") == s["q1512_build_receipt_sha256"]
    for build_path in (run.Q1517 / "build_receipt.json", Q1512 / "build_receipt.json"):
        build = run.read(build_path)
        assert run.sha(Path(build["binary_path"])) == build["binary_sha256"]
    frozen = run.read(run.Q1488 / "freeze.json")
    raw_base = run.BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i + 21], "little")
            for i in range(0, len(raw_base), 21)}
    assert len(keys) == p["factor_base_folded_columns_K"]
    onb = run.base_runner.CountedOnb(83)
    curve = run.base_runner.Curve(onb)
    orbit = run.base_runner.OrbitKey(onb)
    order = int(run.read(run.BASE_MANIFEST)["curve"]["subgroup_order"])
    assert len(result["rows"]) == 18
    grid = {}
    for row in result["rows"]:
        label, phase = row["input"], row["phase"]
        assert label in p["inputs"] and phase in p["mask_phases"]
        assert (label, phase) not in grid
        grid[label, phase] = row
        cell = frozen["inputs"][label]
        assert row["workload_id"] == cell["workload_id"]
        assert row["flip_count"] == len(frozen["mask_schedule"][str(phase)]["flip_ids"])
        folder = HERE / "runs" / label / f"phase{phase}"
        assert row["stdout_sha256"] == run.sha(folder / "solver.stdout.txt")
        assert row["stderr_sha256"] == run.sha(folder / "solver.stderr.txt")
        stderr = (folder / "solver.stderr.txt").read_bytes()
        markers = [(int(a), int(b), int(c), int(d), e.decode())
                   for a, b, c, d, e in run.prior.PAIR.findall(stderr)]
        assert row["pairs"] == [{"index": a, "branch": b,
                                "cnf_calls": c, "xor_calls": d, "bits": e}
                               for a, b, c, d, e in markers]
        assert row["distinct_pairs"] == len(set(x[4] for x in markers))
        assert len(row["exact_base_outcomes"]) == len(markers)
        usable = 0
        for marker, outcome in zip(markers, row["exact_base_outcomes"]):
            leaves = run.base_runner.base_pair(marker[4], onb, curve, orbit,
                                                keys, order)
            assert outcome["bits"] == marker[4]
            assert outcome["leaves"] == [
                {k: v for k, v in x.items() if k != "point"} for x in leaves]
            assert outcome["both_exact_base_usable"] == all(
                x["exact_base_member"] for x in leaves)
            usable += outcome["both_exact_base_usable"]
        assert row["exact_base_usable_pairs"] == usable
        assert row["status"] == "EIGHT_PAIRS_TERMINATED"
        assert row["return_code"] == 47 and row["search_started"]
        assert len(markers) == 8
        assert f"Q1481_MASK {phase} ".encode() in stderr
        assert row["cnf_xor_calls_to_last_pair"] == markers[-1][2] + markers[-1][3]
        assert row["calls_per_usable_pair"] == (
            row["cnf_xor_calls_to_last_pair"] / usable if usable else None)
    for label in p["inputs"]:
        cell = frozen["inputs"][label]
        raw = gzip.decompress((HERE / "runs" / label / "system.xcnf.gz").read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
    expected_cells = [(label, index, s0, s1)
                      for label in p["inputs"] for index in (1, 2, 3, 4, 6)
                      for s0 in (1, -1) for s1 in (1, -1)]
    assert len(expected_cells) == 40
    assert len(scans["rows"]) == 16
    assert [(x["input"], x["pair_index"], *x["signs"])
            for x in scans["rows"]] == expected_cells[:16]
    assert scans["interruption"]["active_cell"] == {
        "input": expected_cells[16][0], "pair_index": expected_cells[16][1],
        "signs": list(expected_cells[16][2:])}
    assert scans["interruption"]["remaining_planned_cells_including_active"] == 24
    seen = set()
    total_hits, total_calls, complete_scans, timeout_scans = 0, 0, 0, 0
    for row in scans["rows"]:
        label, index = row["input"], row["pair_index"]
        s0, s1 = row["signs"]
        key = (label, index, s0, s1)
        assert key not in seen
        seen.add(key)
        stage = grid[label, 3]
        assert stage["exact_base_outcomes"][index]["both_exact_base_usable"]
        leaves = run.base_runner.base_pair(stage["pairs"][index]["bits"],
                                            onb, curve, orbit, keys, order)
        target = tuple(run.read(run.base_runner.TARGETS[label])["public_target"])
        p0 = leaves[0]["point"] if s0 == 1 else curve.neg(leaves[0]["point"])
        p1 = leaves[1]["point"] if s1 == 1 else curve.neg(leaves[1]["point"])
        comp = curve.add(target, curve.neg(curve.add(p0, p1)))
        assert curve.add(curve.add(p0, p1), comp) == target
        assert row["complement_x_onb_hex"] == format(onb.toCoords(comp[0]), "x")
        assert row["complement_y_onb_hex"] == format(onb.toCoords(comp[1]), "x")
        folder = HERE / "scans" / label / f"pair{index}" / f"sign{s0}_{s1}"
        assert row["stdout_sha256"] == run.sha(folder / "stdout.txt")
        assert row["stderr_sha256"] == run.sha(folder / "stderr.txt")
        lines = (folder / "stdout.txt").read_text().splitlines()
        if row["status"] == "TIMEOUT":
            assert row["return_code"] is None
            assert row["native_result"] is None
            assert row["batch_mul_calls_excluding_inversion_internals"] is None
            timeout_scans += 1
            continue
        assert row["status"] == "COMPLETE" and row["return_code"] == 0
        assert row["native_result"] == json.loads(lines[-1])
        assert row["native_hit_lines"] == lines[:-1]
        complete_scans += 1
        native = row["native_result"]
        assert native["actual_B"] == native["scanned"] == p["factor_base_actual_B"]
        assert native["bloom_log2_bits"] == s["bloom_log2_bits"]
        assert native["bloom_hashes"] == s["bloom_hashes"]
        total_hits += native["hits"]
        if native["hits"] == 0 and native["exceptional_pairs"] == 0:
            assert row["batch_mul_calls_excluding_inversion_internals"] == (
                5 * s["scan_pairs_per_complement"])
            total_calls += row["batch_mul_calls_excluding_inversion_internals"]
    assert {i for l in p["inputs"] for i, o in enumerate(grid[l, 3]["exact_base_outcomes"])
            if o["both_exact_base_usable"]} == {1, 2, 3, 4, 6}
    analysis_rows = []
    for label in p["inputs"]:
        best = min((grid[label, ph] for ph in p["mask_phases"]
                    if grid[label, ph]["calls_per_usable_pair"] is not None),
                   key=lambda x: x["calls_per_usable_pair"])
        baseline = grid[label, 2]
        analysis_rows.append({"input": label, "workload_id": best["workload_id"],
                              "best_phase": best["phase"],
                              "best_exact_base_usable_pairs": best["exact_base_usable_pairs"],
                              "best_cnf_xor_calls": best["cnf_xor_calls_to_last_pair"],
                              "best_calls_per_usable_pair": best["calls_per_usable_pair"],
                              "phase2_calls_per_usable_pair": baseline["calls_per_usable_pair"],
                              "phase2_over_best_ratio": baseline["calls_per_usable_pair"] /
                                  best["calls_per_usable_pair"],
                              "phase2_over_best_bits": math.log2(
                                  baseline["calls_per_usable_pair"] /
                                  best["calls_per_usable_pair"])})
    return {"proposal_id": "Q1518", "candidate_id": None,
            "curve_id": p["curve_id"], "isogeny": "none",
            "mask_cells": len(result["rows"]), "rows": analysis_rows,
            "phase3_planned_signed_scans": len(expected_cells),
            "phase3_attempted_signed_scans": len(scans["rows"]),
            "phase3_complete_signed_scans": complete_scans,
            "phase3_timeout_signed_scans": timeout_scans,
            "phase3_unattempted_or_interrupted_scans": len(expected_cells) - len(scans["rows"]),
            "phase3_relation_yield_status": "CENSORED",
            "phase3_verified_exact_base_hits": total_hits,
            "phase3_batch_mul_calls_excluding_inversion_internals": total_calls,
            "phase3_batch_mul_calls_log2": math.log2(total_calls),
            "complete_n83_decomposition_work_log2": None,
            "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    output = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert output == run.read(HERE / "analysis.json")
    print("PASS Q1518 complete mask sweep and censored phase-three scan audit")
