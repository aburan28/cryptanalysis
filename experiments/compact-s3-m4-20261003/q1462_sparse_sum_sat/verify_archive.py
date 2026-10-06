#!/usr/bin/env python3
"""Audit Q1462 receipts and independently enumerate affordable snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1461 = PARENT / "q1461_sparse_sum_inverse"
sys.path.insert(0, str(PARENT))

from q1438_dense_base.build_formula import build_cnf  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "verification.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_one(n: int, protocol: dict) -> dict:
    cell = protocol["cells"][str(n)]
    output = HERE / f"runs/n{n}_ordinary"
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["proposal_id"] == "Q1462"
    assert receipt["curve_id"] == cell["curve_id"]
    assert receipt["workload_id"] == cell["workload_id"]
    assert receipt["factor_base_actual_B"] == cell["factor_base_actual_B"]
    assert receipt["folded_columns_K"] == cell["folded_columns_K"]
    assert receipt["factor_base_enumerated_set_sha256"] == cell[
        "factor_base_enumerated_set_sha256"]
    assert receipt["sum_candidate_cap"] == cell["sum_candidate_cap"]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["solver_binary_sha256"] == protocol[
        "solver_binary_sha256"]
    for name in ("solver.stdout.txt", "solver.stderr.txt"):
        assert receipt[name.replace(".", "_").replace("_txt", "_sha256")] == sha(
            output / name)
    assert receipt["cnf_archive_sha256"] == sha(output / "system.cnf.gz")
    if receipt["solver_model_sha256"] is not None:
        assert receipt["solver_model_sha256"] == sha(
            output / "solver.model.txt")
    report = receipt["solver_report"]
    direct_replays = 0
    if report is not None:
        assert json.loads((output / "solver.stdout.txt").read_text()) == report
        assert report["sum_checks"] == (
            report["sum_checks_pair0"] + report["sum_checks_pair1"])
        assert report["sum_rejections"] == (
            report["sum_rejections_pair0"] + report["sum_rejections_pair1"])
        rows = [s for s in report["sum_snapshots"]
                if s["direct_pair_candidates"] <= 1000000]
        if rows:
            lines = [" ".join(map(str, (
                f"n{n}_ordinary", i, s["pair"], s["mid_onb_hex"],
                s["a_fixed_mask_onb_hex"], s["a_ones_onb_hex"],
                s["b_fixed_mask_onb_hex"], s["b_ones_onb_hex"])))
                for i, s in enumerate(rows)]
            completed = subprocess.run(
                [str(Q1461 / "probe"),
                 str(PARENT / f"q1420_root_theory/n{n}_field.txt"),
                 str(cell["weight_bound"]), str(cell["sum_candidate_cap"]),
                 "1000000"], input="\n".join(lines) + "\n",
                capture_output=True, text=True, check=True)
            observed = [json.loads(line) for line in
                        completed.stdout.splitlines()[1:]]
            assert len(observed) == len(rows)
            for expected, measured in zip(rows, observed):
                assert measured["sum_candidate_count"] == expected[
                    "sum_candidates"]
                assert measured["pair_candidates"] == expected[
                    "direct_pair_candidates"]
                assert (measured["verified_pairs"] == 0) == expected[
                    "no_pair"]
            direct_replays = len(rows)
    replay_status = None
    if receipt["solver_status"] == "sat":
        raw, _, formula, meta, variables, clauses = build_cnf(n, "ordinary")
        assert hashlib.sha256(raw).hexdigest() == cell["cnf_raw_sha256"]
        parent = json.loads((PARENT /
            "q1438_dense_base/solver_protocol.json").read_text())
        relation = model_relation(
            raw, formula, meta, variables, clauses,
            output / "solver.model.txt", parent["instances"][str(n)])
        replay_status = relation["status"]
        assert relation == receipt["model_check"]
    return {
        "degree_n": n, "curve_id": cell["curve_id"],
        "workload_id": cell["workload_id"],
        "solver_status": receipt["solver_status"],
        "verified_relation_count": receipt["verified_relation_count"],
        "sum_checks": (report or {}).get("sum_checks"),
        "sum_rejections": (report or {}).get("sum_rejections"),
        "sampled_direct_pair_replays": direct_replays,
        "independent_relation_replay_status": replay_status,
        "receipt_sha256": sha(output / "receipt.json"),
    }


def make_result() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1462"
    for section in ("source_sha256", "input_sha256"):
        for relative, digest in protocol[section].items():
            assert sha(ROOT / relative) == digest, relative
    assert sha(HERE / "native_solver") == protocol["solver_binary_sha256"]
    q1461_build = json.loads((Q1461 / "compile_receipt.json").read_text())
    assert sha(Q1461 / "probe") == q1461_build[
        "binary_sha256"]["probe"]
    rows = [audit_one(n, protocol) for n in (53, 83)]
    return {
        "kind": "q1462_sparse_sum_sat_archive_verification",
        "proposal_id": "Q1462", "candidate_id": None, "run_id": None,
        "isogeny": "none", "status": "pass",
        "protocol_sha256": sha(PROTOCOL),
        "rows": rows,
        "verified_ordinary_relations": sum(
            row["verified_relation_count"] for row in rows),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_result()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == result
        print("Q1462 ordinary archive: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1462", "status": "pass",
                          "verified_ordinary_relations": result[
                              "verified_ordinary_relations"]}))


if __name__ == "__main__":
    main()
