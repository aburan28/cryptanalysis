#!/usr/bin/env python3
"""Materialize and replay exact Q1483 fixed-window input bytes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from build_formula import DESIGN, HERE, Q1481, Q1438, Q1482, ORDINARY, build_cnf


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(case: str, check: bool) -> dict:
    n_text, role = case.split("_", 1)
    n = int(n_text[1:])
    design = json.loads(DESIGN.read_text())
    item = design["instances"][str(n)]
    d = item["nominal_window_dimension_d"]
    base_path = Q1481 / f"n{n}_d{d}_base.json"
    base = json.loads(base_path.read_text())
    assert base["actual_usable_points_B_before_folding"] == item[
        "actual_usable_B"]
    assert base["enumerated_set_sha256"] == item[
        "enumerated_set_sha256"]
    raw, varmap, targets, _, meta, variables, clauses = build_cnf(n, role)
    if role == "ordinary":
        old = json.loads((Q1438 / "solver_protocol.json").read_text())[
            "workloads"][case]
        assert old["workload_id"] == item["ordinary_parent_workload_id"]
        assert hashlib.sha256(targets).hexdigest() == old[
            "target_input_sha256"]
        fixture_sha = None
        parent_sha = sha(ORDINARY[n])
    else:
        fixture_path = Q1482 / f"n{n}_planted_fixture.json"
        fixture = json.loads(fixture_path.read_text())
        assert fixture["proposal_id"] == "Q1482"
        assert fixture["curve_id"] == item["curve_id"]
        assert fixture["factor_base_enumerated_set_sha256"] == item[
            "enumerated_set_sha256"]
        fixture_sha = sha(fixture_path)
        parent_sha = fixture_sha
    output = HERE / "inputs" / case
    packed = gzip.compress(raw, mtime=0)
    summary = {
        "kind": "q1483_frozen_fixed_window_s3_input",
        "proposal_id": "Q1483", "candidate_id": None,
        "isogeny": "none", "case": case, "degree_n": n,
        "role": role, "curve_id": item["curve_id"],
        "factor_base_actual_B": item["actual_usable_B"],
        "folded_columns_K": item["folded_K"],
        "factor_base_enumerated_set_sha256": item[
            "enumerated_set_sha256"],
        "factor_base_receipt_sha256": sha(base_path),
        "planted_fixture_sha256": fixture_sha,
        "parent_target_or_fixture_sha256": parent_sha,
        "public_target": meta["public_target"],
        "target_preimage_x_count": meta["target_preimage_x_count"],
        "cnf_variables": variables, "cnf_clauses": clauses,
        "cnf_raw_bytes": len(raw),
        "cnf_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "input_sha256": {
            "system.cnf.gz": hashlib.sha256(packed).hexdigest(),
            "variables.txt": hashlib.sha256(varmap).hexdigest(),
            "targets.txt": hashlib.sha256(targets).hexdigest(),
        },
        "design_sha256": sha(DESIGN),
        "formula_source_sha256": sha(HERE / "build_formula.py"),
        "preparer_source_sha256": sha(Path(__file__)),
        "ordinary_relation_yield_estimate": None,
        "complete_solve_work_log2": None,
    }
    if check:
        assert json.loads((output / "input.json").read_text()) == summary
        assert (output / "system.cnf.gz").read_bytes() == packed
        assert (output / "variables.txt").read_bytes() == varmap
        assert (output / "targets.txt").read_bytes() == targets
    else:
        assert not output.exists(), "refuse to overwrite frozen input"
        output.mkdir(parents=True)
        (output / "system.cnf.gz").write_bytes(packed)
        (output / "variables.txt").write_bytes(varmap)
        (output / "targets.txt").write_bytes(targets)
        (output / "input.json").write_text(json.dumps(
            summary, indent=2, sort_keys=True) + "\n")
    return {"case": case, "cnf_variables": variables,
            "cnf_clauses": clauses,
            "target_preimage_x_count": meta["target_preimage_x_count"],
            "status": "checked" if check else "frozen"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    design = json.loads(DESIGN.read_text())
    assert args.case in design["run_order"]
    print(json.dumps(prepare(args.case, args.check)), flush=True)


if __name__ == "__main__":
    main()
