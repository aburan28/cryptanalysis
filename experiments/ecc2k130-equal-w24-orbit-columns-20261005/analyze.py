#!/usr/bin/env python3
"""Restrict the verified full W24 Frobenius partition to an equal-size prefix."""

import argparse
import gzip
import hashlib
import json
import struct
import time
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005/runs/w24-b2048-r1"
PARENT = ROOT / "experiments/ecc2k130-263-w24-orbit-columns-20261005"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def scan(path, expected_gzip, expected_raw, expected_count, prefix_count=None):
    assert sha(path) == expected_gzip
    full = hashlib.sha256()
    prefix = hashlib.sha256()
    present = bytearray(1 << 24) if prefix_count is not None else None
    prior = 0
    count = 0
    prefix_last = None
    first_excluded = None
    with gzip.open(path, "rb") as stream:
        while block := stream.read(1 << 20):
            assert len(block) % 4 == 0
            full.update(block)
            take = max(0, min((prefix_count or 0) - count, len(block)//4))
            prefix.update(block[:4*take])
            for (mask,) in struct.iter_unpack("<I", block):
                assert prior < mask < (1 << 24)
                if present is not None:
                    present[mask] = 1
                    if count == prefix_count - 1:
                        prefix_last = mask
                    if count == prefix_count:
                        first_excluded = mask
                prior = mask
                count += 1
    assert count == expected_count and full.hexdigest() == expected_raw
    return present, {"full_count": count, "full_raw_sha256": full.hexdigest(),
                     "prefix_count": prefix_count,
                     "prefix_raw_sha256": prefix.hexdigest() if prefix_count is not None else None,
                     "prefix_last_mask": prefix_last,
                     "first_excluded_mask": first_excluded,
                     "full_last_mask": prior}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    started = time.perf_counter()
    config = json.loads((HERE / "CONFIG.json").read_text())
    assert config["candidate_id"] is None
    assert sha(ROUTE) == config["route_manifest_sha256"]
    route = json.loads(ROUTE.read_text())
    assert route["curve_nodes"]["source"]["curve_id"] == config["source_curve_id"]
    assert route["curve_nodes"]["target"]["curve_id"] == config["descendant_curve_id"]
    assert route["route_id"] == config["route_id"]
    exact = BASE / "verification.json"
    assert sha(exact) == config["exact_base_verification_sha256"]
    assert json.loads(exact.read_text())["status"] == "PASS_EXACT_BASE_AND_GROUP_CONTROLS"
    native_path = PARENT / "runs/w24-native/native.json"
    parent_verification_path = PARENT / "runs/w24-native/verification.json"
    parent_analysis_path = PARENT / "analysis.json"
    map_path = PARENT / "runs/w24-native/nontrivial-components.bin"
    for path, expected in ((native_path, config["parent_orbit_native_sha256"]),
                           (parent_verification_path, config["parent_orbit_verification_sha256"]),
                           (parent_analysis_path, config["parent_orbit_analysis_sha256"]),
                           (map_path, config["parent_component_map_sha256"])):
        assert sha(path) == expected, path
    native = json.loads(native_path.read_text())
    parent_verification = json.loads(parent_verification_path.read_text())
    parent_analysis = json.loads(parent_analysis_path.read_text())
    assert parent_verification["status"] == "PASS_EXACT_GRAPH_AND_POINT_CONTROLS"
    assert parent_analysis["status"] == "verified_stage_only"
    assert native["reciprocal_hits"] == 0
    assert native["source_signed_columns"] == config["source_base_full_signed_classes"]
    assert parent_analysis["saved_potential_log_columns"] == native["saved_columns"]

    membership, source = scan(BASE / "source-masks.bin.gz",
                              config["source_masks_gzip_sha256"],
                              config["source_masks_raw_sha256"],
                              config["source_base_full_signed_classes"],
                              config["source_prefix_signed_classes"])
    assert source["prefix_raw_sha256"] == config["source_prefix_raw_sha256"]
    assert source["prefix_last_mask"] == config["source_prefix_last_mask"]
    assert source["first_excluded_mask"] is not None
    _, descendant = scan(BASE / "descendant-masks.bin.gz",
                         config["descendant_masks_gzip_sha256"],
                         config["descendant_masks_raw_sha256"],
                         config["descendant_native_signed_classes"])
    assert config["source_prefix_signed_classes"] == descendant["full_count"]

    data = map_path.read_bytes()
    assert len(data) % 8 == 0
    labels = list(struct.iter_unpack("<II", data))
    assert len(labels) == native["nontrivial_masks"]
    previous = 0
    all_representatives = set()
    selected_representatives = set()
    selected_nontrivial = 0
    excluded_nontrivial = 0
    cutoff = config["source_prefix_last_mask"]
    for mask, representative in labels:
        assert previous < mask and representative <= mask
        assert membership[mask] and membership[representative]
        all_representatives.add(representative)
        if mask <= cutoff:
            selected_nontrivial += 1
            selected_representatives.add(representative)
        else:
            excluded_nontrivial += 1
        previous = mask
    self_labels = {mask for mask, representative in labels
                   if mask == representative}
    assert all_representatives <= self_labels
    assert (len(labels) - len(all_representatives) == native["saved_columns"])
    assert all(rep <= cutoff for rep in selected_representatives)
    selected = config["source_prefix_signed_classes"]
    saved = selected_nontrivial - len(selected_representatives)
    columns = selected - saved
    with localcontext() as context:
        context.prec = 40
        saving_percent = str(Decimal(100*saved)/Decimal(selected))
    output = {
        "schema": "ecc2k130-equal-w24-orbit-columns-analysis-v1",
        "status": "exact_restriction_pending_independent_direct_replay",
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "source_curve_id": config["source_curve_id"],
        "descendant_curve_id": config["descendant_curve_id"],
        "route_id": config["route_id"],
        "selected_signed_classes_each": selected,
        "actual_usable_points_B_each": 2*selected,
        "source_sign_only_columns": selected,
        "source_sign_plus_frobenius_potential_columns": columns,
        "transported_same_abstract_potential_columns": columns,
        "descendant_native_sign_only_columns": selected,
        "pullback_same_abstract_sign_only_columns": selected,
        "descendant_induced_orbit_potential_columns": None,
        "pullback_source_frobenius_potential_columns": None,
        "source_columns_saved": saved,
        "source_saving_percent": saving_percent,
        "selected_nontrivial_masks": selected_nontrivial,
        "selected_nontrivial_representatives": len(selected_representatives),
        "excluded_nontrivial_masks": excluded_nontrivial,
        "full_nontrivial_masks": len(labels),
        "full_saved_columns": native["saved_columns"],
        "source_stream": source,
        "descendant_stream": descendant,
        "configuration_sha256": sha(HERE / "CONFIG.json"),
        "parent_component_map_sha256": sha(map_path),
        "analyzer_sha256": sha(Path(__file__)),
        "wall_seconds_unisolated_diagnostic": time.perf_counter() - started,
        "native_induced_quotient_cost": None,
        "actual_relation_matrix_columns": None,
        "natural_pdp_yield": None,
        "verified_relation_rank": None,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: output[key] for key in (
        "selected_signed_classes_each", "source_columns_saved",
        "source_sign_plus_frobenius_potential_columns",
        "descendant_native_sign_only_columns", "excluded_nontrivial_masks")}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    main()
