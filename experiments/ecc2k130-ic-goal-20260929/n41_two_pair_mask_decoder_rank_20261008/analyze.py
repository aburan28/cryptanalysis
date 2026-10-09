#!/usr/bin/env python3
"""Compare N41 pair-sum and curve-point quadratic feature row spaces."""

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


def nullspace_basis(high_rows: dict[int, int]):
    free = [i for i in range(FEATURES) if i not in high_rows]
    pivots = sorted(high_rows)
    for index in free:
        equation = 1 << index
        for pivot in pivots:
            if parity(high_rows[pivot] & equation):
                equation |= 1 << pivot
        assert all(not parity(row & equation)
                   for row in high_rows.values())
        yield equation


def main():
    result_path = HERE / "analysis_result.json"
    relation_path = HERE / "pair_relation.json"
    if result_path.exists() or relation_path.exists():
        raise FileExistsError("preserve first analysis")
    start = time.monotonic_ns()
    protocol_path = HERE / "protocol_analysis.json"
    protocol = json.loads(protocol_path.read_text())
    names = ("initial_rows", "holdout_rows", "curve_control_rows", "feature_script")
    paths = {name: (HERE / protocol[name]).resolve() for name in names}
    assert all(sha(path) == protocol[f"{name}_sha256"] for name, path in paths.items())
    assert FEATURES == protocol["feature_count"]
    initial = json.loads(paths["initial_rows"].read_text())
    holdout = json.loads(paths["holdout_rows"].read_text())
    control = json.loads(paths["curve_control_rows"].read_text())
    assert initial["curve_id"] == holdout["curve_id"] == control["curve_id"] == protocol["curve_id"]
    pair_points = [r["sum_point"] for r in initial["rows"] + holdout["rows"]]
    control_points = control["points"]
    pair_basis: dict[int, int] = {}
    control_basis: dict[int, int] = {}
    for x, y in pair_points:
        insert_high(pair_basis, feature_vector(x, y))
    control_vectors = [feature_vector(x, y) for x, y in control_points]
    for row in control_vectors:
        insert_high(control_basis, row)
    assert len(pair_basis) == protocol["expected_input_ranks"]["pair_sum"]
    assert len(control_basis) == protocol["expected_input_ranks"]["curve_control"]
    union_basis = dict(pair_basis)
    for row in control_basis.values():
        insert_high(union_basis, row)
    selected = None
    selected_weight = FEATURES + 1
    relations = 0
    nonzero_on_control = 0
    for equation in nullspace_basis(pair_basis):
        relations += 1
        witness = next((index for index, row in enumerate(control_vectors)
                        if parity(equation & row)), None)
        if witness is not None:
            nonzero_on_control += 1
            weight = bin(equation).count("1")
            if weight < selected_weight:
                selected = equation, witness
                selected_weight = weight
    assert relations == FEATURES - len(pair_basis)
    assert selected is not None
    equation, witness = selected
    term_indices = [i for i in range(FEATURES) if equation >> i & 1]
    relation_record = {
        "kind": "n41_two_pair_coordinate_quadratic_candidate_equation",
        "curve_id": protocol["curve_id"],
        "term_indices": term_indices,
        "feature_count": FEATURES,
        "term_count": len(term_indices),
        "control_witness_index": witness,
        "control_witness_point": control_points[witness],
        "control_witness_evaluation": 1,
        "pair_sample_points": len(pair_points),
        "pair_sample_evaluations_nonzero": 0,
        "status": "SAMPLE_EQUATION_PENDING_EXHAUSTIVE_CHECK",
    }
    relation_path.write_text(json.dumps(relation_record, sort_keys=True, separators=(",", ":")) + "\n")
    result = {
        "kind": protocol["kind"],
        "status": "RANK_COMPARISON_COMPLETE",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "feature_count": FEATURES,
        "pair_sample_rows": len(pair_points),
        "control_sample_rows": len(control_points),
        "pair_rank": len(pair_basis),
        "control_rank": len(control_basis),
        "union_rank": len(union_basis),
        "pair_nullity": relations,
        "pair_nullspace_basis_vectors_nonzero_on_control": nonzero_on_control,
        "selected_relation_terms": len(term_indices),
        "selected_relation_control_witness_index": witness,
        "exploratory_wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": {**{name: sha(path) for name, path in paths.items()},
                          "protocol": sha(protocol_path),
                          "analyze": sha(Path(__file__)),
                          "pair_relation": sha(relation_path)},
        "claim_boundary": protocol["claim_boundary"],
    }
    result_path.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"pair_rank": len(pair_basis), "control_rank": len(control_basis),
                      "union_rank": len(union_basis), "relation_terms": len(term_indices),
                      "control_witness": witness,
                      "wall_s": result["exploratory_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
