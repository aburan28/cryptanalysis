#!/usr/bin/env python3
"""Fast quotient-rank comparison with independent N41 subgroup points."""

from __future__ import annotations

import hashlib
import json
import resource
import time
from pathlib import Path

from holdout import FEATURES, feature_vector, insert_high, sha

HERE = Path(__file__).resolve().parent


def parity(value: int) -> int:
    return bin(value).count("1") & 1


def pair_nullspace(basis: dict[int, int]):
    pivot_order = sorted(basis)
    for free in range(FEATURES):
        if free in basis:
            continue
        equation = 1 << free
        for pivot in pivot_order:
            if parity(basis[pivot] & equation):
                equation |= 1 << pivot
        yield equation


def main():
    output = HERE / "subgroup_rank_result.json"
    if output.exists():
        raise FileExistsError("preserve first quotient-rank result")
    start = time.monotonic_ns()
    protocol_path = HERE / "protocol_subgroup_rank.json"
    protocol = json.loads(protocol_path.read_text())
    names = ("subgroup_control_rows", "initial_rows", "holdout_rows", "feature_script")
    paths = {name: (HERE / protocol[name]).resolve() for name in names}
    assert all(sha(path) == protocol[f"{name}_sha256"] for name, path in paths.items())
    subgroup = json.loads(paths["subgroup_control_rows"].read_text())["points"]
    initial = json.loads(paths["initial_rows"].read_text())["rows"]
    holdout = json.loads(paths["holdout_rows"].read_text())["rows"]
    assert len(subgroup) == len(initial) == len(holdout) == 8192
    assert protocol["feature_count"] == FEATURES
    pair_basis: dict[int, int] = {}
    for row in initial + holdout:
        insert_high(pair_basis, feature_vector(*row["sum_point"]))
    assert len(pair_basis) == protocol["expected_pair_rank"]
    equations = list(pair_nullspace(pair_basis))
    assert len(equations) == FEATURES - len(pair_basis) == 124
    subgroup_basis: dict[int, int] = {}
    quotient_basis: dict[int, int] = {}
    nonzero_quotient_rows = 0
    for point in subgroup:
        vector = feature_vector(*point)
        insert_high(subgroup_basis, vector)
        signature = 0
        for i, equation in enumerate(equations):
            signature |= parity(equation & vector) << i
        if signature:
            nonzero_quotient_rows += 1
        insert_high(quotient_basis, signature)
    result = {
        "kind": protocol["kind"],
        "status": "COMPLETE_QUOTIENT_RANK",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "feature_count": FEATURES,
        "pair_rows": len(initial) + len(holdout),
        "pair_rank": len(pair_basis),
        "pair_nullity": len(equations),
        "subgroup_control_rows": len(subgroup),
        "subgroup_rank": len(subgroup_basis),
        "nonzero_quotient_rows": nonzero_quotient_rows,
        "quotient_rank_increase": len(quotient_basis),
        "combined_rank": len(pair_basis) + len(quotient_basis),
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{name: sha(path) for name, path in paths.items()},
                          "protocol": sha(protocol_path),
                          "subgroup_rank": sha(Path(__file__))},
    }
    output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"pair_rank": len(pair_basis),
                      "subgroup_rank": len(subgroup_basis),
                      "quotient_rank_increase": len(quotient_basis),
                      "combined_rank": result["combined_rank"],
                      "wall_s": result["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
