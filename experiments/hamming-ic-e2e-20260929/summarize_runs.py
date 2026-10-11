#!/usr/bin/env python3
"""Summarize the six frozen, same-target N9 IC measurements."""

from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/ic-candidate-catalog"))
import analyze_v2  # noqa: E402


def main():
    runs = HERE / "runs"
    arms = {}
    rows = []
    for encoding in ("fc", "unary"):
        results = []
        for number in (1, 2, 3):
            folder = runs / f"n9_{encoding}_r{number}"
            result = json.loads((folder / "result.json").read_text())
            row = analyze_v2.validate_run(json.loads((folder / "run.jsonl").read_text()))
            assert result["status"] == row["status"] == "complete"
            assert result["run_id"] == row["run_id"]
            assert result["workload_id"] == row["workload_id"]
            results.append(result)
            rows.append(row)
        assert len({item["candidate_id"] for item in results}) == 1
        assert len({item["workload_id"] for item in results}) == 1
        online = [item["ic"]["online_wall_ns"] for item in results]
        rho = [item["rho"]["online_wall_ns"] for item in results]
        arms[encoding] = {
            "candidate_id": results[0]["candidate_id"],
            "workload_id": results[0]["workload_id"],
            "run_ids": [item["run_id"] for item in results],
            "online_wall_ns": online, "rho_online_wall_ns": rho,
            "median_ic_online_ns": statistics.median(online),
            "range_ic_online_ns": [min(online), max(online)],
            "median_rho_online_ns": statistics.median(rho),
            "median_rho_over_ic": statistics.median(
                item["online_speedup"] for item in results),
            "precompute_query_counts": [len(item["preparation"]["factor_logs"]["records"])
                                        for item in results],
            "precompute_verified_relations": [item["preparation"]["factor_logs"]["verified_relations"]
                                              for item in results],
            "final_ranks": [item["preparation"]["factor_logs"]["rank"]
                            for item in results],
            "formula": {key: value for key, value in results[0]["preparation"]["sat_formula"].items()
                        if key in ("variables", "cnf_clauses", "xor_rows", "and_gates")}}
    workload_ids = {item["workload_id"] for item in rows}
    target_hashes = {item["target_point_sha256"] for item in rows}
    resources = {item["provenance"]["resource_envelope_id"] for item in rows}
    assert len(workload_ids) == len(target_hashes) == len(resources) == 1
    ratios = [u / f for u, f in zip(arms["unary"]["online_wall_ns"],
                                   arms["fc"]["online_wall_ns"])]
    summary = {
        "kind": "paired_n9_one_target_fc_hamming_vs_unary",
        "workload_id": next(iter(workload_ids)),
        "target_point_sha256": next(iter(target_hashes)),
        "resource_envelope_id": next(iter(resources)),
        "pair_blocks": 3, "target_count_per_run": 1,
        "arms": arms,
        "paired_unary_over_fc_online_ratio": ratios,
        "median_paired_unary_over_fc": statistics.median(ratios),
        "range_paired_unary_over_fc": [min(ratios), max(ratios)],
        "uncertainty_note": "Three repeated solves of one frozen target; the range is run-to-run variation, not a population confidence interval.",
        "claim_boundary": "Toy N9 only; no N37, N53, or ECC2K-130 speedup inference."}
    (runs / "all_runs.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    (runs / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pair_blocks": 3,
                      "fc_median_online_ms": arms["fc"]["median_ic_online_ns"] / 1e6,
                      "unary_median_online_ms": arms["unary"]["median_ic_online_ns"] / 1e6,
                      "median_unary_over_fc": summary["median_paired_unary_over_fc"]},
                     indent=2))


if __name__ == "__main__":
    main()
