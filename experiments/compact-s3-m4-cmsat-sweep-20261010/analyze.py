#!/usr/bin/env python3
"""Bind target identities and summarize the censored SAT sweep."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def build() -> dict:
    freeze = read(HERE / "freeze.json")
    audit = read(HERE / "audit.json")
    parent = read(PARENT / "q1419_partial_pin/protocol.json")
    assert audit["status"] == "PASS" and len(audit["rows"]) == 18
    assert audit["freeze_sha256"] == sha(HERE / "freeze.json")
    assert freeze["parent_q1419_protocol_sha256"] == sha(
        PARENT / "q1419_partial_pin/protocol.json")
    targets = {}
    for name in freeze["inputs"]:
        n = name[1:3]
        profile = parent["profiles"][n]
        path = (PARENT / "runs/n83_q1408_ordinary.json"
                if name == "n83_ordinary"
                else ROOT / profile["parent_receipt"]["path"])
        receipt = read(path)
        actual = freeze["profiles"][n]
        assert receipt["curve_id"] == actual["curve_id"]
        assert receipt["factor_base_actual_B"] == actual[
            "actual_usable_points_B"]
        assert receipt["factor_base_folded_columns"] == actual[
            "folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == actual[
            "factor_base_enumerated_set_sha256"]
        assert receipt["attempts"][0]["xcnf_sha256"] == freeze[
            "inputs"][name]["raw_sha256"]
        targets[name] = {
            "curve_id": actual["curve_id"],
            "workload_id": receipt["workload_id"],
            "public_target": receipt["public_target"],
            "parent_receipt_sha256": sha(path),
            "formula_raw_sha256": freeze["inputs"][name]["raw_sha256"],
            "actual_usable_points_B": actual["actual_usable_points_B"],
            "folded_columns_K": actual["folded_columns_K"],
            "factor_base_enumerated_set_sha256": actual[
                "factor_base_enumerated_set_sha256"],
            "input_law": freeze["input_laws"][name],
        }
    cells = []
    for name, setting in freeze["cell_order"]:
        label = f"{name}__{setting}"
        receipt = read(HERE / "runs" / f"{label}.json")
        assert receipt["status"] == "BOUNDED_UNKNOWN"
        assert receipt["external_timeout"]
        assert receipt["return_code"] == -9
        cells.append({"cell": label, "input_name": name,
                      "setting": setting, "status": receipt["status"],
                      "wall_seconds_exploratory": receipt[
                          "wall_seconds_exploratory"],
                      "peak_child_rss_bytes": receipt[
                          "peak_child_rss_ru_maxrss"],
                      "solver_search_began": True,
                      "reported_final_conflict_count": receipt[
                          "conflicts_reported"]})
    followup = read(HERE / "gauss25000.audit.json")
    assert followup["status"] == "PASS" and len(followup["rows"]) == 2
    assert followup["freeze_sha256"] == sha(HERE / "gauss25000.freeze.json")
    assert all(row["status"] == "BOUNDED_UNKNOWN" and
               row["gaussian_matrices_active"] == 3
               for row in followup["rows"])
    return {
        "schema": "q20261010125300-cmsat-analysis-v2",
        "proposal_id": freeze["proposal_id"], "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "audit_sha256": sha(HERE / "audit.json"),
        "host_observation_sha256": sha(HERE / "host_observation.json"),
        "gauss25000_audit_sha256": sha(HERE / "gauss25000.audit.json"),
        "source_sha256": sha(Path(__file__)),
        "targets": targets, "cells": cells,
        "all_18_cells_bounded_unknown": True,
        "all_20_cells_bounded_unknown": True,
        "n83_gauss25000_active_matrices": 3,
        "ordinary_relation_yield_observed": 0,
        "natural_relation_yield_rate_estimate": None,
        "promoted_setting": None,
        "complete_n131_solve_work_log2": None,
        "scope": "One highly contended host observation and one run per setting, including two separately frozen N83 Gaussian-width follow-ups. External wall caps censored every ordinary and satisfiable-control cell without a final reported conflict count. No measured setting speed ranking or solver-growth extrapolation follows.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / "analysis.json"
    content = json.dumps(build(), sort_keys=True, indent=2) + "\n"
    if args.check:
        assert path.read_text() == content
        print("PASS: target-bound sweep analysis")
    else:
        assert not path.exists()
        path.write_text(content)
        print(json.dumps({"status": "PASS", "cells": 20,
                          "targets": 3}))


if __name__ == "__main__":
    main()
