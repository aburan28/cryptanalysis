#!/usr/bin/env python3
"""Check immutable IC lead receipts, source hashes, and cross-run invariants."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parent / "ic-ideas-completion-20261008"
PRIOR = HERE.parent / "ic-ideas-20261007"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name, source, proposal):
    value = json.loads((HERE / name).read_text())
    assert value["proposal_id"] == proposal
    assert value["candidate_id"] is None and value["run_id"] is None
    assert value["source_sha256"] == sha(HERE / source)
    return value


def main():
    assert json.loads((HERE / "sage_runtime_info.json").read_text())
    trace = read("g1_f4_trace.json", "g1_f4_trace.py", "G1")
    assert [(c["arity"], c["exact_basis_equal_count"],
             c["solution_set_equal_count"]) for c in trace["cells"]] == [
                 (2, 1, 1), (3, 2, 8)]
    audit = read("g1_f4_audit.json", "g1_f4_audit.py", "G1")
    assert len(audit["audited_cells"]) == 4
    assert all(c["certificate_verified"] and c["fresh_basis_solution_set_equal"]
               for c in audit["audited_cells"])
    symbolic = read("g1_f4_symbolic.json", "g1_f4_symbolic.py", "G1")
    assert symbolic["native_symbolic_source_sha256"] == sha(HERE / "native_f4_symbolic.cpp")
    assert [(c["arity"], c["fresh_completed"], c["replay_completed"],
             c["exact_basis_equal_count"]) for c in symbolic["cells"]] == [
                 (2, 16, 10, 10), (3, 15, 2, 2)]
    assert all(t["fresh_truth_set_equal"] is True for c in symbolic["cells"]
               for t in c["targets"] if t["fresh_status"] == "gb")
    assert all(t["replay_truth_set_equal"] is True for c in symbolic["cells"]
               for t in c["targets"] if t["replay_status"] == "gb")

    g2 = read("g2_f4_control.json", "g2_f4_control.py", "G2")
    g2q = read("g2_f4_qualification.json", "g2_f4_qualification.py", "G2")
    assert g2["invariant_input_generators"] == g2q["invariant_input_generators"] == 191
    assert [x["max_work"] for x in g2q["attempts"]] == [50_000_000,
                                                            1_000_000_000,
                                                            5_000_000_000]
    assert all(x["status"] == "inconclusive" for x in g2q["attempts"])
    for n, rank in ((19, 8399), (23, 14767)):
        block = json.loads((COMPLETION / f"g2_n{n}.json").read_text())["cells"][0]
        assert block["binary_rank"] == block["reconstructed_binary_rank"] == rank

    g3 = json.loads((COMPLETION / "g3_krylov_budget.json").read_text())
    assert (g3["rows"], g3["ambient_columns"], g3["nnz"]) == (
        2_017_933, 100_315_659, 247_444_987)
    assert g3["conventional_block_wiedemann_budgets"][1][
        "four_byte_index_stream_bytes"] > 124_000_000_000_000

    g4 = read("g4_backend_gate.json", "g4_backend_gate.py", "G4")
    assert [(x["algorithm"], x["status"]) for x in g4["backend_rows"]] == [
        ("msolve", "unsupported"), ("libsingular:std", "completed")]
    assert g4["available_macaulay2_executable"] is None
    chain = json.loads((COMPLETION / "g4_chain_equivalence.json").read_text())
    assert chain["total_false_closure_hits_removed"] == 8

    a1 = read("a1_equal_geometry.json", "a1_equal_geometry.py", "A1")
    assert [(c["actual_usable_B"], c["verified_triple_hits"], c["relation_rank"],
             c["first_full_rank_query"], c["scalar_replay_on_G"])
            for c in a1["cells"]] == [(230, 156, 5, 10, True),
                                     (230, 74, 1, 3, True)]
    a1n53 = read("a1_n53_seed600_yield.json", "a1_n53_seed600_yield.py", "A1")
    assert a1n53["factor_base_folded_columns"] == 600
    assert a1n53["factor_base_usable_B"] == 63_600
    if (HERE / a1n53["raw_result_path"]).exists():
        assert a1n53["raw_result_sha256"] == sha(HERE / a1n53["raw_result_path"])
    matched = read("a1_n53_matched_seed_q64.json", "a1_n53_matched_yield.py", "A1")
    assert matched["policy"] == "seed" and matched["query_count_cap"] == 64
    assert matched["factor_base_geometric_columns"] == 600
    assert matched["factor_base_usable_B"] == 63_600
    assert matched["status"] == "timeout_600s"
    assert matched["query_attempts_completed"] is None
    assert matched["raw_result_sha256"] == sha(HERE / matched["raw_result_path"])
    assert matched["solver_source_sha256"] == sha(
        HERE / "a1_n53_closure/src/main.rs")
    one = read("a1_n53_matched_seed_q1.json", "a1_n53_matched_yield.py", "A1")
    assert one["status"] == "timeout_600s"
    assert one["query_count_cap"] == 1 and one["query_attempts_completed"] is None
    assert one["raw_result_sha256"] == sha(HERE / one["raw_result_path"])
    for columns, queries in ((200, 32), (600, 64), (600, 128)):
        for policy in ("seed", "closure"):
            prefix = f"a1_n53_pair_{policy}_k{columns}_q{queries}"
            pair = read(prefix + ".json", "a1_n53_pair_yield.py", "A1")
            assert pair["status"] == "completed_verified"
            assert pair["actual_usable_B"] == columns * 106
            assert pair["pair_source_sha256"] == sha(
                HERE / "a1_n53_closure/src/bin/pair_probe.rs")
            assert pair["shared_source_sha256"] == sha(
                HERE / "a1_n53_closure/src/main.rs")
            assert pair["build_source_sha256"] == sha(
                HERE / "a1_n53_closure/build.rs")
            assert pair["raw_sha256"] == sha(HERE / pair["raw_record"])
            assert pair["progress_sha256"] == sha(HERE / pair["progress_record"])
            raw = json.loads((HERE / pair["raw_record"]).read_text())
            assert raw["verified_hits"] == pair["verified_hits"]
            assert raw["rank"] == pair["novel_rows"]
            assert sum(row["hit"] for row in raw["rows"]) == raw["verified_hits"]
            assert sum(row["novel_row"] for row in raw["rows"]) == raw["rank"]
    compare = read("a1_n53_pair_comparison.json", "a1_n53_pair_compare.py", "A1")
    assert [(cell["policy"], cell["verified_hits"], cell["novel_rows"],
             cell["independent_log_columns"]) for cell in compare["cells"]] == [
                 ("seed", 56, 56, 600), ("closure", 57, 55, 60)]
    assert compare["paired_outcomes"] == {"both": 49, "seed_only": 7,
                                           "closure_only": 8, "neither": 0}
    assert compare["paired_exact_two_sided_p"] == 1.0
    replay = read("a1_n53_pair_sage_verification.json",
                  "a1_n53_pair_sage_verification.py", "A1")
    assert replay["all_64_matched_target_scalar_replays"]
    assert [(cell["policy"], cell["verified_hits"], len(cell["witnesses"]))
            for cell in replay["cells"]] == [
                ("seed", 56, 56), ("closure", 57, 57)]
    for cell in replay["cells"]:
        policy = cell["policy"]
        prefix = f"a1_n53_pair_{policy}_k600_q64"
        assert cell["raw_sha256"] == sha(HERE / f"{prefix}_raw.json")
        assert cell["receipt_sha256"] == sha(HERE / f"{prefix}.json")
        assert all(w["sign_assignments_matching_target"] >= 1
                   for w in cell["witnesses"])
    compare128 = read("a1_n53_pair_comparison_128.json",
                      "a1_n53_pair_compare_128.py", "A1")
    assert [(cell["policy"], cell["verified_hits"], cell["novel_rows"])
            for cell in compare128["cells"]] == [
                ("seed", 111, 111), ("closure", 111, 60)]
    assert compare128["paired_outcomes"] == {
        "both": 94, "seed_only": 17, "closure_only": 17, "neither": 0}
    assert compare128["paired_exact_two_sided_p"] == 1.0
    memory_rows = []
    for policy in ("seed", "closure"):
        memory = read(f"a1_n53_memory_{policy}.json",
                      "a1_n53_memory_probe.py", "A1")
        assert memory["status"] == "completed_verified"
        assert memory["actual_usable_B"] == 63_600
        assert memory["pair_source_sha256"] == sha(
            HERE / "a1_n53_closure/src/bin/pair_probe.rs")
        assert memory["raw_sha256"] == sha(HERE / memory["raw_record"])
        assert memory["progress_sha256"] == sha(HERE / memory["progress_record"])
        memory_rows.append(memory["peak_rss_bytes"])
    assert memory_rows == [585_973_760, 586_186_752]
    assert abs(memory_rows[0] - memory_rows[1]) / max(memory_rows) < 0.01
    rank_replay = read("a1_n53_rank_replay.json", "a1_n53_rank_replay.py", "A1")
    assert rank_replay["verified_relations"] == 111
    assert rank_replay["weighted_relation_rank"] == 60
    assert rank_replay["full_rank"]
    assert len(rank_replay["solved_seed_logs"]) == 60
    assert rank_replay["sage_seed_log_x_replays"] == [True] * 60
    assert rank_replay["raw_sha256"] == sha(
        HERE / "a1_n53_pair_closure_k600_q128_raw.json")
    recovery = read("a1_n53_target0_recovery.json",
                    "a1_n53_target0_recovery.py", "A1")
    assert recovery["status"] == "verified_recovery"
    assert recovery["recovered_scalar"] == 6_141_872_670_687
    assert recovery["target_lookups"] == 4488
    relation_rows = json.loads((HERE /
        "a1_n53_pair_closure_k600_q128_raw.json").read_text())["rows"]
    assert all(row["target_point"] != recovery["target_point"] and
               row["scalar"] != recovery["recovered_scalar"]
               for row in relation_rows)
    assert recovery["charged_online_ns_exploratory"] == sum(
        recovery["phase_ns_exploratory"].values())
    assert recovery["raw_sha256"] == sha(HERE / recovery["raw_record"])
    assert recovery["progress_sha256"] == sha(HERE / recovery["progress_record"])
    assert recovery["target_source_sha256"] == sha(
        HERE / "a1_n53_closure/src/bin/target_probe.rs")
    assert recovery["log_receipt_sha256"] == sha(
        HERE / "a1_n53_rank_replay.json")
    target_replay = read("a1_n53_target0_sage_verify.json",
                         "a1_n53_target0_sage_verify.py", "A1")
    assert target_replay["scalar_replay_on_public_target"]
    assert target_replay["matching_sign_assignments"] == 1
    assert target_replay["recovered_scalar"] == recovery["recovered_scalar"]
    assert target_replay["target_receipt_sha256"] == sha(
        HERE / "a1_n53_target0_recovery.json")
    fixture_path = (HERE.parent /
        "koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting"
        "/validation/known_answers.jsonl")
    fixture = json.loads(fixture_path.read_text().splitlines()[0])
    assert fixture["target"] == recovery["target_point"]
    assert fixture["fixture_scalar"] == recovery["recovered_scalar"]

    a2 = read("a2_membership_degree.json", "a2_membership_degree.py", "A2")
    a2q = read("a2_quartic_relations.json", "a2_quartic_relations.py", "A2")
    assert a2["membership_indicator"]["membership_count"] == 17_296
    assert a2["membership_indicator"]["algebraic_degree"] == 20
    assert a2q["evaluation_rank_by_degree"] == {
        "0": 1, "1": 24, "2": 277, "3": 2048, "4": 7614}
    assert a2q["quartic_vanishing_space_dimension"] == 3289
    assert a2q["challenge_results"][-1]["uniform_outside_rejected"] == 1024
    assert a2q["challenge_results"][-1]["weight_four_sums_rejected"] == 1024
    exact = read("a2_exact_quartic_membership.json",
                 "a2_exact_quartic_membership.py", "A2")
    artifact = HERE / exact["equations_artifact"]
    assert sha(artifact) == exact["equations_gzip_sha256"]
    equations = json.loads(gzip.decompress(artifact.read_bytes()))
    assert len(equations) == exact["selected_equation_count"]
    assert sum(len(row) for row in equations) == exact["selected_total_anf_terms"]
    assert exact["remaining_false_positives"] == 0 if exact[
        "exact_membership_over_all_field_elements"] else exact["remaining_false_positives"] > 0
    residual = read("a2_partial_false_positives.json",
                    "a2_partial_false_positives.py", "A2")
    assert len(residual["false_positive_x_bits"]) == 53
    assert residual["first_256_false_positives"] == exact["remaining_false_positives"]
    full_path = HERE / "a2_full_quartic_audit.json"
    if full_path.exists():
        full = read(full_path.name, "a2_full_quartic_audit.py", "A2")
        assert full["partial_false_positives"] == 53
        assert full["degree_four_vanishing_space_dimension"] == 3289
        assert full["greedy_added_equations"] == 1
        assert full["final_false_positives"] == 48
        assert {0, 1}.issubset(full["full_space_survivors"])
        assert full["partial_residual_receipt_sha256"] == sha(
            HERE / "a2_partial_false_positives.json")
        assert full["partial_equations_sha256"] == sha(artifact)
        full_artifact = HERE / full["equations_artifact"]
        assert full["equations_gzip_sha256"] == sha(full_artifact)
        final_equations = json.loads(gzip.decompress(full_artifact.read_bytes()))
        assert len(final_equations) == full["final_equation_count"]
        assert final_equations[:256] == equations
        assert sum(len(row) for row in final_equations) == full["final_total_anf_terms"]
        assert full["final_false_positives"] == len(full["full_space_survivors"])
        assert full["exact_membership_over_all_field_elements"] == (
            full["final_false_positives"] == 0)

    n1 = read("n1_parity_classes.json", "n1_parity_classes.py", "N1")
    mixed = read("n1_mixed_sparse_lifts.json", "n1_mixed_sparse_lifts.py", "N1")
    assert sum(row["exact_lift_parity_allowed"] for row in
               n1["exact_s3_parity_table"]) == 3
    assert (mixed["valid_field_s3_identities"], mixed["raw_sparse_exact_lifts"],
            mixed["fixed_a_b_exact_lift_exists"]) == (128, 0, 64)
    assert min(mixed["repaired_c_supports"]) == 15
    print(json.dumps({"status": "PASS", "lead_ids": ["G1", "G2", "G3",
                                                     "G4", "A1", "A2", "N1"]}))


if __name__ == "__main__":
    main()
