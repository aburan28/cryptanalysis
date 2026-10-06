#!/usr/bin/env python3
"""Frozen secondary n53 ordinary-target relation-yield panel."""

import hashlib
import json
import random
import time
from pathlib import Path

import curves
import field
from dyadic_base_geometry import CONFIG, enumerate_points, select_seeds
from dyadic_n53_relation_probe import build_cross_seed_index, extract_first
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PANEL_SEED = 20260928153
MAX_TARGETS = 4


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main():
    reference_path = HERE / "runs" / "n53_perf_prefix.json"
    geometry_path = HERE / "runs" / "n53_dyadic_base_geometry.json"
    single_path = HERE / "runs" / "n53_dyadic_ordinary_relation.json"
    reference = json.loads(reference_path.read_text())
    geometry = json.loads(geometry_path.read_text())
    single = json.loads(single_path.read_text())
    assert single["ordinary_query"]["status"] == "complete_index_miss"
    cfg = CONFIG[53]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    eigenvalue = int(geometry["frobenius_eigenvalue_mod_r"])
    canonicalize = XOnlyCycle(onb)
    seeds, _, _ = select_seeds(curve, onb, canonicalize, generator,
                               reference["cofactor"], cfg["seed_columns"],
                               cfg["doubling_window"], cfg["seed"])
    labels, representatives, digests = enumerate_points(
        curve, onb, seeds, cfg["doubling_window"], eigenvalue, order)
    assert digests["enumerated_set_sha256"] == geometry["factor_base"][
        "enumerated_set_sha256"]
    setup_started = time.perf_counter()
    index, build = build_cross_seed_index(
        curve, sorted(labels), representatives, labels, canonicalize)
    setup_seconds = time.perf_counter() - setup_started
    assert build["index_sha256"] == single["index_build"]["index_sha256"]
    rng = random.Random(PANEL_SEED)
    scalars = rng.sample(range(1, order), MAX_TARGETS)
    targets = [curve.mul(generator, scalar) for scalar in scalars]
    assert all(point is not None for point in targets)
    assert len(set(targets)) == MAX_TARGETS
    workload = {"curve_id": reference["curve_id"],
                "input_law": "independent uniform nonzero scalar times G; scalar withheld from extraction",
                "target_points": targets,
                "panel_seed": PANEL_SEED, "target_count": MAX_TARGETS,
                "stop_rule": "first verified four-point relation or all four complete index scans",
                "base_geometry_sha256": sha(geometry_path),
                "index_sha256": build["index_sha256"]}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    fixture_path = HERE / "runs" / "n53_dyadic_panel_fixtures.json"
    fixture_path.write_text(json.dumps({"workload": workload,
                                        "validation_scalars": scalars}, indent=2) + "\n")
    output = HERE / "runs" / "n53_dyadic_relation_panel.json"
    report = {"kind": "n53_dyadic_base_secondary_ordinary_relation_panel",
              "scope": "four predeclared public targets after a completed single-target miss; stop at first verified relation; no n83 relation or DLP claim",
              "proposal_id": "Q1016", "candidate_id": None,
              "run_id": f"Q1016W{workload_id}R1", "workload_id": workload_id,
              "workload": workload, "curve_id": reference["curve_id"],
              "isogeny": "none", "factor_base": geometry["factor_base"],
              "index_build": build, "setup_seconds": setup_seconds,
              "target_rows": [], "status": "running",
              "fixture_sha256": sha(fixture_path),
              "geometry_receipt_sha256": sha(geometry_path),
              "single_target_miss_receipt_sha256": sha(single_path),
              "source_sha256": sha(Path(__file__)),
              "dependency_sha256": {name: sha(HERE / name) for name in (
                  "dyadic_base_geometry.py", "dyadic_n53_relation_probe.py",
                  "batch_x_only.py", "x_only_cycle.py", "curves.py", "field.py")},
              "ordinary_relation_yield_observed": None,
              "verified_single_target_dlp": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    for index_no, (target, scalar) in enumerate(zip(targets, scalars)):
        witness, query = extract_first(curve, index, target, canonicalize)
        row = {"target_index": index_no, "target": target,
               "ordinary_query": query,
               "fixture_scalar_validation_only": scalar,
               "relation": None}
        if witness is not None:
            vector = [0] * cfg["seed_columns"]
            for point in witness:
                seed, coefficient = labels[point]
                vector[seed] = (vector[seed] + coefficient) % order
            scalar_replay = None
            for seed_index, coefficient in enumerate(vector):
                if coefficient:
                    scalar_replay = curve.add(
                        scalar_replay, curve.mul(seeds[seed_index], coefficient))
            assert scalar_replay == target
            row["relation"] = {
                "point_witness": witness,
                "seed_coefficient_vector_mod_r": vector,
                "unknown_seed_coefficients_nonzero": any(vector[1:]),
                "known_scalar_rhs_after_generator_seed": (scalar - vector[0]) % order,
                "group_sum_and_seed_scalar_replay_verified": True,
            }
        report["target_rows"].append(row)
        report["ordinary_relation_yield_observed"] = {
            "verified_hits": sum(r["relation"] is not None for r in report[
                "target_rows"]),
            "completed_targets": len(report["target_rows"]),
            "total_pair_complement_probes": sum(r["ordinary_query"][
                "lookups_including_failed"] for r in report["target_rows"]),
        }
        report["status"] = ("first_verified_relation" if witness is not None else
                            "running" if index_no + 1 < MAX_TARGETS else "complete_no_relation")
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"target_index": index_no, "status": query["status"],
                          "lookups": query["lookups_including_failed"],
                          "seconds": query["wall_seconds"]}), flush=True)
        if witness is not None:
            break


if __name__ == "__main__":
    main()
