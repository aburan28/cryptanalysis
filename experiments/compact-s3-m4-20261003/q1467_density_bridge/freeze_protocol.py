#!/usr/bin/env python3
"""Freeze exact N53/N83 four-sum supply bridge inputs and selection rule."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
OUTPUT = HERE / "protocol.json"
SOURCES = ("select_n53_base.py", "freeze_protocol.py")
INPUTS = (
    "experiments/compact-s3-m4-20261003/protocol.json",
    "experiments/compact-s3-m4-20261003/bases/n53_weight3_orbits.json.gz",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/n53_w4_base.json",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/protocol.json",
    "experiments/compact-s3-m4-20261003/runs/n83_q1413_projected_x_w4.json",
    "experiments/compact-s3-m4-20261003/runs/n131_q1413_projected_x_w6.json",
    "experiments/compact-s3-m4-20261003/runs/n131_q1414_exact_uniform_query_bound.json",
    "experiments/compact-s3-m4-20261003/enumerate_n83_weight5_full.py",
    "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
    "experiments/compact-s3-m4-20261003/q1438_dense_base/enumerate_base.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "ecc2k130/codegen/field.py",
    "ecc2k130/codegen/curves.py",
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mean_decimal(B: int, r: int) -> str:
    with localcontext() as context:
        context.prec = 60
        return str(Decimal(math.comb(B + 3, 4)) / Decimal(r - 1))


def make() -> dict:
    parent = json.loads((PARENT / "protocol.json").read_text())
    n53 = next(p for p in parent["profiles"] if p["field"]["n"] == 53)
    n83 = next(p for p in parent["profiles"] if p["field"]["n"] == 83)
    w4_83 = json.loads((PARENT /
        "runs/n83_q1413_projected_x_w4.json").read_text())
    w6_131 = json.loads((PARENT /
        "runs/n131_q1413_projected_x_w6.json").read_text())
    bound131 = json.loads((PARENT /
        "runs/n131_q1414_exact_uniform_query_bound.json").read_text())
    B131 = w6_131["actual_usable_points_B_before_folding"]
    r131 = int(bound131["nonidentity_subgroup_target_count"]) + 1
    assert bound131["base_set_sha256"] == w6_131["enumerated_set_sha256"]
    assert bound131["actual_usable_points_B_before_folding"] == B131
    assert n83["curve"]["curve_id"] == w4_83["curve_id"]
    assert w4_83["actual_usable_points_B_before_folding"] == 1934066
    assert w4_83["signed_frobenius_columns_K"] == 11651
    r53 = int(n53["curve"]["subgroup_order"])
    r83 = int(n83["curve"]["subgroup_order"])
    target_mean = math.comb(B131 + 3, 4) / (r131 - 1)
    all_k = range(1, 228)
    selected_k = min(all_k, key=lambda k: abs(math.log2(
        (math.comb(2 * 53 * k + 3, 4) / (r53 - 1)) / target_mean)))
    assert selected_k == 26
    B53 = 2 * 53 * selected_k
    runtime = HERE / "sage_runtime_info.json"
    assert json.loads(runtime.read_text())["status"] == "verified"
    return {
        "kind": "q1467_exact_density_bridge_protocol",
        "proposal_id": "Q1467", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "n53_selection_rule": (
            "first 26 sorted canonical projected x-orbit keys from the "
            "complete N53 W<=3 base; include every rational W<=3 raw x "
            "Frobenius orbit projecting to a selected key"),
        "n53_selection_optimality_rule": (
            "among K=1..227 complete signed Frobenius orbit prefixes, "
            "choose K minimizing absolute log2 difference between "
            "C(2*53*K+3,4)/(r53-1) and the exact N131 W<=6 bound"),
        "selected_n53_projected_orbits_K": selected_k,
        "curve_id": n53["curve"]["curve_id"],
        "profiles": [
            {"degree_n": 53, "curve_id": n53["curve"]["curve_id"],
             "factor_base_policy": "selected_prefix_of_exact_W<=3",
             "factor_base_actual_B": B53,
             "folded_columns_K": selected_k,
             "subgroup_order": r53,
             "uniform_nonidentity_target_mean_multisets_upper_decimal":
                 mean_decimal(B53, r53),
             "enumerated_set_sha256": None},
            {"degree_n": 83, "curve_id": n83["curve"]["curve_id"],
             "factor_base_policy": "exact_W<=4",
             "factor_base_actual_B": w4_83[
                 "actual_usable_points_B_before_folding"],
             "folded_columns_K": w4_83["signed_frobenius_columns_K"],
             "subgroup_order": r83,
             "uniform_nonidentity_target_mean_multisets_upper_decimal":
                 mean_decimal(w4_83[
                     "actual_usable_points_B_before_folding"], r83),
             "enumerated_set_sha256": w4_83["enumerated_set_sha256"]},
            {"degree_n": 131, "curve_id": w6_131["curve_id"],
             "factor_base_policy": "exact_W<=6_reference",
             "factor_base_actual_B": B131,
             "folded_columns_K": w6_131["signed_frobenius_columns_K"],
             "subgroup_order": r131,
             "uniform_nonidentity_target_mean_multisets_upper_decimal":
                 mean_decimal(B131, r131),
             "enumerated_set_sha256": w6_131["enumerated_set_sha256"]},
        ],
        "claim_scope": (
            "exact finite-set counting upper bounds for uniformly drawn "
            "nonidentity subgroup targets; no independence assumption, "
            "natural relation yield, solver work, or complete solve cost"),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "source_sha256": {name: sha(HERE / name) for name in SOURCES},
        "input_sha256": {name: sha(ROOT / name) for name in INPUTS},
        "sage_runtime_info_sha256": sha(runtime),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = make()
    if args.check:
        assert data == json.loads(OUTPUT.read_text())
        print("Q1467 density-bridge protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"proposal_id": "Q1467",
                          "selected_n53_orbits": data[
                              "selected_n53_projected_orbits_K"]}))


if __name__ == "__main__":
    main()
