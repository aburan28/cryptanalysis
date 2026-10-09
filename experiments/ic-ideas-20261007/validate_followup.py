#!/usr/bin/env python3
"""Validate final follow-up receipts without promoting them to IC1 runs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((RESULTS / name).read_text())


def main():
    assert read("sage_runtime_info_followup.json")["status"] == "verified"
    names = {
        "G1": "g1_template_followup_final.json",
        "G2": "g2_barrel_followup_final.json",
        "G4": "g4_frobenius_followup_final.json",
        "A1": "a1_rank_followup_final.json",
        "A2": "a2_encoding_followup_final.json",
        "N1": "n1_crt_followup_final.json",
    }
    runs = {idea: read(name) for idea, name in names.items()}
    source_hash = sha(HERE / "followup_probes.py")
    for idea, run in runs.items():
        assert run["proposal_id"] == idea
        assert run["candidate_id"] is None and run["run_id"] is None
        assert run["source_sha256"] == source_hash, idea

    for cell in runs["G1"]["cells"]:
        assert cell["targets"] == 16
        assert all(cell["cached_rows_equal_fresh"])
        assert sum(cell["same_pivot_schedule_as_first"]) < 16
    assert [(cell["field_degree"], cell["binary_row_rank"],
             cell["dft_nonzero_character_count"]) for cell in runs["G2"]["cells"]] == [
                 (19, 19, 19), (23, 23, 23)]

    g3_operator = read("g3_operator_followup.json")
    g3_full = read("g3_full_rows_followup.json")
    for run, source in ((g3_operator, "followup_g3.py"),
                        (g3_full, "g3_n41_sparse.py")):
        assert run["proposal_id"] == "G3"
        assert run["candidate_id"] is None and run["run_id"] is None
        assert run["source_sha256"] == sha(HERE / source)
    assert g3_operator["operator_transpose_bilinear_check"]
    assert g3_operator["full_squarefree_columns"] == 100_315_659
    assert g3_full["status"] == "COMPLETE"
    assert g3_full["rows_built"] == g3_full["expected_rows"] == 2_017_933
    assert g3_full["nonzero_entries"] == 247_444_987
    assert g3_full["frozen_builder_sha256"] == g3_operator["frozen_builder_sha256"]

    g4 = runs["G4"]
    assert len(g4["cells"]) == 12
    assert all(c["field_rational_hits"] == c["frobenius_filtered_hits"] ==
               c["trace_filtered_hits"] for c in g4["cells"])
    assert sum(c["false_positives_removed"] for c in g4["cells"]) > 0

    a1 = runs["A1"]
    assert a1["classes_after_sign_frobenius"] == 10
    assert a1["toy_original_rank"] == a1["toy_rank_after_known_log_transport"]
    geometry = read("a1_geometry_n23_followup_final_v2.json")
    assert geometry["source_sha256"] == sha(HERE / "a1_geometry_followup.py")
    assert geometry["proposal_id"] == "A1"
    assert geometry["candidate_id"] is None and geometry["run_id"] is None
    assert len(geometry["target_points"]) == 16
    seed, closure = geometry["cells"]
    assert seed["independent_log_columns_after_known_transport"] == 1
    assert closure["independent_log_columns_after_known_transport"] == 1
    assert seed["actual_usable_B"] < closure["actual_usable_B"]
    assert seed["m3_hits"] < closure["m3_hits"]
    assert geometry["closure_transport_verified_points"] == closure["actual_usable_B"]
    n53 = read("a1_n53_k600_followup_final.json")
    assert n53["source_sha256"] == sha(HERE / "a1_n53_k600_followup.py")
    assert n53["proposal_id"] == "A1"
    assert n53["candidate_id"] is None and n53["run_id"] is None
    assert n53["status"] == "COMPLETE"
    assert (n53["seed_folded_columns"], n53["seed_actual_usable_B"],
            n53["closure_folded_columns"], n53["closure_actual_usable_B"]) == (
                600, 63_600, 6_000, 636_000)
    assert n53["multiplier_classes_after_sign_frobenius"] == 10
    assert n53["scalar_image_operations"] == 6_000

    a2 = runs["A2"]
    assert a2["distinct_x"] == 17_296
    assert a2["collision_histogram"] == {"1": 17_296}
    assert a2["x47_equals_1"] == a2["x263_equals_1"] == 0

    n1 = runs["N1"]
    assert n1["planted_samples"] == 256
    assert n1["polynomial_section_exact"] == 0
    assert n1["crt_section_exact"] == 256

    print(json.dumps({"status": "PASS", "source_sha256": source_hash,
                      "checked_receipts": names,
                      "g3_full_rows": g3_full["rows_built"]}, sort_keys=True))


if __name__ == "__main__":
    main()
