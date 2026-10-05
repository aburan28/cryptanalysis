#!/usr/bin/env python3
"""Recompute the W24 orbit-column decision from frozen, verified receipts."""

import argparse
import gzip
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
W24_SOURCE = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005/enumerate.cpp"
W10_MASKS = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005/controls/d10/source-masks.bin"
ALGORITHM_KEYS = (
    "source_signed_columns", "orbit_representatives", "saved_columns",
    "direct_hits", "reciprocal_hits", "forest_edges", "nontrivial_masks",
    "largest_component", "component_size_histogram",
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decompressed_sha256(path):
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_pair(runs, prefix):
    a_dir = runs / (prefix + "-native")
    b_dir = runs / (prefix + "-portable")
    a = json.loads((a_dir / "native.json").read_text())
    b = json.loads((b_dir / "native.json").read_text())
    assert a["field_backend"] == "arm_pmull"
    assert b["field_backend"] == "portable_bitwise"
    for key in ALGORITHM_KEYS:
        assert a[key] == b[key], (prefix, key, a[key], b[key])
    bound = {}
    for name in ("forest.bin", "nontrivial-components.bin"):
        assert (a_dir / name).read_bytes() == (b_dir / name).read_bytes()
        bound[name] = sha256(a_dir / name)
    for d in (a_dir, b_dir):
        assert (d / "orbit").is_file()
        assert (d / "run.stdout").is_file() if prefix == "w24" else True
    return a, b, bound


def check_sage(run_dir, expected_count, expected_saved):
    receipt_path = run_dir / "verification.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "PASS_EXACT_GRAPH_AND_POINT_CONTROLS"
    assert receipt["source_signed_columns"] == expected_count
    assert receipt["saved_columns"] == expected_saved
    assert receipt["forest_edges_checked"] == expected_saved
    assert receipt["native_sha256"] == sha256(run_dir / "native.json")
    assert receipt["forest_sha256"] == sha256(run_dir / "forest.bin")
    assert receipt["component_map_sha256"] == sha256(
        run_dir / "nontrivial-components.bin")
    assert receipt["verifier_source_sha256"] == sha256(HERE / "verify_sage.py")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("analysis output already exists")
    config = json.loads(CONFIG.read_text())
    assert config["candidate_id"] is None
    assert sha256(ROUTE) == config["route_manifest_sha256"]
    compressed = (HERE / config["source_masks_gzip"]).resolve()
    assert sha256(compressed) == config["source_masks_gzip_sha256"]
    assert decompressed_sha256(compressed) == config["source_masks_raw_sha256"]
    assert sha256(W10_MASKS) == config["small_control_source_masks_sha256"]
    route = json.loads(ROUTE.read_text())
    assert route["route_id"] == config["route_id"]
    subgroup_order = int(route["curve_nodes"]["source"]["subgroup_order"])
    runs = HERE / "runs"
    small_native, small_portable, small_artifacts = check_pair(runs, "d10")
    full_native, full_portable, full_artifacts = check_pair(runs, "w24")
    assert small_native["source_signed_columns"] == 492
    assert full_native["source_signed_columns"] == config["source_signed_columns"]
    assert full_native["source_signed_columns"] * 2 == config[
        "source_actual_usable_points_B"]
    small_sage = check_sage(runs / "d10-native", 492,
                            small_native["saved_columns"])
    full_sage = check_sage(runs / "w24-native",
                           full_native["source_signed_columns"],
                           full_native["saved_columns"])
    assert small_sage["point_checks"]["exhaustive_point_orbits"] == 492
    assert small_sage["point_checks"]["exhaustive_point_orbit_classes"] == \
        small_native["orbit_representatives"]
    assert full_sage["point_checks"]["sampled_edges"] == 256
    assert full_native["reciprocal_hits"] == 0
    columns = full_native["source_signed_columns"]
    representatives = full_native["orbit_representatives"]
    saved = full_native["saved_columns"]
    assert columns == representatives + saved
    numerator = config["material_saving_threshold_numerator"]
    denominator = config["material_saving_threshold_denominator"]
    threshold = (columns * numerator + denominator - 1) // denominator
    # Every nonidentity signed class has a full 131-element Frobenius orbit.
    closure_signed_classes = config["endomorphism_order"] * representatives
    closure_B = 2 * closure_signed_classes
    with localcontext() as context:
        context.prec = 40
        saving_percent = str(Decimal(100 * saved) / Decimal(columns))
        expansion = str(Decimal(closure_B) / Decimal(2 * columns))
        m4_mean = str(Decimal(math.comb(closure_B + 3, 4)) /
                      Decimal(subgroup_order - 1))
        m5_mean = str(Decimal(math.comb(closure_B + 4, 5)) /
                      Decimal(subgroup_order - 1))
    source_hashes = {
        "config": sha256(CONFIG),
        "protocol": sha256(HERE / "PROTOCOL.md"),
        "producer": sha256(HERE / "orbit.cpp"),
        "reused_field_core": sha256(W24_SOURCE),
        "verifier": sha256(HERE / "verify_sage.py"),
        "analyzer": sha256(Path(__file__)),
        "route_manifest": sha256(ROUTE),
        "source_masks_gzip": sha256(compressed),
        "source_masks_raw": config["source_masks_raw_sha256"],
        "w10_masks_raw": sha256(W10_MASKS),
        "sage_runtime_info": sha256(HERE / "runtime-info.json"),
    }
    result = {
        "schema": "ecc2k130-w24-orbit-columns-analysis-v1",
        "status": "verified_stage_only",
        "candidate_id": None,
        "curve_id": config["source_curve_id"],
        "transported_curve_id": config["transported_curve_id"],
        "route_id": config["route_id"],
        "actual_source_factor_base_B": config["source_actual_usable_points_B"],
        "sign_only_potential_log_columns": columns,
        "sign_plus_frobenius_potential_log_columns": representatives,
        "saved_potential_log_columns": saved,
        "saving_percent": saving_percent,
        "material_saving_threshold_columns": threshold,
        "material_saving_threshold_met": saved >= threshold,
        "raw_17_byte_log_vector_saved_bytes": 17 * saved,
        "full_orbit_closure_signed_classes": closure_signed_classes,
        "full_orbit_closure_geometric_B": closure_B,
        "full_orbit_closure_expansion_factor": expansion,
        "closure_m4_formal_mean_multisets_per_nonidentity_target": m4_mean,
        "closure_m5_formal_mean_multisets_per_nonidentity_target": m5_mean,
        "closure_natural_PDP_yield": None,
        "closure_membership_cost": None,
        "closure_relation_rank": None,
        "closure_matrix_cost": None,
        "closure_target_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
        "decision": ("advance_quotient_implementation_cost_panel" if saved >= threshold
                     else "deprioritize_folding_original_W24;_test_implicit_orbit_closure_separately"),
        "native_diagnostics": {
            "direct_hits": full_native["direct_hits"],
            "reciprocal_hits": full_native["reciprocal_hits"],
            "forest_edges": full_native["forest_edges"],
            "nontrivial_masks": full_native["nontrivial_masks"],
            "largest_component": full_native["largest_component"],
            "component_size_histogram": full_native["component_size_histogram"],
            "native_elapsed_ns_unisolated": full_native["elapsed_ns"],
            "portable_elapsed_ns_unisolated": full_portable["elapsed_ns"],
            "native_peak_rss_bytes": full_native["peak_rss_bytes"],
            "portable_peak_rss_bytes": full_portable["peak_rss_bytes"],
        },
        "control": {
            "w10_source_columns": small_native["source_signed_columns"],
            "w10_orbit_representatives": small_native["orbit_representatives"],
            "w10_saved_columns": small_native["saved_columns"],
            "w10_exhaustive_point_orbits": small_sage["point_checks"][
                "exhaustive_point_orbits"],
            "full_forest_edges_structurally_checked": full_sage["forest_edges_checked"],
            "full_point_edges_checked": full_sage["point_checks"]["sampled_edges"],
        },
        "backend_artifact_sha256": {"w10": small_artifacts,
                                    "w24": full_artifacts},
        "binary_sha256": {
            "native": sha256(runs / "w24-native/orbit"),
            "portable": sha256(runs / "w24-portable/orbit"),
        },
        "verification_sha256": {
            "w10": sha256(runs / "d10-native/verification.json"),
            "w24": sha256(runs / "w24-native/verification.json"),
        },
        "source_sha256": source_hashes,
        "raw_failures": [],
        "limitations": [
            "No natural PDP, rank, matrix, target, or rho interval was measured.",
            "Full W24 point-law checks cover a frozen 256-edge sample; both complete native backends match exactly.",
            "The orbit closure is a mathematical set, not a materialized factor base or an activated IC candidate.",
            "CPU timings are unisolated diagnostics, not a speedup comparison.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "sign_only_potential_log_columns",
        "sign_plus_frobenius_potential_log_columns",
        "saved_potential_log_columns", "saving_percent",
        "full_orbit_closure_geometric_B", "decision")}, indent=2))


if __name__ == "__main__":
    main()
