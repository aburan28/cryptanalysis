#!/usr/bin/env python3
"""Summarize the frozen paired hit panel without treating stage cost as IC speed."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median


HERE = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=HERE / "receipt-r1.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output already exists: {args.out}")
    protocol = json.loads((HERE / "protocol.json").read_text())
    receipt = json.loads(args.receipt.read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    assert receipt["status"] == "verified_stage_control"
    assert receipt["source_sha256"] == protocol["source_sha256"]
    rows = receipt["held_out_rows"]
    n = len(rows)
    assert n == protocol["target_count"]
    assert workload["workload_record"]["source_targets"] == [
        row["source_target"] for row in rows]
    assert workload["workload_record"]["descendant_targets"] == [
        row["descendant_target"] for row in rows]
    b = receipt["paired_source_only"]
    c = receipt["paired_native_only"]
    difference = (c - b)/n
    standard_error = math.sqrt(max(0, ((b + c)/n - difference*difference)/n))
    low, high = difference - 1.96*standard_error, difference + 1.96*standard_error
    source_ns = [row["policies"]["source"]["wall_ns"] for row in rows]
    native_ns = [row["target_map_wall_ns"] + row["policies"]["descendant_native"]["wall_ns"]
                 for row in rows]
    source_hits = receipt["verified_hit_counts"]["source"]
    native_hits = receipt["verified_hit_counts"]["descendant_native"]
    assert source_hits + c == native_hits + b
    rate_gate = difference >= 0.10 and low > 0
    cost_ratio = median(native_ns)/median(source_ns)
    cost_gate_exploratory = cost_ratio <= 2
    analysis = {
        "kind": "n39_degree79_paired_stage_analysis",
        "proposal_id": "Q1419", "candidate_id": None,
        "receipt_sha256": sha256(args.receipt),
        "protocol_sha256": sha256(HERE / "protocol.json"),
        "workload_id": workload["workload_id"],
        "workload_sha256": sha256(HERE / "workload.json"),
        "source_sha256": sha256(Path(__file__)),
        "target_count": n,
        "usable_base_points_each": protocol["base_size_actual_usable_points"],
        "source_verified_hits": source_hits,
        "descendant_native_verified_hits": native_hits,
        "source_only_targets": b,
        "descendant_native_only_targets": c,
        "native_minus_source_hit_rate": difference,
        "paired_approx_95_interval": [low, high],
        "median_source_lookup_ms_exploratory": median(source_ns)/1e6,
        "median_mapped_native_lookup_ms_exploratory": median(native_ns)/1e6,
        "median_mapped_native_over_source_exploratory": cost_ratio,
        "source_total_lookup_ms_per_verified_hit_including_misses":
            sum(source_ns)/1e6/source_hits if source_hits else None,
        "native_total_mapped_lookup_ms_per_verified_hit_including_misses":
            sum(native_ns)/1e6/native_hits if native_hits else None,
        "predeclared_rate_gate_passed": rate_gate,
        "exploratory_cost_gate_passed": cost_gate_exploratory,
        "decision": "advance_native_policy_for_new_implicit_PDP_test" if
            rate_gate and cost_gate_exploratory else "deprioritize_this_native_base_policy",
        "decision_scope": "N39 cofactor-projected first-x bases and exact group pair-index only; no N131 IC speed inference",
        "complete_ic_online_ms": None, "rho_online_ms": None, "speedup": None,
        "cpu_isolation": "unverified; wall-time ratios exploratory",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(analysis, indent=2) + "\n")
    print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    main()
