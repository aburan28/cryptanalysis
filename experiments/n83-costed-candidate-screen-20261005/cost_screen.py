#!/usr/bin/env python3
"""Turn pinned N83 geometry into a deliberately incomplete cost ledger."""

from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from math import comb
from pathlib import Path


HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "hamming-ic-e2e-20260929"
BASELINE = PRIOR / "runs/n83_full_w4_geometry_v1/geometry.json"
PROTOCOL = HERE / "protocol.json"
ARITY_PROTOCOL = HERE / "protocol_arity_sweep.json"
ONLINE = ("target_query", "target_pdp", "target_relation_check",
          "target_descent", "target_recovery_check")
COLD = ("setup", "isogeny", "factor_base", "precompute", "queries",
        "pdp", "relation_check", "matrix_build", "relation_la",
        "target_descent", "recovery_check")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratio(a: int, b: int) -> str:
    with localcontext() as context:
        context.prec = 50
        return format(Decimal(a) / Decimal(b), ".40g")


def new_row(label: str, geometry: Path, protocol: dict) -> dict:
    data = json.loads(geometry.read_text())
    if data["status"] != "EXACT_GEOMETRY_PASS":
        raise ValueError(f"{label}: incomplete geometry")
    if data["curve_id"] != protocol["curve_id"]:
        raise ValueError(f"{label}: wrong curve")
    if label != "full_w4_m5":
        protocol_path = ARITY_PROTOCOL if label in {
            option["label"] for option in json.loads(ARITY_PROTOCOL.read_text())["options"]
        } else PROTOCOL
        if data["protocol_sha256"] != sha(protocol_path):
            raise ValueError(f"{label}: protocol digest mismatch")
    r = int(protocol["subgroup_order_decimal"])
    if label == "full_w4_m5":
        checkpoint = data["checkpoints"][-1]
        b = checkpoint["actual_usable_projected_points_B"]
        k = checkpoint["effective_signed_frobenius_columns"]
        m = 5
        tuples = comb(b + m - 1, m)
        model = "unordered_multisets_with_repetition_same_base"
        assert ratio(tuples, r)[:18] == checkpoint["multisets_per_subgroup_element"]["5"][:18]
        pair_states = None
        pair_payload = None
        index_bytes = None
        existing_index_work = checkpoint["root_index_pair_state_loops_NK2"]
        nominal_boolean_coordinates = m * 83
    else:
        b = data["actual_usable_projected_points_B_per_slot"]
        k = data["effective_signed_frobenius_columns_K"]
        m = data["arity"]
        tuples = b**m
        model = "ordered_labeled_frobenius_shifted_slots"
        assert ratio(tuples, r) == data["ordered_tuples_per_subgroup_element"]
        # This is a specified explicit-record design, not a universal memory
        # lower bound. Different-slot pair sums have B^2 logical candidates.
        pair_states = b * b
        index_bytes = ((b - 1).bit_length() + 7) // 8
        pair_payload = pair_states * (12 + 2 * index_bytes)
        existing_index_work = None
        nominal_boolean_coordinates = m * data["dimension"]
    within_limit = (label == "full_w4_m5" or
                    data.get("whole_process_from_main_wall_ms_exploratory", 0)
                    <= protocol["resource_limit_seconds_per_base"] * 1000)
    return {
        "label": label, "candidate_id": None, "curve_id": protocol["curve_id"],
        "stage_status": ("EXACT_GEOMETRY_ONLY" if within_limit else
                         "EXACT_GEOMETRY_OVER_FROZEN_WALL_LIMIT"),
        "within_frozen_base_wall_limit": within_limit,
        "geometry_ref": str(geometry.relative_to(HERE.parent)),
        "geometry_sha256": sha(geometry), "summands": m,
        "nominal_boolean_coordinates_before_equations": nominal_boolean_coordinates,
        "actual_usable_factor_base_points_B": b,
        "effective_signed_frobenius_columns_K": k,
        "tuple_count_model": model, "tuple_count_exact": str(tuples),
        "tuples_per_subgroup_element": ratio(tuples, r),
        "support_ceiling_fraction": ratio(min(tuples, r), r),
        "ordinary_query_coverage": None, "ordinary_query_pdp_completion": None,
        "verified_relations_per_query": None, "novel_rank_per_query": None,
        "required_rank": None, "factor_log_precomputation_wall_ns": None,
        "matrix_build_wall_ns": None, "relation_la_wall_ns": None,
        "target_descent_wall_ns": None, "target_recovery_verified": None,
        "same_point_rho_verified": None, "same_point_rho_online_wall_ns": None,
        "online_phase_wall_ns": {name: None for name in ONLINE},
        "online_wall_ns": None,
        "cold_phase_wall_ns": {name: None for name in COLD},
        "cold_wall_ns": None, "operation_count": None,
        "online_speedup": None,
        "explicit_distinct_slot_pair_candidates": pair_states,
        "explicit_pair_record_index_bytes_each": index_bytes,
        "explicit_pair_record_raw_payload_bytes_no_container": pair_payload,
        "explicit_pair_record_model": (
            "One compressed 83-bit group point (12 bytes) and two fixed-width "
            "factor-base indices per distinct-slot pair, retaining all B^2 "
            "candidates. This is a conditional design size; no compression, "
            "deduplication, allocator, hash-table, I/O or work time is priced."
            if pair_states is not None else None),
        "existing_root_index_pair_state_loops_NK2": existing_index_work,
    }


def main(out: Path) -> None:
    protocols = [(path, json.loads(path.read_text()))
                 for path in (PROTOCOL, ARITY_PROTOCOL)]
    first = protocols[0][1]
    for _, protocol in protocols:
        assert sha(BASELINE) == protocol["baseline_full_w4_geometry_sha256"]
        assert protocol["curve_id"] == first["curve_id"]
        assert protocol["subgroup_order_decimal"] == first["subgroup_order_decimal"]
    entries = [("full_w4_m5", BASELINE, first)]
    for _, protocol in protocols:
        for option in protocol["options"]:
            label = option["label"]
            path = HERE / "runs" / f"{label}_v1" / "geometry.json"
            if path.is_file():
                entries.append((label, path, protocol))
    record = {
        "schema_version": 1, "kind": "n83_costed_geometry_screen",
        "protocol_sha256": {path.name: sha(path) for path, _ in protocols},
        "source_sha256": sha(Path(__file__)),
        "curve_id": first["curve_id"],
        "subgroup_order": first["subgroup_order_decimal"],
        "accounting_boundary": "One unseen target after reusable precomputation; "
        "five exclusive target-online phases; same public point and envelope for rho.",
        "measurement_environment": "ordinary_contended_macos_exploratory",
        "rows": [new_row(label, path, protocol)
                 for label, path, protocol in entries],
        "claim_boundary": "Geometry and exact/conditional size arithmetic only. "
        "No measured ordinary-query yield, complete IC, rho pair, cost total, or speedup.",
    }
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"rows": len(record["rows"]), "source_sha256": record["source_sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
