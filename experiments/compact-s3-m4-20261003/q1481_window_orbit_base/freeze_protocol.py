#!/usr/bin/env python3
"""Freeze exact Q1481 base source, references, and accepted Sage runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make() -> dict:
    design_path = HERE / "design_protocol.json"
    design = json.loads(design_path.read_text())
    assert design["proposal_id"] == "Q1481"
    assert design["candidate_id"] is None
    assert design["construction"]["isogeny"] == "none"
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    parent_path = PARENT / "q1438_dense_base/protocol.json"
    parent = json.loads(parent_path.read_text())
    instances = {}
    for n in (53, 83):
        d = design["instances"][str(n)]["nominal_window_dimension_d"]
        reference = parent["instances"][str(n)]
        assert reference["curve_id"] == design["instances"][str(n)][
            "curve_id"]
        assert reference["reference_actual_B"] != design["instances"][
            str(n)]["reference_actual_B"]
        instances[str(n)] = {
            "curve_id": reference["curve_id"],
            "field": reference["field"],
            "curve": reference["curve"],
            "subgroup_order": reference["subgroup_order"],
            "cofactor": reference["cofactor"],
            "nominal_window_dimension_d": d,
            "raw_x_orbits_formula": 1 << (d - 1),
            "reference_actual_B": design["instances"][str(n)][
                "reference_actual_B"],
            "reference_folded_K": design["instances"][str(n)][
                "reference_folded_K"],
        }
        ref_weight = reference["new_weight_bound"]
        ref_base = json.loads((PARENT / "q1438_dense_base" /
                               f"n{n}_w{ref_weight}_base.json").read_text())
        assert ref_base["actual_usable_points_B_before_folding"] == (
            instances[str(n)]["reference_actual_B"])
        assert ref_base["signed_frobenius_columns_K"] == (
            instances[str(n)]["reference_folded_K"])
    dependency_files = (
        "ecc2k130/codegen/field.py",
        "ecc2k130/codegen/curves.py",
        "experiments/koblitz-pair-claw-20260929/orbit_key.py",
        "experiments/compact-s3-m4-20261003/enumerate_n83_weight5_full.py",
        "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
        "experiments/compact-s3-m4-20261003/run_probe.py",
    )
    reference_files = (
        "experiments/compact-s3-m4-20261003/q1438_dense_base/protocol.json",
        "experiments/compact-s3-m4-20261003/q1438_dense_base/n53_w4_base.json",
        "experiments/compact-s3-m4-20261003/q1438_dense_base/n83_w6_base.json",
        "experiments/compact-s3-m4-20261003/protocol.json",
    )
    source_files = ("enumerate_base.py", "verify_base.py",
                    "validate_window.py", "freeze_protocol.py")
    return {
        "kind": "q1481_frozen_exact_window_orbit_base_protocol",
        "proposal_id": "Q1481", "candidate_id": None,
        "isogeny": "none",
        "design_sha256": sha(design_path),
        "design_instances": design["instances"],
        "instances": instances,
        "run_order": ["n53_d14", "n83_d23"],
        "source_sha256": {name: sha(HERE / name) for name in source_files},
        "dependency_sha256": {name: sha(ROOT / name)
                              for name in dependency_files},
        "reference_sha256": {name: sha(ROOT / name)
                             for name in reference_files},
        "runtime_info_sha256": sha(runtime_path),
        "claim_scope": (
            "Exact projected N53/N83 base geometry and sampled independent "
            "group controls. No PDP result, natural relation yield, N131 "
            "actual B or K, complete 2^x, or IC1 candidate."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = make()
    if args.check or PROTOCOL.exists():
        assert json.loads(PROTOCOL.read_text()) == data
        print("Q1481 base protocol verified")
    else:
        PROTOCOL.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("Q1481 base protocol frozen")


if __name__ == "__main__":
    main()
