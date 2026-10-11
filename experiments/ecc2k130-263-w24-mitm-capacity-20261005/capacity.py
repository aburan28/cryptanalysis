#!/usr/bin/env python3
"""Exact tuple-count screen for materialized W24/m6 group MITM tables.

This counts enumeration states, not distinct group sums and not the work of
algebraic PDP solvers. No curve arithmetic or timing extrapolation is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005"
CONFIG = BASE / "CONFIG.json"
SELECTION = BASE / "base_selection.json"
PRIMARY = BASE / "primary_workload.json"
RAM_BYTES = 4 * 1024**3


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output already exists: {args.out}")

    config = json.loads(CONFIG.read_text())
    selection = json.loads(SELECTION.read_text())
    primary = json.loads(PRIMARY.read_text())
    assert config["proposal_id"] == selection["proposal_id"] == "Q1420"
    assert config["candidate_id"] is selection["candidate_id"] is None
    assert selection["config_sha256"] == sha256(CONFIG)
    assert primary["target_count"] == 1
    workload_record = {key: value for key, value in primary.items()
                       if key != "workload_id"}
    workload_digest = hashlib.sha256(json.dumps(
        workload_record, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    assert primary["workload_id"] == workload_digest == "eee7f6ee5f6b"
    assert config["four_policies"] == [
        "source", "transported", "descendant_native", "pullback"
    ]
    columns = config["selected_signed_columns_each"]
    points = config["selected_usable_points_B_each"]
    assert points == 2 * columns
    for name in ("source", "descendant_native"):
        assert selection[name]["selected_signed_columns"] == columns
        assert selection[name]["selected_usable_points_B"] == points

    # Both distinct-input counts and repetition-allowed counts are retained.
    # Any literal exhaustive distinct-point half enumerator visits the former;
    # a materialized table also needs at least one addressable slot per row.
    pair_distinct = math.comb(points, 2)
    triple_distinct = math.comb(points, 3)
    pair_repetition = math.comb(points + 1, 2)
    triple_repetition = math.comb(points + 2, 3)
    assert pair_distinct < pair_repetition
    assert triple_distinct < triple_repetition
    counts = {
        "unordered_distinct_point_pairs": pair_distinct,
        "unordered_distinct_point_triples": triple_distinct,
        "unordered_pairs_allowing_repetition": pair_repetition,
        "unordered_triples_allowing_repetition": triple_repetition,
    }
    result = {
        "schema": "ecc2k130-w24-mitm-enumeration-capacity-v1",
        "proposal_id": "Q1420",
        "candidate_id": None,
        "workload_id": primary["workload_id"],
        "scope": "full materialized raw-point 2+4 pair index and 3+3 triple index only",
        "point_count_before_sign_folding_B": points,
        "signed_columns_before_frobenius_folding": columns,
        "curve_policy_counts_equal": True,
        "producer_sha256": sha256(Path(__file__)),
        "resource_envelope_bytes": RAM_BYTES,
        "counts": counts,
        "one_bit_per_distinct_tuple_bytes": {
            "pair": ceil_div(pair_distinct, 8),
            "triple": ceil_div(triple_distinct, 8),
        },
        "one_byte_per_distinct_tuple_to_ram_ratio_ceil": {
            "pair": ceil_div(pair_distinct, RAM_BYTES),
            "triple": ceil_div(triple_distinct, RAM_BYTES),
        },
        "one_bit_per_distinct_tuple_to_ram_ratio_ceil": {
            "pair": ceil_div(ceil_div(pair_distinct, 8), RAM_BYTES),
            "triple": ceil_div(ceil_div(triple_distinct, 8), RAM_BYTES),
        },
        "full_table_fits_4gib_at_one_bit_per_tuple": {
            "pair": ceil_div(pair_distinct, 8) <= RAM_BYTES,
            "triple": ceil_div(triple_distinct, 8) <= RAM_BYTES,
        },
        "input_sha256": {
            "config": sha256(CONFIG),
            "base_selection": sha256(SELECTION),
            "primary_workload": sha256(PRIMARY),
        },
        "method_boundary": (
            "Counts are of input tuples, not unique sum outputs. They exclude "
            "streaming, collision compression, target-adaptive joins, and "
            "implicit F4/F5/SAT/Gray-code/FES/crossbred approaches. No PDP "
            "yield, relation rank, scalar recovery, or speedup was measured."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "computed", "counts": counts,
                      "one_bit_per_distinct_tuple_to_ram_ratio_ceil":
                      result["one_bit_per_distinct_tuple_to_ram_ratio_ceil"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
