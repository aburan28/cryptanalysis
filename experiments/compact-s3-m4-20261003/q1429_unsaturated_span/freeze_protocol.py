#!/usr/bin/env python3
"""Freeze Q1429's unsaturated partial-pair span and exact-root comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    parent_path = PARENT / "q1427_interleaved_pair/protocol.json"
    q1428_path = PARENT / "q1428_bilinear_span/protocol.json"
    support_path = PARENT / "q1425_reverse_pair/pair_support_screen.json"
    parent = json.loads(parent_path.read_text())
    support = json.loads(support_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    degrees = []
    for n, sizes, slacks, samples in (
            (53, [16, 14, 12, 10], [1, 2], 16),
            (83, [24, 20, 18, 16], [1, 2], 16),
            (131, [36, 32, 28], [2], 4)):
        screen = next(row for row in support["rows"]
                      if row["field_degree_n"] == n)
        if n in (53, 83):
            workload = parent["workloads"][f"n{n}_ordinary"]
            assert screen["curve_id"] == workload["curve_id"]
            assert screen["factor_base_enumerated_set_sha256"] == workload[
                "factor_base_enumerated_set_sha256"]
            assert screen["actual_usable_factor_base_points_B"] == workload[
                "factor_base_actual_B"]
            assert screen["folded_columns_K"] == workload["folded_columns_K"]
        degrees.append({
            "degree_n": n,
            "curve_id": screen["curve_id"],
            "factor_base_actual_B": screen[
                "actual_usable_factor_base_points_B"],
            "folded_columns_K": screen["folded_columns_K"],
            "factor_base_enumerated_set_sha256": screen[
                "factor_base_enumerated_set_sha256"],
            "weight_bound": screen["normal_basis_weight_bound"],
            "free_suffix_sizes": sizes,
            "weight_slacks": slacks,
            "samples_per_cell": samples,
        })
    return {
        "kind": "q1429_frozen_unsaturated_s3_span_vs_exact_completion",
        "proposal_id": "Q1429", "candidate_id": None,
        "isogeny": "none", "degrees": degrees,
        "seed": 1429,
        "maximum_exact_root_calls_per_sample": 1000,
        "sampling_law": (
            "Independently draw nonzero m uniformly from exact field "
            "coordinates. Fix exactly w-slack one bits on each leaf in "
            "the first n-k normal-basis coordinates, chosen uniformly "
            "without replacement; leave the final k bits free. Exact "
            "completion enumerates every a extension of weight at most "
            "w and checks all S3 roots for b against the fixed prefix "
            "and weight bound. No public target law is used."),
        "source_sha256": sha(HERE / "run_screen.py"),
        "dependency_sha256": {
            "q1428_bilinear_span/screen.py": sha(
                PARENT / "q1428_bilinear_span/screen.py"),
            "s3_root_oracle.py": sha(PARENT / "s3_root_oracle.py"),
            "chain_s3.py": sha(PARENT / "chain_s3.py"),
        },
        "field_source_sha256": sha(ROOT / "ecc2k130/codegen/field.py"),
        "q1427_protocol_sha256": sha(parent_path),
        "q1428_protocol_sha256": sha(q1428_path),
        "q1425_pair_support_sha256": sha(support_path),
        "runtime_info_sha256": sha(runtime_path),
        "claim_boundary": (
            "Synthetic partial-pair method screen, not an ordinary "
            "query, relation-yield measurement, or complete N131 work "
            "projection. Root counts and span columns are distinct work "
            "units; no timing speedup claim follows."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), sort_keys=True, indent=2) + "\n"
    if args.check:
        assert PROTOCOL.read_text() == content
    else:
        assert not PROTOCOL.exists()
        PROTOCOL.write_text(content)
    print(PROTOCOL)


if __name__ == "__main__":
    main()
