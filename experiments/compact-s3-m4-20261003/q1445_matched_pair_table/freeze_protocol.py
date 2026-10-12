#!/usr/bin/env python3
"""Freeze the Q1445 exact-base pair-table inputs before ordinary queries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_n53_base import HERE, PARENT, REPO, sha
from pair_probe import canonical_json, workload_id


PROTOCOL = HERE / "protocol.json"
SOURCE_PATHS = [
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "build_n53_base.py",
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "pair_probe.py",
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "verify_archive.py",
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "validate_control.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/enumerate_n83_weight5_full.py",
    "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/enumerate_base.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "ecc2k130/codegen/curves.py",
    "ecc2k130/codegen/field.py",
]
INPUT_PATHS = [
    "experiments/compact-s3-m4-20261003/q1438_dense_base/protocol.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/n53_w4_base.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/n83_w6_base.json",
    "experiments/compact-s3-m4-20261003/q1439_fixed_leaf/"
    "runs/n53_control/receipt.json",
    "experiments/compact-s3-m4-20261003/q1444_wdsat_adapter/protocol.json",
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "n53_w4_points.bin",
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "n53_w4_points_receipt.json",
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "validation.json",
]


def produce():
    q1438 = json.loads((PARENT / "q1438_dense_base/protocol.json").read_text())
    q1444 = json.loads((PARENT / "q1444_wdsat_adapter/protocol.json").read_text())
    n53_material = json.loads((HERE / "n53_w4_points_receipt.json").read_text())
    assert n53_material["proposal_id"] == "Q1445"
    assert n53_material["source_sha256"] == sha(HERE / "build_n53_base.py")
    assert n53_material["point_file_sha256"] == sha(HERE / "n53_w4_points.bin")
    assert n53_material["target_independent"] is True
    cells = {}
    for n in (53, 83):
        key = str(n)
        base = json.loads((PARENT / f"q1438_dense_base/n{n}_w"
                           f"{4 if n == 53 else 6}_base.json").read_text())
        instance = q1438["instances"][key]
        anchor = q1444["cells"][f"n{n}_ordinary"]
        assert base["curve_id"] == instance["curve_id"] == anchor["curve_id"]
        assert base["enumerated_set_sha256"] == anchor[
            "factor_base_enumerated_set_sha256"]
        assert base["actual_usable_points_B_before_folding"] == anchor[
            "factor_base_actual_B"]
        assert base["signed_frobenius_columns_K"] == anchor[
            "folded_columns_K"]
        if n == 53:
            assert n53_material["factor_base_actual_B"] == anchor[
                "factor_base_actual_B"]
            assert n53_material["folded_columns_K"] == anchor[
                "folded_columns_K"]
            table_cap, query_cap = 500_000, 1_500_000
            sampling = "uniform index of fully materialized exact Q1438 base"
        else:
            assert base["actual_usable_points_B_before_folding"] == (
                2 * n * base["signed_frobenius_columns_K"])
            assert all(row["duplicate_projected_orbits_at_insertion"] == 0
                       for row in base["strata"])
            table_cap, query_cap = 10_000, 10_000
            sampling = (
                "uniform nonzero normal-basis x support of weight <=6; "
                "reject nonrational or identity projection; random sign; "
                "Q1438 proves full, collision-free projected Frobenius orbits")
        public = anchor["public_target"]
        table_seed = 144500 + n
        query_seed = 144600 + n
        workload = {
            "curve_id": instance["curve_id"],
            "subgroup_order": instance["subgroup_order"],
            "target": public,
            "target_count": 1,
            "target_input_law": "archived fixed ordinary public subgroup point",
            "factor_base_actual_B": base[
                "actual_usable_points_B_before_folding"],
            "factor_base_set_sha256": base["enumerated_set_sha256"],
            "factor_base_sampling": sampling,
            "table_seed": table_seed,
            "query_seed": query_seed,
            "table_sample_cap": table_cap,
            "query_sample_cap": query_cap,
            "online_wall_cap_seconds": 60,
            "cache_state": "target-independent base and pair table ready",
        }
        assert len(canonical_json(workload)) > 0
        cells[key] = {
            "curve_id": instance["curve_id"],
            "weight_bound": instance["new_weight_bound"],
            "cofactor": instance["cofactor"],
            "subgroup_order": instance["subgroup_order"],
            "factor_base_actual_B": base[
                "actual_usable_points_B_before_folding"],
            "folded_columns_K": base["signed_frobenius_columns_K"],
            "factor_base_enumerated_set_sha256": base[
                "enumerated_set_sha256"],
            "factor_base_sampling": sampling,
            "public_target": public,
            "matched_q1444_ordinary_workload_id": anchor["workload_id"],
            "table_seed": table_seed,
            "query_seed": query_seed,
            "table_sample_cap": table_cap,
            "query_sample_cap": query_cap,
            "online_wall_cap_seconds": 60,
            "workload": workload,
            "workload_id": workload_id(workload),
        }
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    return {
        "proposal_id": "Q1445", "candidate_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "method": "signed-Frobenius pair-sum table; exact matched Q1438 bases",
        "claim_scope": "bounded one-target relation-stage diagnostic",
        "run_order": ["n53_ordinary", "n83_ordinary"],
        "cells": cells,
        "source_sha256": {name: sha(REPO / name) for name in SOURCE_PATHS},
        "input_sha256": {name: sha(REPO / name) for name in INPUT_PATHS},
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cpu_isolation_receipt": None,
        "online_single_target_speedup": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = produce()
    if args.check:
        assert json.loads(PROTOCOL.read_text()) == expected
        print("Q1445 frozen protocol: PASS")
    else:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(expected, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1445",
                          "workloads": {n: row["workload_id"]
                                        for n, row in expected["cells"].items()},
                          "protocol_sha256": sha(PROTOCOL)}, sort_keys=True))
