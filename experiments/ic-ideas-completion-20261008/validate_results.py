#!/usr/bin/env python3
"""Cross-check final-source receipts and their algebraic/resource gates."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name: str, source: str | None = None):
    path = HERE / name
    result = json.loads(path.read_text())
    assert result["candidate_id"] is None and result["run_id"] is None
    if source is not None:
        assert result["source_sha256"] == hashlib.sha256(
            (HERE / source).read_bytes()).hexdigest(), name
    return result


def main():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    g1 = read("g1_ideal_trace.json", "g1_full_ideal_trace.py")
    assert [(cell["arity"], sum(row["learned_spans_full_ideal"]
                                  for row in cell["cells"]))
            for cell in g1["cells"]] == [(2, 1), (3, 2)]
    for cell in g1["cells"]:
        for row in cell["cells"]:
            assert row["full_ideal_dimension"] + row["solution_count"] == (
                1 << cell["boolean_variables"])
            assert row["learned_rank"] <= row["full_ideal_dimension"]
    for name, expected in (("g2_n19.json", (19, 8399, [443, 442])),
                           ("g2_n23.json", (23, 14767, [643, 642, 642]))):
        data = read(name, "g2_degree3_blocks.py")["cells"][0]
        assert (data["field_degree"], data["binary_rank"],
                [block["rank"] for block in data["character_blocks"]]) == expected
        assert sum(block["rank"]*block["orbit_size"] for block in
                   data["character_blocks"]) == data["binary_rank"]
    g2_projection = read("g2_n131_projection.json", "g2_n131_projection.py")
    n131 = g2_projection["cells"][-1]
    assert n131["n"] == 131 and n131["nontrivial_character_extension_degree"] == 130
    assert n131["dense_nontrivial_block_coefficient_bytes_floor"] > 34_000_000_000
    g3 = read("g3_krylov_budget.json", "g3_krylov_budget.py")
    assert g3["rows"] == 2_017_933 and g3["nnz"] == 247_444_987
    assert g3["degree_five_ambient_columns"] == 4_394_565_333
    assert g3["conventional_block_wiedemann_budgets"][1][
        "four_byte_index_stream_bytes"] > 124_000_000_000_000
    g4_equivalence = read("g4_chain_equivalence.json", "g4_chain_equivalence.py")
    assert len(g4_equivalence["cells"]) == 12
    assert g4_equivalence["total_false_closure_hits_removed"] == 8
    for name, index in (("g4_target0_chain4_boolean_final.json", 0),
                        ("g4_target2_chain4_boolean.json", 2)):
        data = read(name, "g4_matched_groebner.py")
        assert len(data["rows"]) == 2
        assert {row["encoding"] for row in data["rows"]} == {
            "mixed_chain4", "boolean"}
        assert all(row["target_index"] == index and row["status"] == "completed"
                   for row in data["rows"])
        mixed = next(row for row in data["rows"] if row["encoding"] == "mixed_chain4")
        boolean = next(row for row in data["rows"] if row["encoding"] == "boolean")
        assert (mixed["variables"], mixed["input_equations"],
                mixed["maximum_input_degree"]) == (16, 18, 4)
        assert (boolean["variables"], boolean["input_equations"],
                boolean["maximum_input_degree"]) == (25, 63, 3)
        assert mixed["target_point"] == boolean["target_point"]
        assert mixed["target_point"] == g4_equivalence["cells"][index]["target_point"]
    g4_chains = read("g4_chains.json", "g4_matched_groebner.py")
    assert [row["status"] for row in g4_chains["rows"]] == ["completed", "completed"]
    g4_initial = read("g4_matched.json", "g4_matched_groebner_v0.py")
    assert any(row["status"] == "error" for row in g4_initial["rows"])
    assert any(row["status"] == "timeout" for row in g4_initial["rows"])
    a1 = read("a1_fastindex_budget.json", "a1_fastindex_budget.py")
    assert a1["multiplier_classes_after_sign_frobenius"] == 10
    assert a1["cases"]["600_seed_full_closure"]["s3_root_calls"] == 1_908_000_000
    assert a1["cases"]["600_seed_full_closure"][
        "combined_pre_merge_bytes_lower_bound"] > 100_000_000_000
    a2 = read("a2_selector_frontier.json", "a2_selector_frontier.py")
    assert a2["weight_two_or_three_distinct_x"] == 17_296
    assert a2["x47_membership_hits"] == a2["x263_membership_hits"] == 0
    assert a2["direct_selector_dimensions"]["degree4_column_ratio"] > 10
    n1 = read("n1_gate.json", "n1_augmentation_gate.py")
    assert n1["cyclotomic_factor_degrees"] == [1, 23, 23]
    assert n1["sampled_valid_field_identities"] == 256
    assert n1["impossible_exact_lifts_with_fixed_even_leaves"] == 256
    assert n1["kernel_parity_repair"]["minimum_odd_kernel_weight"] == 11
    assert n1["kernel_parity_repair"]["enumerated_nonzero_kernel_words"] == 2**24-1
    print(json.dumps({"status": "passed", "proposal_ids":
        ["G1", "G2", "G3", "G4", "A1", "A2", "N1"],
        "checked_source_receipts": 13}, sort_keys=True))


if __name__ == "__main__":
    main()
