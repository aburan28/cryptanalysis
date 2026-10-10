#!/usr/bin/env python3
"""Replay the Q1426 frozen lift choices, root lemmas, and run receipts."""

from __future__ import annotations

import json

import run as experiment
from hybrid import MeteredField, build_hybrid, exact_roots, root_lemma


def replay_relation(n, profile, reported):
    leaves = [list(range(1 + pair * n, 1 + (pair + 1) * n))
              for pair in range(4)]
    model = {bit: bool(value >> offset & 1)
             for row, value in zip(leaves, reported["raw_leaf_x"])
             for offset, bit in enumerate(row)}
    assert experiment.prior.verify_relation(profile, model, leaves) == reported


def verify_one(n, index, frozen):
    stem = f"n{n}_lift{index:03d}"
    path = experiment.HERE / f"{stem}.json"
    trace_path = experiment.HERE / f"{stem}.trace.jsonl"
    assert path.is_file() and trace_path.is_file(), stem
    row = json.loads(path.read_text())
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    case = frozen["cases"][str(n)]
    profile, parent, _, parent_path, _ = experiment.prior.load_case(
        n, "ordinary_both_lazy")
    assert row["schema"] == "q1426-lift-slice-run-v1"
    assert row["proposal_id"] == "Q1426"
    assert row["candidate_id"] is None and row["run_id"] is None
    assert row["isogeny"] == "none"
    assert row["n"] == n and row["curve_id"] == case["curve_id"]
    assert row["workload_id"] == case["workload_id"]
    assert row["factor_base_actual_B"] == case["B"]
    assert row["factor_base_folded_columns_K"] == case["K"]
    assert row["factor_base_enumerated_set_sha256"] == case["base_digest"]
    assert row["lift_index"] == index
    assert row["lift_count"] == case["raw_lift_count"]
    assert row["selected_lifts"] == case["selected_indices"]
    assert row["target_x_coords"] == parent["raw_preimage_x_coordinates"][index]
    assert row["ordinary_receipt_sha256"] == experiment.prior.digest(parent_path)
    assert row["freeze_sha256"] == experiment.prior.digest(
        experiment.HERE / "freeze.json")
    assert row["trace_sha256"] == experiment.prior.digest(trace_path)
    assert row["trace_rows"] == row["solver_calls"] == len(trace)
    assert len(trace) <= frozen["limits"]["max_solver_calls"]
    assert len(row["root_lemmas"]) <= frozen["limits"]["max_refinements"]
    assert [event["solver_call"] for event in trace] == list(range(1, len(trace) + 1))
    assert row["status"] in ("VERIFIED_RELATION", "BOUNDED_UNKNOWN", "UNSAT")
    assert row["natural_relation_yield_estimate"] is None
    assert row["cost_per_novel_rank_row"] is None
    assert row["field_operations_complete"] is None
    assert row["n131_complete_cold_work_log2"] is None
    assert row["n131_complete_online_one_target_work_log2"] is None
    formula, leaves, mids, _, _ = build_hybrid(
        n, case["normal_basis_weight_bound"], [row["target_x_coords"]],
        (0, 1))
    assert formula.variables == row["formula"]["variables"]
    assert len(formula.clauses) == row["formula"]["cnf_clauses"]
    assert len(formula.xors) == row["formula"]["xor_rows"]
    for lemma in row["root_lemmas"]:
        pair = lemma["pair"]
        assert pair in (0, 1)
        roots = exact_roots(MeteredField(experiment.prior.field.Onb(n)),
                            lemma["left_x"], lemma["right_x"])
        assert list(roots) == lemma["root_x"]
        clauses = root_lemma(leaves[2 * pair], leaves[2 * pair + 1],
                             mids[pair], lemma["left_x"], lemma["right_x"],
                             roots, lemma["branch_var"])
        assert len(clauses) == lemma["clauses"]
        assert experiment.prior.canonical_hash(clauses) == lemma["clause_digest"]
    if row["status"] == "VERIFIED_RELATION":
        assert row["verified_relation"] is not None
        assert trace[-1]["relation_status"] == "verified_four_point_relation"
        replay_relation(n, profile, row["verified_relation"])
    else:
        assert row["verified_relation"] is None
    phases = ("formula_build_seconds", "formula_load_seconds",
              "solver_wall_seconds", "lemma_oracle_and_add_seconds",
              "relation_check_seconds", "pdp_other_seconds")
    assert all(row[name] >= 0 for name in phases)
    assert abs(sum(row[name] for name in phases) -
               row["target_pdp_wall_seconds"]) < 1e-4
    if row["peak_rss_units"].startswith("bytes"):
        assert row["peak_parent_rss_raw"] < frozen["limits"]["rss_mib"] * 2**20
    return {"case": stem, "status": row["status"],
            "first_sat_model": any(event["state"] == "SAT" for event in trace),
            "root_calls": row["root_calls"].get("oracle_misses", 0),
            "solver_calls": len(trace)}


def main():
    frozen = experiment.check_freeze()
    rows = [verify_one(n, index, frozen)
            for n in (53, 83)
            for index in frozen["cases"][str(n)]["selected_indices"]]
    assert len(rows) == 8
    result = {"schema": "q1426-lift-slice-verification-v1",
              "all_eight_cells_checked": True,
              "freeze_sha256": experiment.prior.digest(
                  experiment.HERE / "freeze.json"),
              "rows": rows}
    (experiment.HERE / "verification.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
