#!/usr/bin/env python3
"""Freeze Q1428's exact-field bilinear-span screen parameters."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    parent_path = PARENT / "q1427_interleaved_pair/protocol.json"
    parent = json.loads(parent_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    degrees = []
    for n in (53, 83):
        workload = parent["workloads"][f"n{n}_ordinary"]
        base = workload["stage_config_hash_input"]["factor_base"]
        w = base["normal_basis_weight_bound"]
        sizes = sorted({n, 3 * n // 4, n // 2, 24, 16, 12, 10,
                        8, 6, 4, 2, 0}, reverse=True)
        degrees.append({
            "degree_n": n,
            "curve_id": workload["curve_id"],
            "factor_base_actual_B": workload["factor_base_actual_B"],
            "folded_columns_K": workload["folded_columns_K"],
            "factor_base_enumerated_set_sha256": workload[
                "factor_base_enumerated_set_sha256"],
            "weight_bound": w,
            "free_suffix_sizes": sizes,
        })
    return {
        "kind": "q1428_frozen_bilinear_s3_partial_pair_span_screen",
        "proposal_id": "Q1428", "candidate_id": None,
        "isogeny": "none", "degrees": degrees,
        "seed": 1428, "samples_per_cell": 16,
        "sampling_law": (
            "For each degree and free-suffix size, independently draw "
            "nonzero m uniformly from field coordinates; choose exactly "
            "min(weight_bound, fixed_prefix_size) one positions for each "
            "leaf uniformly from the fixed prefix; leave the same final "
            "k coordinates free on both leaves. No target law is used."),
        "source_sha256": sha(HERE / "screen.py"),
        "q1427_protocol_sha256": sha(parent_path),
        "runtime_info_sha256": sha(runtime_path),
        "claim_boundary": (
            "A sound necessary-condition rank screen on synthetic "
            "partial assignments. It does not solve an ordinary query, "
            "measure natural relation yield, or project complete work."),
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
