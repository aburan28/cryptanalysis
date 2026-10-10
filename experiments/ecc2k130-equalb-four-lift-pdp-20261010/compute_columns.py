#!/usr/bin/env python3
"""Restrict the independently checked W24 orbit map to the new equal-B prefix."""

from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import json
from pathlib import Path
import struct

import build_four_lift as gate


ORBIT_REL = Path("experiments/ecc2k130-263-w24-orbit-columns-20261005")
PREFIX = gate.ref.EQUAL / "runs/R1/base_prefixes.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=gate.ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite column census")
    parent = args.evidence_root / ORBIT_REL
    map_path = parent / "runs/w24-native/nontrivial-components.bin"
    native_path = parent / "runs/w24-native/native.json"
    verification_path = parent / "runs/w24-native/verification.json"
    direct_path = parent / "independent_direct.json"
    analysis_path = parent / "analysis.json"
    prefix = json.loads(PREFIX.read_text())
    native = json.loads(native_path.read_text())
    verification = json.loads(verification_path.read_text())
    direct = json.loads(direct_path.read_text())
    analysis = json.loads(analysis_path.read_text())
    raw = map_path.read_bytes()
    map_hash = gate.ref.sha(map_path)
    if (prefix["source"]["actual_usable_points_B"] != 11743888
            or prefix["source"]["selected_signed_classes"] != 5871944
            or prefix["preflight"]["q1421_K"] != 44824
            or prefix["preflight"]["q1421_B"] != 11743888
            or verification["status"] != "PASS_EXACT_GRAPH_AND_POINT_CONTROLS"
            or direct["status"]
            != "PASS_INDEPENDENT_DIRECT_AND_PARTITION_GIVEN_RECIPROCAL_ZERO"
            or analysis["status"] != "verified_stage_only"
            or native["reciprocal_hits"] != 0
            or native["nontrivial_masks"] != len(raw)//8
            or native["saved_columns"] != verification["saved_columns"]
            or analysis["saved_potential_log_columns"] != native["saved_columns"]
            or map_hash != verification["component_map_sha256"]
            or map_hash != direct["native_component_map_sha256"]):
        raise ValueError("parent map, base prefix, or independent checks changed")
    cutoff = prefix["source"]["last_selected_mask"]
    selected = []
    prior = 0
    for mask, representative in struct.iter_unpack("<II", raw):
        if not prior < mask or representative > mask:
            raise ValueError("noncanonical orbit component map")
        if mask <= cutoff:
            selected.append((mask, representative))
        prior = mask
    reps = {representative for _, representative in selected}
    if any(rep > cutoff for rep in reps):
        raise ValueError("selected orbit component has excluded representative")
    saved = len(selected) - len(reps)
    source_columns = prefix["source"]["selected_signed_classes"] - saved
    normal_columns = prefix["preflight"]["q1421_K"]
    with localcontext() as context:
        context.prec = 40
        ratio = str(Decimal(source_columns)/Decimal(normal_columns))
    result = {
        "schema": "ecc2k130-equalb-m6-orbit-columns-v1",
        "status": "PASS_EXACT_PREFIX_RESTRICTION_OF_VERIFIED_ORBIT_MAP",
        "candidate_id": None,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "actual_usable_points_B_each": 11743888,
        "source_w24_signed_classes": prefix["source"]["selected_signed_classes"],
        "source_w24_last_selected_mask": cutoff,
        "source_w24_nontrivial_masks_in_prefix": len(selected),
        "source_w24_nontrivial_representatives_in_prefix": len(reps),
        "source_w24_saved_potential_columns": saved,
        "source_w24_potential_columns": source_columns,
        "source_normal4_potential_columns": normal_columns,
        "w24_over_normal4_potential_column_ratio": ratio,
        "source_prefix_selected_stream_sha256": prefix["source"][
            "selected_raw_sha256"],
        "source_prefix_receipt_sha256": gate.ref.sha(PREFIX),
        "parent_component_map_sha256": map_hash,
        "parent_native_receipt_sha256": gate.ref.sha(native_path),
        "parent_verification_sha256": gate.ref.sha(verification_path),
        "parent_independent_direct_sha256": gate.ref.sha(direct_path),
        "parent_analysis_sha256": gate.ref.sha(analysis_path),
        "source_sha256": gate.ref.sha(Path(__file__)),
        "actual_relation_matrix_columns": None,
        "relation_rank": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "source_w24_potential_columns",
                       "source_normal4_potential_columns",
                       "w24_over_normal4_potential_column_ratio")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
