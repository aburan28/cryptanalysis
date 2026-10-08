#!/usr/bin/env python3
"""Check provenance and cross-receipt invariants of the retained stage runs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def read(name):
    return json.loads((RESULTS / name).read_text())


def main():
    source_hash = hashlib.sha256((HERE / "sage_probes.py").read_bytes()).hexdigest()
    names = {
        "G1": "g1_final.json", "G2": "g2_final_current.json",
        "G4": "g4_final_current.json", "A1": "a1_final.json",
        "A2": "a2_final.json", "N1": "n1_final_current_retry.json"}
    runs = {idea: read(name) for idea, name in names.items()}
    for idea, run in runs.items():
        assert run["proposal_id"] == idea
        assert run["candidate_id"] is None and run["run_id"] is None
        assert run["source_sha256"] == source_hash, idea
    assert read("sage_runtime_info.json")["status"] == "verified"

    g1 = runs["G1"]
    assert {cell["arity"] for cell in g1["cells"]} == {2, 3}
    for cell in g1["cells"]:
        assert cell["target_count"] == len(cell["same_echelon_basis"]) == 16
        assert not cell["passes_table_falsifier"]

    g2 = runs["G2"]
    assert [cell["irreducible_rational_blocks"] for cell in g2["cases"]] == [2, 3, 2]
    for cell in g2["cases"]:
        module = cell["degree2_monomial_module"]
        assert (module["trivial_character_dimension"] +
                sum(module["nontrivial_rational_block_dimensions"]) ==
                module["squarefree_columns"])

    g3 = read("g3_degree4_complete.json")
    assert g3["status"] == "COLUMN_LIMIT"
    assert g3["rows_built"] < g3["expected_rows"]
    assert g3["observed_distinct_columns"] >= 12_000_000
    assert g3["nonzero_entries"] > 0
    g3_smoke = read("g3_smoke_current.json")
    g3_source_hash = hashlib.sha256((HERE / "g3_n41_sparse.py").read_bytes()).hexdigest()
    assert g3_smoke["source_sha256"] == g3_source_hash
    assert g3_smoke["status"] == "ROW_LIMIT" and g3_smoke["rows_built"] == 1000

    g4 = runs["G4"]
    assert g4["mixed_groebner_status"] == "completed"
    assert g4["boolean_f4"]["status"] == "completed"
    assert g4["field_rational_intermediate_assignments"] < g4[
        "algebraic_closure_intermediate_assignments"]

    a1 = runs["A1"]
    assert a1["curve_id"] == "EC1N53Ckb1h888961ed110e"
    assert a1["multipliers_up_to_sign"] == 21
    assert a1["classes_after_existing_sign_frobenius_folding"] == 10
    assert (a1["sample_base_points"], a1["sample_original_folded_columns"],
            a1["closure_folded_columns"]) == (600, 6, 60)

    a2 = runs["A2"]
    assert len(a2["target_points"]) == 16
    assert [(cell["actual_usable_B"], cell["folded_x_columns"])
            for cell in a2["cells"]] == [(230, 5), (230, 5)]
    assert not a2["claimed_membership_equation_valid"]
    assert [cell["m3_hits"] for cell in a2["cells"]] == [8, 11]
    for cell in a2["cells"]:
        lo, hi = cell["m3_wilson95"]
        assert lo <= cell["m3_hits"]/16 <= hi

    n1 = runs["N1"]
    assert n1["planted_s3_samples"] == 256 and n1["exact_lifts"] == 0
    print(json.dumps({"status": "PASS", "source_sha256": source_hash,
                      "checked_final_receipts": names,
                      "g3_bounded_rows": g3["rows_built"]}, sort_keys=True))


if __name__ == "__main__":
    main()
