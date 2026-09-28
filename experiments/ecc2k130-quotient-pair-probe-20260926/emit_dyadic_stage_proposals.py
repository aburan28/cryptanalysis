#!/usr/bin/env python3
"""Emit exact Q-stage identities without issuing premature IC1 candidate IDs."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    geometry = {
        "Q1013": read("runs/n83_dyadic_base_geometry.json"),
        "Q1014": read("runs/n53_dyadic_base_geometry.json"),
        "Q1017": read("runs/n53_dyadic_two_seed_geometry.json"),
        "Q1018": read("runs/n83_dyadic_two_seed_geometry.json"),
        "Q1020": read("runs/n83_dyadic_target_seed_geometry.json"),
    }
    ordinary = read("runs/n53_dyadic_ordinary_relation.json")
    panel = read("runs/n53_dyadic_relation_panel.json")
    target = read("runs/n53_dyadic_target_seed_dlp.json")
    wide_target = read("runs/n53_dyadic_target_seed_dlp_w64.json")
    n83_perf = read("runs/n83_dyadic_target_perf_L32.json")
    n83_compact = read("runs/n83_dyadic_compact_packed.json")
    five_n53 = read("runs/n53_dyadic_five_sum_dlp.json")
    five_n83 = read("runs/n83_dyadic_five_sum_stage.json")
    five_support_n83 = read("runs/n83_dyadic_G_pair_scalar_support_L1000.json")
    assert ordinary["curve_id"] == panel["curve_id"] == geometry["Q1014"]["curve_id"]
    assert ordinary["factor_base"] == panel["factor_base"] == geometry[
        "Q1014"]["factor_base"]
    assert target["curve_id"] == geometry["Q1017"]["curve_id"]
    assert target["factor_base"]["actual_usable_points_B_before_folding"] == 3392
    assert wide_target["curve_id"] == target["curve_id"]
    assert wide_target["factor_base"]["actual_usable_points_B_before_folding"] == 13568
    assert n83_perf["curve_id"] == geometry["Q1020"]["curve_id"]
    assert n83_perf["factor_base"]["actual_usable_points_B_before_folding"] == 10624
    assert n83_compact["curve_id"] == n83_perf["curve_id"]
    assert n83_compact["factor_base"]["actual_usable_points_B_before_folding"] == 10624
    assert five_n53["curve_id"] == wide_target["curve_id"]
    assert five_n53["factor_base"]["enumerated_set_sha256"] == wide_target[
        "factor_base"]["enumerated_set_sha256"]
    assert five_n83["curve_id"] == n83_perf["curve_id"]
    assert five_n83["factor_base"]["enumerated_set_sha256"] == n83_perf[
        "factor_base"]["enumerated_set_sha256"]
    assert five_support_n83["curve_id"] == geometry["Q1020"]["curve_id"]
    assert five_support_n83["factor_base"]["enumerated_set_sha256"] == geometry[
        "Q1020"]["factor_base"]["enumerated_set_sha256"]
    assert all(row["candidate_id"] is None and row["isogeny"] == "none"
               for row in (*geometry.values(), ordinary, panel, target, wide_target,
                           n83_perf, n83_compact, five_n53, five_n83,
                           five_support_n83))
    source = {
        "Q1013": (geometry["Q1013"], "enumerated 100-seed n83 geometry; 99 unknown seed logs", ["runs/n83_dyadic_base_geometry.json", "dyadic_n83_work_projection.json"]),
        "Q1014": (geometry["Q1014"], "enumerated 8-seed n53 geometry; 7 unknown seed logs", ["runs/n53_dyadic_base_geometry.json"]),
        "Q1015": (ordinary, "one frozen n53 ordinary-target complete quotient search", ["runs/n53_dyadic_ordinary_relation.json"]),
        "Q1016": (panel, "secondary frozen n53 ordinary-target relation-yield panel", ["runs/n53_dyadic_relation_panel.json"]),
        "Q1017": (geometry["Q1017"], "enumerated two-seed n53 geometry; one unknown seed log", ["runs/n53_dyadic_two_seed_geometry.json"]),
        "Q1018": (geometry["Q1018"], "enumerated two-seed n83 geometry; one unknown seed log", ["runs/n83_dyadic_two_seed_geometry.json"]),
        "Q1019": (target, "target-dependent two-seed n53 quotient DLP pilot", ["runs/n53_dyadic_target_seed_dlp.json"]),
        "Q1020": (geometry["Q1020"], "target-dependent two-seed n83 geometry and conditional query model", ["runs/n83_dyadic_target_seed_geometry.json", "dyadic_two_seed_n83_projection.json"]),
        "Q1021": (wide_target, "target-dependent two-seed n53 quotient DLP pilot with 64-step window", ["runs/n53_dyadic_target_seed_dlp_w64.json"]),
        "Q1022": (n83_perf, "exact target-dependent n83 L32 quotient index and bounded ordinary-query performance", ["runs/n83_dyadic_target_perf_L32.json"]),
        "Q1023": (n83_compact, "packed n83 L32 quotient index with exact-key and witness controls", ["runs/n83_dyadic_compact_packed.json", "runs/n83_dyadic_compact_compare.json"]),
        "Q1024": (five_n53, "verified single-target n53 five-sum two-plus-three quotient DLP pilot", ["runs/n53_dyadic_five_sum_dlp.json"]),
        "Q1025": (five_n83, "n83 L32 two-G quotient index and bounded batched three-Q stage", ["runs/n83_dyadic_five_sum_stage.json", "dyadic_five_sum_n83_projection.json"]),
        "Q1026": (five_support_n83, "exact n83 L1000 G-pair scalar quotient support, no point-witness index", ["runs/n83_dyadic_G_pair_scalar_support_L1000.json", "dyadic_five_sum_n83_projection.json"]),
    }
    out = []
    for proposal_id, (receipt, description, refs) in source.items():
        base = receipt["factor_base"]
        identity = receipt.get("curve_identity_record")
        if identity is None:
            identity = geometry["Q1014" if receipt["curve_id"] == geometry[
                "Q1014"]["curve_id"] else "Q1013"]["curve_identity_record"]
        assert receipt["curve_id"] in (geometry["Q1014"]["curve_id"],
                                        geometry["Q1013"]["curve_id"])
        assert identity["field"]["n"] == (53 if receipt["curve_id"] == geometry[
            "Q1014"]["curve_id"] else 83)
        row = {
            "proposal_id": proposal_id, "candidate_id": None,
            "description": description,
            "field": identity["field"],
            "curve_id": receipt["curve_id"], "curve": identity["curve"],
            "isogeny": "none", "endomorphism_order_conductor": None,
            "factor_base": {
                "construction": base.get("construction", receipt.get("seed_selection") or
                                         "signed-Frobenius closure of dyadic windows from G and public Q"),
                "nominal_seed_columns": base.get("nominal_seed_columns", 2),
                "doubling_window": base.get("doubling_window", receipt[
                    "workload"].get("doubling_window")),
                "actual_usable_points_B_before_folding": base[
                    "actual_usable_points_B_before_folding"],
                "signed_frobenius_columns": base["signed_frobenius_columns"],
                "effective_unknown_log_columns_after_dyadic_labels": base[
                    "effective_unknown_log_columns_after_dyadic_labels"],
                "enumerated_set_sha256": base["enumerated_set_sha256"],
                "point_coefficient_label_sha256": base[
                    "point_coefficient_label_sha256"],
            },
            "point_decomposition": {
                "m": 5 if proposal_id in ("Q1024", "Q1025", "Q1026") else 4,
                "method": "complete two-G quotient pair index with sampled three-Q complements"
                          if proposal_id in ("Q1024", "Q1025") else
                          "exact known-scalar G-pair orbit support only"
                          if proposal_id == "Q1026" else
                          "complete cross-seed quotient pair-sum index",
                "quotient": "signed Frobenius, x-only cyclic canonicalization",
                "complement": "batched inversion across one orbit",
                "status": "implemented n53" if proposal_id in ("Q1015", "Q1016", "Q1019", "Q1021", "Q1024") else
                          "implemented n83 bounded stage" if proposal_id in ("Q1022", "Q1023", "Q1025") else
                          "exact n83 L1000 scalar support only" if proposal_id == "Q1026" else
                          "conditional n83 scaling or geometry only",
            },
            "relation_collection": (
                "known-scalar uniform G multiples against public target-seeded base"
                if proposal_id in ("Q1019", "Q1021", "Q1024", "Q1025") else
                "frozen ordinary target stream" if proposal_id == "Q1016" else None),
            "relation_linear_algebra": (
                "one-row modular inverse if a nonzero target coefficient is found"
                if proposal_id in ("Q1019", "Q1021", "Q1024", "Q1025") else None),
            "target_descent": (
                "direct scalar recovery from target-seed coefficient"
                if proposal_id in ("Q1019", "Q1021", "Q1024", "Q1025") else None),
            "stage_receipts": refs,
            "measured_complete_work_log2": None,
            "rho_paired_online_speedup": None,
        }
        out.append(row)
    path = HERE / "dyadic_stage_proposals.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"proposal_ids": [row["proposal_id"] for row in out],
                      "curves": sorted(set(row["curve_id"] for row in out))}))


if __name__ == "__main__":
    main()
