#!/usr/bin/env python3
"""Replay Q1524 identities, exact outputs, and source-level operation counts."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
PAIR_LIMIT = 15_488_796
EXACT_FIELDS = (
    "actual_B", "folded_K", "scanned", "batch_pairs", "hits",
    "exceptional_pairs", "bloom_log2_bits", "bloom_hashes", "bloom_bytes",
    "bloom_build_bit_sets", "bloom_scan_bit_probes", "bloom_positives",
    "canonical_calls", "raw_x_checksum_hex", "hit_key_checksum_hex",
)


def check():
    p = run.read(HERE / "protocol.json")
    screen = run.read(HERE / "batch_screen.json")
    parent = run.read(run.Q1521 / "result.json")
    build = run.read(HERE / "build_receipt.json")
    assert run.sha(run.BASE) == p["factor_base_file_sha256"]
    assert run.sha(run.Q1521 / "result.json") == p["baseline_result_sha256"]
    assert run.sha(run.Q1521 / "native_fused.cpp") == p["baseline_source_sha256"]
    assert run.sha(HERE / "native_joint.cpp") == p["source_sha256"]
    assert run.sha(run.BINARY) == p["binary_sha256"]
    assert build["status"] == "COMPILED"
    assert build["source_sha256"] == p["source_sha256"]
    assert build["binary_sha256"] == p["binary_sha256"]
    assert run.sha(HERE.parent / "q20261012_native_rational_guard/native_n83_pairs.cpp") == build["included_native_parent_sha256"]
    assert p["candidate_id"] is None and p["isogeny"] == "none"
    assert p["factor_base_actual_B"] == 2 * PAIR_LIMIT
    assert p["factor_base_folded_K"] == 186_612
    assert [(row["label"], row["batch_pairs"]) for row in
            [run.read(HERE / "runs" / f"{label}_{batch}" / "receipt.json")
             for label, batch in screen["panel_order"]]] == [tuple(x) for x in screen["panel_order"]]
    baselines = {row["label"]: row for row in parent["rows"]}
    rows = []
    panel = [(label, p["batch_pairs"][label], label) for label in p["panel_order"]]
    panel += [(label, batch, f"{label}_{batch}") for label, batch in screen["panel_order"]]
    for label, batch, key in panel:
        folder = HERE / "runs" / key
        receipt = run.read(folder / "receipt.json")
        assert receipt["status"] == "COMPLETE" and receipt["return_code"] == 0
        assert receipt["label"] == label
        assert run.sha(folder / "stdout.txt") == receipt["stdout_sha256"]
        assert run.sha(folder / "stderr.txt") == receipt["stderr_sha256"]
        assert run.sha(run.Q1521 / f"{label}_xy.txt") == p["input_sha256"][label]
        assert receipt["command"] == [str(run.BINARY), str(run.BASE),
                str(run.Q1521 / f"{label}_xy.txt"),
                "1" if label == "control" else str(PAIR_LIMIT), str(batch), "28", "4"]
        lines = (folder / "stdout.txt").read_text().splitlines()
        assert [json.loads(line) for line in lines if line.startswith("{")] == receipt["native"]
        assert [line for line in lines if line.startswith("hit ")] == receipt["hit_lines"]
        assert [x["complement_index"] for x in receipt["native"]] == list(range(4))
        expected_inversions = math.ceil((1 if label == "control" else PAIR_LIMIT) / batch)
        assert {x["joint_batch_inversions"] for x in receipt["native"]} == {expected_inversions}
        assert len({x["setup_seconds"] for x in receipt["native"]}) == 1
        prior = baselines[label]
        for a, b in zip(receipt["native"], prior["native"]):
            assert all(a[field] == b[field] for field in EXACT_FIELDS if field != "batch_pairs")
            assert a["batch_pairs"] == batch
        if label == "control":
            assert len(receipt["hit_lines"]) == 4
            assert all(x["hits"] == 1 for x in receipt["native"])
            assert {line.split()[-1] for line in receipt["hit_lines"]} == {"1cec2d365a677c81"}
        else:
            assert receipt["hit_lines"] == []
            assert all(x["hits"] == x["exceptional_pairs"] == 0 for x in receipt["native"])
        row = {"label": label, "batch_pairs": batch,
               "status": receipt["status"], "exact_outputs_match_q1521": True,
               "joint_inversions": expected_inversions,
               "baseline_separate_inversions": 4 * expected_inversions,
               "inversions_saved": 3 * expected_inversions,
               "child_cpu_seconds_exploratory":
                   receipt["child_user_cpu_seconds"] + receipt["child_system_cpu_seconds"],
               "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
               "peak_rss_bytes_darwin": receipt["child_peak_rss_bytes_darwin"],
               "hits": sum(x["hits"] for x in receipt["native"])}
        if label != "control":
            # Each complete four-complement zero-hit scan uses 20 mul and
            # 8 sqr calls per positive base representative outside inv().
            # The fixed N83 Itoh-Tsujii inv() has 8 mul and 82 sqr calls.
            raw_mul = 20 * PAIR_LIMIT
            raw_sqr = 8 * PAIR_LIMIT
            row.update({
                "scan_mul_calls_excluding_inversion": raw_mul,
                "scan_sqr_calls_excluding_inversion": raw_sqr,
                "joint_mul_calls_including_inversion": raw_mul + 8 * expected_inversions,
                "baseline_mul_calls_including_inversion": raw_mul + 32 * expected_inversions,
                "joint_sqr_calls_including_inversion": raw_sqr + 82 * expected_inversions,
                "baseline_sqr_calls_including_inversion": raw_sqr + 328 * expected_inversions,
            })
        rows.append(row)
    assert len(rows) == 7
    return {"proposal_id": "Q1524", "candidate_id": None, "run_id": None,
            "curve_id": p["curve_id"], "isogeny": "none",
            "point_decomposition_stage_code": "PDP4hybrid",
            "protocol_sha256": run.sha(HERE / "protocol.json"),
            "batch_screen_sha256": run.sha(HERE / "batch_screen.json"),
            "source_sha256": p["source_sha256"], "binary_sha256": p["binary_sha256"],
            "rows": rows, "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    result = check()
    if sys.argv[1:] == ["--write-analysis"]:
        run.save(HERE / "analysis.json", result)
    else:
        assert sys.argv[1:] == []
        assert result == run.read(HERE / "analysis.json")
    print("PASS Q1524 positive replay and exact Q1521 ordinary vectors")
