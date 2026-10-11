#!/usr/bin/env python3
"""Rebuild compact S3 formula shapes at N53, N83, and proposed N131.

The N131 target words are syntactic placeholders. No solver is invoked and
no model or operation-equivalent decomposition cost is inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from chain_s3_multitarget import build_multitarget


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "runs/n53_n83_n131_q1407_compact_formula_shape.json"
SOURCE_PATHS = (
    "experiments/compact-s3-m4-20261003/screen_q1407_compact_formula_shape.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "ecc2k130/codegen/field.py",
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shape(n: int, weight: int, target_xs: list[int]) -> dict:
    formula, leaves, mids, target, selector = build_multitarget(
        n, weight, target_xs)
    assert len(leaves) == 4 and len(mids) == 2
    assert len(target) == n
    assert len(selector) == max(1, (len(target_xs) - 1).bit_length())
    cnf_literals = sum(len(row) for row in formula.clauses)
    xor_literals = sum(len(row) for row, _ in formula.xors)
    return {
        "field_degree_n": n,
        "summands_m": 4,
        "normal_basis_raw_x_weight_bound": weight,
        "target_x_options": len(target_xs),
        "variables": formula.variables,
        "cnf_clauses": len(formula.clauses),
        "xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "cnf_literal_occurrences": cnf_literals,
        "xor_literal_occurrences": xor_literals,
        "total_literal_occurrences": cnf_literals + xor_literals,
        "total_literal_occurrences_log2": math.log2(
            cnf_literals + xor_literals),
        "expanded_s5_materialized": False,
        "solver_attempted": False,
    }


def build() -> dict:
    protocol_path = HERE / "protocol.json"
    coset53_path = HERE / "runs/n53_ordinary_raw_preimages.json"
    stage53_path = HERE / "runs/n53_ordinary_multitarget.json"
    stage83_path = HERE / "runs/n83_q1404_ordinary.json"
    protocol = json.loads(protocol_path.read_text())
    coset53 = json.loads(coset53_path.read_text())
    stage53 = json.loads(stage53_path.read_text())
    stage83 = json.loads(stage83_path.read_text())
    profiles = {p["field"]["n"]: p for p in protocol["profiles"]}
    n53 = profiles[53]
    n83 = profiles[83]
    n131 = protocol["degree_131_design"]
    assert coset53["curve_id"] == n53["curve"]["curve_id"]
    assert coset53["workload_id"] == stage53["workload_id"]
    assert stage53["proposal_id"] == "Q1306"
    assert stage83["proposal_id"] == "Q1404"
    assert stage83["curve_id"] == n83["curve"]["curve_id"]
    assert stage83["workload_id"] == n83["ordinary_workload_id"]
    assert len(coset53["raw_target_x_coordinates"]) == 428
    assert len(stage83["raw_preimage_x_coordinates"]) == 4
    assert n131["factor_base"]["actual_usable_points_B_before_folding"] is None

    exact53 = shape(53, 3, coset53["raw_target_x_coordinates"])
    assert exact53["variables"] == stage53["formula_variables"]
    assert exact53["cnf_clauses"] == stage53["formula_cnf_clauses"]
    assert exact53["xor_rows"] == stage53["formula_xor_rows"]
    assert exact53["and_gates"] == stage53["formula_and_gates"]
    exact83 = shape(83, 5, stage83["raw_preimage_x_coordinates"])
    for name in ("variables", "cnf_clauses", "xor_rows", "and_gates",
                 "cnf_literal_occurrences", "xor_literal_occurrences"):
        assert exact83[name] == stage83["formula"][name]
    # The exact target preimages depend on the public N131 query. The four
    # distinct placeholders fix selector width and clause geometry only.
    proposed131 = shape(131, 6, [1, 2, 4, 8])
    return {
        "kind": "q1407_compact_four_summand_formula_shape_screen",
        "proposal_id": "Q1407",
        "parent_solver_proposal_ids": ["Q1306", "Q1404"],
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "n53_matched_measured_formula_shape": {
            "curve_id": n53["curve"]["curve_id"],
            "factor_base_actual_B": n53["factor_base"][
                "actual_usable_points_B_before_folding"],
            "factor_base_folded_columns_K": n53["factor_base"][
                "signed_frobenius_columns"],
            "ordinary_workload_id": n53["ordinary_workload_id"],
            "formula": exact53,
        },
        "n83_matched_measured_formula_shape": {
            "curve_id": n83["curve"]["curve_id"],
            "factor_base_actual_B": stage83["factor_base_actual_B"],
            "factor_base_folded_columns_K": stage83[
                "factor_base_folded_columns"],
            "ordinary_workload_id": stage83["workload_id"],
            "formula": exact83,
        },
        "n131_placeholder_formula_shape": {
            "curve_id": n131["curve"]["curve_id"],
            "factor_base_actual_B": None,
            "factor_base_folded_columns_K": None,
            "target_x_policy": (
                "four distinct placeholders for syntax and size only; not "
                "actual cofactor preimages of a public curve point"),
            "formula": proposed131,
        },
        "interpretation": (
            "This counts one emitted compact chained-S3 SAT formula. It "
            "does not measure solver search, natural relation yield, final "
            "matrix work, target descent, or complete DLP work."),
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "input_sha256": {
            str(path.relative_to(ROOT)): sha(path) for path in (
                protocol_path, coset53_path, stage53_path, stage83_path)
        },
        "source_sha256": {path: sha(ROOT / path) for path in SOURCE_PATHS},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    serialized = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        assert OUT.read_text() == serialized
        print("PASS: Q1407 compact formula shape matches frozen sources")
    else:
        OUT.write_text(serialized)
        print(OUT)


if __name__ == "__main__":
    main()
