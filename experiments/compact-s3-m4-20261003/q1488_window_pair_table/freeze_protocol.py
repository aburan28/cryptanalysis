#!/usr/bin/env python3
"""Freeze Q1488's exact matched Q1481 pair-table stage before ordinary runs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

from build_n53_base import HERE, PARENT, Q1481, ROOT, sha

sys.path.insert(0, str(PARENT / "q1445_matched_pair_table"))
from pair_probe import workload_id  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OWN_SOURCES = (
    "design_protocol.json", "build_n53_base.py", "sample_window.py",
    "validate_control.py", "freeze_protocol.py", "run_stage.py", "audit.py",
)
EXTERNAL_SOURCES = (
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "pair_probe.py",
    "experiments/compact-s3-m4-20261003/q1445_matched_pair_table/"
    "build_n53_base.py",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/"
    "enumerate_base.py",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/"
    "verify_base.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/compact-s3-m4-20261003/"
    "enumerate_q1413_projected_x.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "ecc2k130/codegen/curves.py", "ecc2k130/codegen/field.py",
)
EXTERNAL_INPUTS = (
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/"
    "protocol.json",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/"
    "n53_d14_base.json",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/"
    "n83_d23_base.json",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/"
    "n53_d14_projected_keys.bin",
    "experiments/compact-s3-m4-20261003/q1481_window_orbit_base/"
    "n83_d23_projected_keys.bin",
    "experiments/compact-s3-m4-20261003/q1482_window_s3/"
    "protocol.json",
    "experiments/compact-s3-m4-20261003/q1487_inverse_partner/"
    "protocol.json",
    "experiments/compact-s3-m4-20261003/q1488_window_pair_table/"
    "n53_window_points.bin",
    "experiments/compact-s3-m4-20261003/q1488_window_pair_table/"
    "n53_window_points_receipt.json",
    "experiments/compact-s3-m4-20261003/q1488_window_pair_table/"
    "validation.json",
)


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    parent = json.loads((PARENT / "q1482_window_s3/protocol.json").read_text())
    comparator = json.loads((PARENT /
        "q1487_inverse_partner/protocol.json").read_text())
    q1481 = json.loads((Q1481 / "protocol.json").read_text())
    material = json.loads((HERE /
        "n53_window_points_receipt.json").read_text())
    validation = json.loads((HERE / "validation.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert design["proposal_id"] == material["proposal_id"] == (
        validation["proposal_id"]) == "Q1488"
    assert runtime["status"] == "verified"
    assert validation["status"] == "passed"
    assert material["source_sha256"] == sha(HERE / "build_n53_base.py")
    assert material["point_file_sha256"] == sha(
        HERE / "n53_window_points.bin")
    assert material["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert validation["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert validation["source_sha256"] == sha(
        HERE / "validate_control.py")
    assert design["run_order"] == ["n53_ordinary", "n83_ordinary"]
    assert q1481["proposal_id"] == "Q1481"
    assert parent["proposal_id"] == "Q1482"
    assert comparator["proposal_id"] == "Q1487"

    prefix = "experiments/compact-s3-m4-20261003/q1488_window_pair_table/"
    source = {prefix + name: sha(HERE / name) for name in OWN_SOURCES}
    source.update({name: sha(ROOT / name) for name in EXTERNAL_SOURCES})
    inputs = {name: sha(ROOT / name) for name in EXTERNAL_INPUTS}
    stages = {}
    cases = {}
    for n in (53, 83):
        case = f"n{n}_ordinary"
        instance = design["instances"][str(n)]
        inherited = parent["cases"][case]
        matched = comparator["cases"][case]
        base = json.loads((Q1481 /
            f"n{n}_d{instance['nominal_window_dimension_d']}_base.json"
                           ).read_text())
        assert inherited["curve_id"] == matched["curve_id"] == (
            instance["curve_id"]) == base["curve_id"]
        assert inherited["public_target"] == matched["public_target"]
        assert inherited["factor_base_actual_B"] == (
            instance["actual_usable_B"]) == base[
                "actual_usable_points_B_before_folding"]
        assert inherited["folded_columns_K"] == instance[
            "folded_K"] == base["signed_frobenius_columns_K"]
        assert inherited["factor_base_enumerated_set_sha256"] == (
            instance["enumerated_set_sha256"]) == base[
                "enumerated_set_sha256"]
        assert matched["workload_id"] == inherited["workload_id"]
        record = copy.deepcopy(parent["stages"][str(n)][
            "stage_config_hash_input"])
        record["point_decomposition"] = {
            "m": 4, "stage_code": "PDP4mitm",
            "solver_family": "signed-Frobenius quotient pair table",
            "pair_table_source_sha256": sha(PARENT /
                "q1445_matched_pair_table/pair_probe.py"),
            "window_sampler_source_sha256": sha(HERE / "sample_window.py"),
            "base_materialization_source_sha256": sha(
                HERE / "build_n53_base.py"),
            "point_pair_law": design["point_decomposition"]["sample_law"],
            "relation_policy": (
                "four distinct signed-Frobenius columns; public target "
                "group sum and subgroup membership replay"),
            "cache_policy": "target-independent pair table ready",
        }
        digest = hashlib.sha256(canonical(record)).hexdigest()
        stage_id = (f"PS1N{n}Ckb1fb{instance['actual_usable_B']}"
                    f"PDP4mitmh{digest[:12]}")
        stages[str(n)] = {
            "stage_config_hash_input": record,
            "stage_config_sha256_full": digest,
            "stage_config_id": stage_id,
        }
        workload = {
            "curve_id": instance["curve_id"],
            "subgroup_order": q1481["instances"][str(n)][
                "subgroup_order"],
            "target": inherited["public_target"],
            "target_count": 1,
            "target_input_law": "archived Q1482 ordinary public subgroup point",
            "factor_base_actual_B": instance["actual_usable_B"],
            "factor_base_set_sha256": instance["enumerated_set_sha256"],
            "factor_base_sampling": instance["base_sampling"],
            "table_seed": instance["table_seed"],
            "query_seed": instance["query_seed"],
            "table_pair_sample_cap": instance["table_pair_sample_cap"],
            "query_pair_sample_cap": instance["query_pair_sample_cap"],
            "online_query_wall_cap_seconds": design[
                "point_decomposition"]["online_query_wall_cap_seconds"],
            "cache_state": "target-independent point base and pair table ready",
        }
        wid = workload_id(workload)
        cases[case] = {
            "case": case, "degree_n": n,
            "curve_id": instance["curve_id"],
            "cofactor": q1481["instances"][str(n)]["cofactor"],
            "subgroup_order": q1481["instances"][str(n)][
                "subgroup_order"],
            "nominal_window_dimension_d": instance[
                "nominal_window_dimension_d"],
            "factor_base_actual_B": instance["actual_usable_B"],
            "folded_columns_K": instance["folded_K"],
            "factor_base_enumerated_set_sha256": instance[
                "enumerated_set_sha256"],
            "factor_base_sampling": instance["base_sampling"],
            "public_target": inherited["public_target"],
            "matched_q1487_workload_id": matched["workload_id"],
            "matched_q1487_stage_config_id": comparator[
                "stages"][str(n)]["stage_config_id"],
            "table_seed": instance["table_seed"],
            "query_seed": instance["query_seed"],
            "table_pair_sample_cap": instance["table_pair_sample_cap"],
            "query_pair_sample_cap": instance["query_pair_sample_cap"],
            "online_query_wall_cap_seconds": workload[
                "online_query_wall_cap_seconds"],
            "workload": workload, "workload_id": wid,
            "stage_config_id": stage_id,
            "stage_run_id": f"{stage_id}W{wid}R1",
        }
    return {
        "kind": "q1488_frozen_matched_window_base_pair_table_protocol",
        "proposal_id": "Q1488", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4mitm",
        "run_order": design["run_order"],
        "stages": stages, "cases": cases,
        "source_sha256": source, "input_sha256": inputs,
        "design_sha256": sha(HERE / "design_protocol.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "validation_sha256": sha(HERE / "validation.json"),
        "n53_materialized_point_file_sha256": sha(
            HERE / "n53_window_points.bin"),
        "claim_limit": (
            "matched-input pair-table stage diagnostic, not a compact "
            "solver or complete IC solve"),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = render()
    if args.check:
        assert json.loads(PROTOCOL.read_text()) == current
    else:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(current, indent=2, sort_keys=True) +
                            "\n")
    print(json.dumps({"proposal_id": "Q1488",
                      "stage_ids": {n: item["stage_config_id"]
                                    for n, item in current["stages"].items()},
                      "status": "checked" if args.check else "frozen"},
                     sort_keys=True))
