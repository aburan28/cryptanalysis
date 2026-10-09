#!/usr/bin/env python3
"""Freeze a single N41 full-coordinate mixed-cubic diagnostic run."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError("preserve first frozen protocol")
    inputs = {
        "arithmetic": GOAL / "n41_two_free_pair_occupancy_20261009/arithmetic_snapshot.py",
        "geometry": GOAL / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json",
        "decoded": GOAL / "n41_two_pair_mask_decoder_rank_20261008/decoded_rows.json",
        "holdout": GOAL / "n41_two_pair_mask_decoder_rank_20261008/holdout_rows.json",
    }
    protocol = {
        "status": "FROZEN", "kind": "n41_distinct_two_pair_full_xy_mixed_cubic_rank",
        "proposal_id": "Q20261009231000", "candidate_id": None, "run_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "field": "GF(2)[t]/(t^41+t^3+1)", "curve": "y^2+xy=x^3+1",
        "subgroup_order": 549756390943,
        "public_target_q": [1458168294740, 1672312028033],
        "factor_base_size": 256, "folded_columns": 26,
        "pair_rotations": [20, 30], "pair_domain_sizes": [1956, 1956],
        "row_count": 80000, "random_seed": 20261009231000,
        "row_order": "distinct saved decoded rows, distinct saved holdout rows, then deterministic distinct random index pairs with four different folded columns",
        "row_encoding": "18 bytes: one byte each seed XOR, six little-endian x, six little-endian y, two little-endian indices for each pair domain",
        "feature_order": "constant; degree-one and degree-two squarefree monomials on 93 bits in lexicographic index order; degree-three squarefree monomials containing one of first 12 seed bits in lexicographic order",
        "variable_order": "s2 bits 0..5, s3 bits 0..5, residual x bits 1..40, residual y bits 0..40",
        "feature_count": 48818, "coordinate_feature_count": 3322,
        "decision_rule": "Full rank on exact four-column-distinct rows rules out a universal equation in the declared 48818-feature family; a deficiency requires equation extraction and independent holdout evaluation before use as a filter.",
        "audit_seed": 20261009231001, "audit_rows": 256,
        "limits": {"workers": 1, "producer_wall_seconds": 180,
                   "rank_wall_seconds": 300, "rss_bytes": 4294967296,
                   "max_random_draws": 150000},
        "compiler": "clang++ -O3 -std=c++17 -I/var/tmp/sage-10.9-current/local/include -L/var/tmp/sage-10.9-current/local/lib -Wl,-rpath,/var/tmp/sage-10.9-current/local/lib rank.cpp -lm4ri -o rank",
        "inputs": {k: str(v) for k, v in inputs.items()},
        "input_sha256": {k: sha(v) for k, v in inputs.items()},
        "source_sha256": {name: sha(HERE / name) for name in
                          ("produce.py", "rank.cpp", "rank", "freeze.py")},
        "claim_boundary": "finite-row exact rank diagnostic on the frozen N41 public-point geometry; promote only a verified target-conditioned filter through unpinned N41 and source-bound N131 gates",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "protocol_sha256": sha(output),
                      "feature_count": protocol["feature_count"],
                      "row_count": protocol["row_count"]}))


if __name__ == "__main__":
    main()
