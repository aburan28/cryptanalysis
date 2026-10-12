#!/usr/bin/env python3
"""Freeze Q1419's matched-source partial-pinning diagnostic protocol."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

from run_cell import CELLS, HERE, PARENT, ROOT, canonical_digest, sha

OUT = HERE / "protocol.json"
SOURCE_PATHS = (
    "ecc2k130/codegen/field.py",
    "ecc2k130/codegen/curves.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/chain_s3_balanced_multitarget.py",
    "experiments/compact-s3-m4-20261003/run_group_add_probe.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
)
PROFILES = {
    53: {
        "parent": "runs/n53_q1410_ordinary.json",
        "fixture": "runs/n53_q1410_witness_locked.json",
        "formula": "runs/n53_q1410_ordinary.xcnf.gz",
        "base_manifest": "bases/n53_weight3_orbits.json.gz",
        "base_archive": "bases/n53_weight3_orbits.json.gz",
        "input_law": "known-satisfiable pinning control on archived ordinary N53 target",
        "source_protocol": "q1410_balanced_s3_n53_protocol.json",
    },
    83: {
        "parent": "runs/n83_q1408_planted_unpinned.json",
        "fixture": "runs/n83_q1408_planted_locked.json",
        "formula": "runs/n83_q1408_planted_unpinned.xcnf.gz",
        "base_manifest": "bases/n83_weight5_full_orbits.json",
        "base_archive": "bases/n83_weight5_full_point_orbits.bin",
        "input_law": "archived known-satisfiable planted N83 pinning control",
        "source_protocol": "q1408_balanced_s3_w5_protocol.json",
    },
}


def artifact(relative):
    path = PARENT / relative
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}


def read_base(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def profile(n, config):
    parent = json.loads((PARENT / config["parent"]).read_text())
    fixture = json.loads((PARENT / config["fixture"]).read_text())
    base = read_base(PARENT / config["base_manifest"])
    prior_protocol = json.loads((PARENT / config["source_protocol"]).read_text())
    fb = base["factor_base"]
    curve = base["curve"]
    assert base["field"]["n"] == n
    assert parent["curve_id"] == fixture["curve_id"] == curve["curve_id"]
    assert parent["factor_base_actual_B"] == fb[
        "actual_usable_points_B_before_folding"]
    assert parent["factor_base_folded_columns"] == fb[
        "signed_frobenius_columns"]
    assert parent["factor_base_enumerated_set_sha256"] == fb[
        "enumerated_set_sha256"]
    assert parent["public_target"] == fixture["public_target"]
    assert fixture["verified_relation"] is not None
    weight = fb["normal_basis_weight_bound"]
    assert (n, weight) in ((53, 3), (83, 5))
    encoded = (PARENT / config["formula"]).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == artifact(config["formula"])[
        "sha256"]
    with gzip.open(PARENT / config["formula"], "rb") as stream:
        raw = stream.read()
    assert hashlib.sha256(raw).hexdigest() == parent["attempts"][0][
        "xcnf_sha256"]
    factor_base = {
        "construction": fb["construction"],
        "normal_basis_weight_bound": weight,
        "nominal_x_mask_count": fb["nominal_x_mask_count"],
        "cofactor_projection": curve["cofactor"],
        "actual_usable_points_B_before_folding": fb[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": fb["signed_frobenius_columns"],
        "enumerated_set_sha256": fb["enumerated_set_sha256"],
        "quotient_rule": fb.get("quotient_rule", fb.get(
            "sign_frobenius_quotient")),
    }
    workload_record = {
        "curve_id": curve["curve_id"],
        "subgroup_order_r": curve["subgroup_order"],
        "target_point": [str(value) for value in parent["public_target"]],
        "input_law": config["input_law"],
        "known_fixture_sha256": sha(PARENT / config["fixture"]),
        "target_generation_seed": prior_protocol.get("planted_seed"),
        "target_count": 1,
        "cold_target_count": 0,
        "warm_target_count": 1,
    }
    return {
        "field_degree_n": n,
        "curve_id": curve["curve_id"],
        "field": base["field"],
        "curve": curve,
        "isogeny": "none",
        "subgroup_order_r": curve["subgroup_order"],
        "cofactor": curve["cofactor"],
        "factor_base": factor_base,
        "factor_base_actual_B": factor_base[
            "actual_usable_points_B_before_folding"],
        "folded_columns_K": factor_base["signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": factor_base[
            "enumerated_set_sha256"],
        "normal_basis_weight_bound": weight,
        "public_target": parent["public_target"],
        "workload_record": workload_record,
        "workload_id": canonical_digest(workload_record)[:12],
        "source_ordinary_workload_id": prior_protocol.get(
            "ordinary_workload_id"),
        "parent_receipt": artifact(config["parent"]),
        "fixture_receipt": artifact(config["fixture"]),
        "formula_archive": artifact(config["formula"]),
        "formula_raw_sha256": parent["attempts"][0]["xcnf_sha256"],
        "factor_base_manifest": artifact(config["base_manifest"]),
        "factor_base_archive": artifact(config["base_archive"]),
        "source_protocol": artifact(config["source_protocol"]),
    }


def build():
    runtime = HERE / "sage_runtime_info.json"
    assert json.loads(runtime.read_text())["status"] == "verified"
    binary = Path(shutil.which("cryptominisat5"))
    return {
        "kind": "q1419_frozen_balanced_s3_m4_partial_pinning_protocol",
        "proposal_id": "Q1419", "candidate_id": None,
        "isogeny": "none",
        "question": (
            "Which balanced S3 input family causes unpinned known-"
            "satisfiable N53/N83 four-point search to stall?"),
        "cells": {name: {
            "pinned_leaf_indices": list(leaves),
            "pin_pair_intermediates": mids,
            "pin_target_preimage_selector": selector,
        } for name, (leaves, mids, selector) in CELLS.items()},
        "run_order": list(CELLS),
        "profiles": {str(n): profile(n, config)
                     for n, config in PROFILES.items()},
        "solver_wall_cap_seconds": 60,
        "solver_conflict_cap": 1000000,
        "solver_binary_sha256": sha(binary),
        "solver_flags": ["--verb", "1", "--threads", "1", "--maxconfl",
                         "1000000"],
        "encoding_source_sha256": {
            "chain_s3": sha(PARENT / "chain_s3.py"),
            "chain_s3_factored": sha(PARENT / "chain_s3_factored.py"),
            "chain_s3_multitarget": sha(PARENT / "chain_s3_multitarget.py"),
            "chain_s3_balanced_multitarget": sha(
                PARENT / "chain_s3_balanced_multitarget.py"),
        },
        "dependency_sha256": {
            source: sha(ROOT / source) for source in SOURCE_PATHS},
        "runtime_info_sha256": sha(runtime),
        "runner_source_sha256": sha(HERE / "run_cell.py"),
        "verifier_source_sha256": sha(HERE / "verify_archive.py"),
        "freeze_source_sha256": sha(Path(__file__)),
        "claim_boundary": (
            "Validation-only partial pinning on archived known-satisfiable "
            "targets. Solver clocks are exploratory on an unisolated host. "
            "No natural relation yield, N131 growth fit, full IC candidate, "
            "DLP recovery, or speedup follows from these cells."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == content
    else:
        assert not OUT.exists()
        OUT.write_text(content)
    print(OUT)


if __name__ == "__main__":
    main()
