#!/usr/bin/env python3
"""Independently replay Q1436 models and sampled affine clauses with Sage."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

from sage.all import GF, matrix, vector

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1435 = PARENT / "q1435_bounded_tail"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(Q1420))

from chain_s3 import field  # noqa: E402
from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, check_math, model_from_file)
from q1426_symbolic_pair.build_formula import build_cnf  # noqa: E402
from q1428_bilinear_span.screen import relaxed_feasible, s3  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_snapshot(snapshot: dict, n: int, weight: int) -> tuple[int, ...]:
    names = ("mid_onb_hex", "a_fixed_mask_onb_hex", "a_ones_onb_hex",
             "b_fixed_mask_onb_hex", "b_ones_onb_hex")
    m, af, ao, bf, bo = (int(snapshot[name], 16) for name in names)
    mask = (1 << n) - 1
    assert not ((m | af | ao | bf | bo) & ~mask)
    assert not (ao & ~af) and not (bo & ~bf)
    assert snapshot["free_a"] == n - af.bit_count()
    assert snapshot["free_b"] == n - bf.bit_count()
    assert snapshot["slack_a"] == weight - ao.bit_count()
    assert snapshot["slack_b"] == weight - bo.bit_count()
    assert 1 <= snapshot["free_a"] <= (18 if n == 53 else 24)
    assert 1 <= snapshot["free_b"] <= (18 if n == 53 else 24)
    assert min(snapshot["slack_a"], snapshot["slack_b"]) in (1, 2)
    return m, af, ao, bf, bo


def replay_affine(snapshot: dict, n: int, weight: int) -> tuple[bool, tuple]:
    """Compute S3 columns directly and solve with Sage GF(2) matrices."""
    m, af, ao, bf, bo = parse_snapshot(snapshot, n, weight)
    swapped = False
    if weight - ao.bit_count() > 2:
        swapped = True
    elif weight - bo.bit_count() <= 2:
        def count(fixed, ones):
            k = n - fixed.bit_count()
            slack = weight - ones.bit_count()
            return 1 + k + (k * (k - 1) // 2 if slack == 2 else 0)
        swapped = (count(bf, bo) * (n - af.bit_count()) <
                   count(af, ao) * (n - bf.bit_count()))
    if swapped:
        af, ao, bf, bo = bf, bo, af, ao
    free_a = [j for j in range(n) if not af >> j & 1]
    free_b = [j for j in range(n) if not bf >> j & 1]
    slack_a = weight - ao.bit_count()
    onb = field.Onb(n)
    m_field = onb.fromCoords(m)
    b0 = onb.fromCoords(bo)
    basis_b = [onb.fromCoords(1 << j) for j in free_b]
    roots = []
    unknown = False
    gf2 = GF(2)
    for size in range(slack_a + 1):
        for selected in itertools.combinations(free_a, size):
            a_coords = ao | sum(1 << j for j in selected)
            a_field = onb.fromCoords(a_coords)
            constant = onb.toCoords(s3(onb, a_field, b0, m_field))
            columns = [onb.toCoords(s3(
                onb, a_field, b0 + e, m_field)) ^ constant
                for e in basis_b]
            mat = matrix(gf2, n, len(columns),
                         lambda row, col: (columns[col] >> row) & 1)
            rank = mat.rank()
            augmented = matrix(gf2, n, len(columns) + 1,
                               lambda row, col: ((
                                   columns[col] if col < len(columns)
                                   else constant) >> row) & 1)
            if augmented.rank() > rank:
                continue
            if rank < len(columns):
                unknown = True
                continue
            rhs = vector(gf2, [(constant >> row) & 1 for row in range(n)])
            solution = mat.solve_right(rhs)
            b_coords = bo | sum(1 << j for j, bit in zip(free_b, solution)
                                if bit)
            if b_coords.bit_count() <= weight:
                roots.append((b_coords, a_coords) if swapped else
                             (a_coords, b_coords))
    return unknown, tuple(roots)


def verify_cell(protocol: dict, key: str) -> dict:
    workload = protocol["workloads"][key]
    output = HERE / "runs" / key
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    n, cell = receipt["degree_n"], receipt["cell"]
    assert key == f"n{n}_{cell}"
    assert receipt["proposal_id"] == "Q1436"
    assert receipt["candidate_id"] is None and receipt["isogeny"] == "none"
    for name in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                 "factor_base_enumerated_set_sha256", "public_target",
                 "stage_config_id", "workload_id", "stage_run_id",
                 "target_input_sha256", "target_preimage_x_count",
                 "removed_partner_pin_units"):
        assert receipt[name] == workload[name]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "run_stage.py"]
    assert receipt["solver_binary_sha256"] == protocol["solver_binary_sha256"]
    assert receipt["runtime_info_sha256"] == protocol[
        "sage_runtime_info_sha256"]
    assert sha(Q1420 / "runs" / workload["parent_q1420_key"] /
               "receipt.json") == workload["parent_q1420_receipt_sha256"]
    matched_path = (Q1435 / "runs" / workload["matched_q1435_key"] /
                    "receipt.json")
    assert sha(matched_path) == workload["matched_q1435_receipt_sha256"]
    matched = json.loads(matched_path.read_text())
    assert matched["workload_id"] == receipt["workload_id"]
    assert matched["factor_base_enumerated_set_sha256"] == receipt[
        "factor_base_enumerated_set_sha256"]
    raw, formula, meta, removed, variables, clauses = build_cnf(n, cell)
    assert sha(output / "solver.stdout.txt") == receipt["solver_stdout_sha256"]
    assert sha(output / "solver.stderr.txt") == receipt["solver_stderr_sha256"]
    assert hashlib.sha256(raw).hexdigest() == receipt[
        "cnf_raw_sha256"] == workload["cnf_raw_sha256"]
    assert len(raw) == workload["cnf_raw_bytes"]
    assert variables == receipt["cnf_variables"] == workload["cnf_variables"]
    assert clauses == receipt["cnf_clauses"] == workload["cnf_clauses"]
    assert removed == workload["removed_partner_pin_units"]
    assert meta["curve_id"] == workload["curve_id"]
    report = receipt["solver_report"]
    span_replayed = zero_replayed = unique_replayed = 0
    if report is not None:
        assert report["status"] == {"sat": 10, "censored": 0,
                                     "unsat": 20}[receipt["solver_status"]]
        assert report["screen_window_free_threshold_each_leaf"] == (
            18 if n == 53 else 24)
        assert report["span_checks"] == report["span_checked_state_count"]
        assert report["affine_eligible"] == report["span_checks"] - report[
            "span_rejections"]
        assert report["affine_eligible"] == report["affine_checks"] + report[
            "affine_skipped_budget"]
        assert report["affine_checks"] == sum(report[name] for name in (
            "affine_zero", "affine_unique", "affine_multiple_or_unknown"))
        assert report["affine_field_inv_calls"] == 0
        weight = workload["stage_config_hash_input"]["factor_base"][
            "normal_basis_weight_bound"]
        onb = field.Onb(n)
        basis = [onb.fromCoords(1 << i) for i in range(n)]
        for snapshot in report["span_rejection_snapshots"][:4]:
            m, af, ao, bf, bo = parse_snapshot(snapshot, n, weight)
            check = relaxed_feasible(
                onb, basis, onb.fromCoords(ao), onb.fromCoords(bo),
                onb.fromCoords(m),
                [i for i in range(n) if not af >> i & 1],
                [i for i in range(n) if not bf >> i & 1])
            assert not check["constant_in_span"]
            span_replayed += 1
        for snapshot in report["affine_zero_snapshots"][:4]:
            unknown, roots = replay_affine(snapshot, n, weight)
            assert not unknown and not roots
            zero_replayed += 1
        for item in report["affine_unique_snapshots"][:4]:
            unknown, roots = replay_affine(item["partial"], n, weight)
            assert not unknown and roots == ((
                int(item["unique_a_onb_hex"], 16),
                int(item["unique_b_onb_hex"], 16)),)
            unique_replayed += 1
    if receipt["solver_status"] == "sat":
        assert receipt["solver_model_sha256"] == sha(output / "solver.model.txt")
        model = model_from_file(output / "solver.model.txt")
        check_cnf(raw, model, variables, clauses)
        relation = check_math(formula, meta, model)
        assert relation == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
    else:
        assert receipt["solver_model_sha256"] is None
        assert receipt["model_check"] is None
        assert receipt["verified_relation_count"] == 0
        assert receipt["solver_status"] in ("censored", "external_timeout",
                                            "unsat", "error")
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["complete_solve_work_log2"] is None
    return {"key": key, "status": receipt["solver_status"],
            "verified_relation_count": receipt["verified_relation_count"],
            "sampled_span_rejections": span_replayed,
            "sampled_affine_zero_checks": zero_replayed,
            "sampled_affine_unique_checks": unique_replayed,
            "affine_checks": (report or {}).get("affine_checks"),
            "affine_zero": (report or {}).get("affine_zero"),
            "affine_unique": (report or {}).get("affine_unique"),
            "receipt_sha256": sha(receipt_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["source_sha256"]["verify_archive.py"] == sha(
        HERE / "verify_archive.py")
    checks, missing = [], []
    for key in protocol["run_order"]:
        if (HERE / "runs" / key / "receipt.json").exists():
            checks.append(verify_cell(protocol, key))
        else:
            missing.append(key)
    assert not args.require_complete or not missing
    report = {"kind": "q1436_affine_pair_archive_verification",
              "proposal_id": "Q1436", "candidate_id": None,
              "protocol_sha256": sha(PROTOCOL),
              "verifier_source_sha256": sha(Path(__file__)),
              "checks": checks, "missing": missing, "complete": not missing,
              "natural_relation_yield_estimate": None,
              "complete_solve_work_log2": None}
    if args.emit:
        (HERE / "verification.json").write_text(json.dumps(
            report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"checked": len(checks), "missing": missing,
                      "verified_relations": sum(row[
                          "verified_relation_count"] for row in checks)}))


if __name__ == "__main__":
    main()
