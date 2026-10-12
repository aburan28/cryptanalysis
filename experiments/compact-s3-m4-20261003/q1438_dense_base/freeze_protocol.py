#!/usr/bin/env python3
"""Freeze Q1438 exact dense-base enumeration before either degree runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
PROTOCOL = HERE / "protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make():
    runtime = HERE / "sage_runtime_info.json"
    assert json.loads(runtime.read_text())["status"] == "verified"
    parent_path = PARENT / "protocol.json"
    parent = json.loads(parent_path.read_text())
    profiles = {row["field"]["n"]: row for row in parent["profiles"]}
    q1413 = json.loads((PARENT / "runs/n83_q1413_projected_x_w5.json").read_text())
    assert q1413["signed_frobenius_columns_K"] == 186612
    dependencies = (
        "ecc2k130/codegen/field.py",
        "ecc2k130/codegen/curves.py",
        "experiments/koblitz-pair-claw-20260929/orbit_key.py",
        "experiments/compact-s3-m4-20261003/enumerate_n83_weight5_full.py",
        "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
        "experiments/compact-s3-m4-20261003/run_probe.py",
    )
    instances = {
        "53": {"curve_id": "EC1N53Ckb1hf77aab617904",
               "subgroup_order": 21044858204113,
               "cofactor": 428,
               "reference_weight_bound": 3,
               "reference_actual_B": 24062,
               "reference_columns_K": 227,
               "new_weight_bound": 4},
        "83": {"curve_id": "EC1N83Ckb1h876c2921cb64",
               "subgroup_order": 2417851639230796216685689,
               "cofactor": 4,
               "reference_weight_bound": 5,
               "reference_actual_B": 30977592,
               "reference_columns_K": 186612,
               "new_weight_bound": 6},
    }
    for n_text, item in instances.items():
        profile = profiles[int(n_text)]
        assert profile["curve"]["curve_id"] == item["curve_id"]
        assert profile["curve"]["subgroup_order"] == item["subgroup_order"]
        assert profile["curve"]["cofactor"] == item["cofactor"]
        if int(n_text) == 53:
            assert profile["factor_base"][
                "actual_usable_points_B_before_folding"] == item[
                    "reference_actual_B"]
        else:
            assert q1413["actual_usable_points_B_before_folding"] == item[
                "reference_actual_B"]
        item["field"] = profile["field"]
        item["curve"] = profile["curve"]
    return {
        "kind": "q1438_frozen_exact_dense_base_protocol",
        "proposal_id": "Q1438", "candidate_id": None,
        "isogeny": "none",
        "question": (
            "Can a one-unit larger normal-basis weight bound improve "
            "ordinary four-summand relation search on the same exact "
            "N53/N83 curves and public targets?"),
        "instances": instances,
        "run_order": ["n53_w4", "n83_w6"],
        "parent_protocol_sha256": sha(parent_path),
        "source_sha256": sha(HERE / "enumerate_base.py"),
        "verifier_sha256": sha(HERE / "verify_base.py"),
        "freeze_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(runtime),
        "dependency_sha256": {name: sha(ROOT / name)
                              for name in dependencies},
        "reference_n53_base_sha256": sha(
            PARENT / "bases/n53_weight3_orbits.json.gz"),
        "reference_n83_w5_receipt_sha256": sha(
            PARENT / "runs/n83_q1413_projected_x_w5.json"),
        "claim_scope": (
            "Exact projected factor-base geometry and independent sampled "
            "group-law controls, not ordinary point-decomposition yield, "
            "solver performance, full IC candidate, or N131 work."),
    }


def main():
    data = make()
    if PROTOCOL.exists():
        assert json.loads(PROTOCOL.read_text()) == data
        print("Q1438 protocol verified")
    else:
        PROTOCOL.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("Q1438 protocol frozen")


if __name__ == "__main__":
    main()
