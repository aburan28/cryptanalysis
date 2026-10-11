#!/usr/bin/env python3
"""Check Q1425 receipts against the frozen inputs, traces, and S3 oracle."""

from __future__ import annotations

import json

from hybrid import MeteredField, build_hybrid, exact_roots, root_lemma
from run import (CASES, HERE, canonical_hash, check_freeze, digest,
                 field, load_case, verify_relation)


def replay_relation(n, mode, reported):
    profile, _, _, _, _ = load_case(n, mode)
    values = reported["raw_leaf_x"]
    leaves = [list(range(1 + pair * n, 1 + (pair + 1) * n))
              for pair in range(4)]
    model = {bit: bool(value >> offset & 1)
             for row, value in zip(leaves, values)
             for offset, bit in enumerate(row)}
    assert verify_relation(profile, model, leaves) == reported


def verify_one(n, mode, frozen):
    stem = f"n{n}_{mode}"
    path = HERE / f"{stem}.json"
    trace_path = HERE / f"{stem}.trace.jsonl"
    assert path.is_file() and trace_path.is_file(), stem
    row = json.loads(path.read_text())
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    assert row["schema"] == "q1425-root-hybrid-run-v1"
    assert row["proposal_id"] == "Q1425"
    assert row["candidate_id"] is None and row["run_id"] is None
    assert row["isogeny"] == "none"
    assert row["n"] == n and row["mode"] == mode
    assert row["curve_id"] == CASES[n][0]
    assert row["factor_base_actual_B"] == CASES[n][2]
    assert row["factor_base_folded_columns_K"] == CASES[n][3]
    assert row["factor_base_enumerated_set_sha256"] == CASES[n][4]
    assert row["freeze_sha256"] == digest(HERE / "freeze.json")
    assert row["trace_sha256"] == digest(trace_path)
    assert row["trace_rows"] == row["solver_calls"] == len(trace)
    assert row["solver_calls"] <= frozen["limits"]["max_solver_calls"]
    assert len(row["refinement_lemmas"]) <= frozen["limits"]["max_refinements"]
    assert [event["solver_call"] for event in trace] == list(range(1, len(trace) + 1))
    assert row["status"] in ("VERIFIED_RELATION", "BOUNDED_UNKNOWN", "UNSAT")
    assert row["verified_relation"] is None or row["status"] == "VERIFIED_RELATION"
    if mode.startswith("ordinary"):
        assert row["workload_id"] == CASES[n][1]
        assert row["input_law"] == "ordinary"
    else:
        assert row["input_law"] == "known_solution_control"
    profile, parent, _, _, _ = load_case(n, mode)
    formula, leaves, mids, _, _ = build_hybrid(
        n, profile["normal_basis_weight_bound"],
        parent["raw_preimage_x_coordinates"], row["deferred_pairs"])
    assert formula.variables == row["formula"]["variables"]
    for lemma in row["refinement_lemmas"]:
        pair = lemma["pair"]
        assert pair in row["deferred_pairs"]
        roots = exact_roots(MeteredField(field.Onb(n)),
                            lemma["left_x"], lemma["right_x"])
        assert list(roots) == lemma["root_x"]
        clauses = root_lemma(leaves[2 * pair], leaves[2 * pair + 1],
                             mids[pair], lemma["left_x"],
                             lemma["right_x"], roots, lemma["branch_var"])
        assert len(clauses) == lemma["clauses"]
        assert canonical_hash(clauses) == lemma["clause_digest"]
    if row["status"] == "VERIFIED_RELATION":
        assert trace[-1]["relation_status"] == "verified_four_point_relation"
        replay_relation(n, mode, row["verified_relation"])
    parts = ("formula_build_seconds", "formula_load_seconds",
             "solver_wall_seconds", "lemma_oracle_and_add_seconds",
             "relation_check_seconds", "pdp_other_seconds")
    assert all(row[key] >= 0 for key in parts)
    total = sum(row[key] for key in parts)
    assert abs(total - row["pdp_wall_seconds"]) < 1e-4
    assert row["target_pdp_wall_seconds"] == (
        row["pdp_wall_seconds"] if mode.startswith("ordinary") else None)
    return {"case": stem, "status": row["status"],
            "solver_calls": len(trace),
            "root_lemmas": len(row["refinement_lemmas"]),
            "verified_relation": row["verified_relation"] is not None}


def main():
    frozen = check_freeze()
    rows = [verify_one(n, mode, frozen)
            for n in (53, 83) for mode in frozen["modes"]]
    summary = {"schema": "q1425-root-hybrid-verification-v1",
               "freeze_sha256": digest(HERE / "freeze.json"),
               "all_six_cells_checked": len(rows) == 6,
               "rows": rows}
    (HERE / "verification.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
