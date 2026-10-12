#!/usr/bin/env python3
"""Derive branch priorities from byte-identical ordinary/control S3 formulas."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1466 = PARENT / "q20261011_wdsat_deep_plain"
sys.path.insert(0, str(PARENT))
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
sys.path.insert(0, str(PARENT / "q1419_partial_pin"))
from run_cell import build_cell  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def serialized_sha(formula) -> str:
    with tempfile.TemporaryDirectory(prefix="q1467_formula_", dir="/Volumes/SSD990/llm/tmp") as directory:
        path = Path(directory) / "formula.xcnf"
        formula.write(path)
        return sha(path)


def main() -> None:
    assert not (HERE / "order_manifest.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    q1466 = json.loads((Q1466 / "freeze.json").read_text())
    q1419 = json.loads((PARENT / "q1419_partial_pin/protocol.json").read_text())
    assert protocol["proposal_id"] == "Q1467"
    cells = {}
    for degree, parent_id, weight in ((53, 1410, 3), (83, 1408, 5)):
        name = f"n{degree}"
        ordinary_receipt = PARENT / "runs" / f"{name}_q{parent_id}_ordinary.json"
        ordinary_parent = json.loads(ordinary_receipt.read_text())
        original_archive = PARENT / "runs" / f"{name}_q{parent_id}_ordinary.xcnf.gz"
        ordinary_raw = gzip.decompress(original_archive.read_bytes())
        formula, leaves, mids, _, selector = build_balanced(
            degree, weight, ordinary_parent["raw_preimage_x_coordinates"])
        assert serialized_sha(formula) == hashlib.sha256(ordinary_raw).hexdigest()
        assert ordinary_parent["curve_id"] == q1466["cells"][f"{name}_ordinary"]["curve_id"]
        profile = q1419["profiles"][str(degree)]
        control_parent_path = PARENT.parents[1] / profile["parent_receipt"]["path"]
        fixture_path = PARENT.parents[1] / profile["fixture_receipt"]["path"]
        control_parent = json.loads(control_parent_path.read_text())
        fixture = json.loads(fixture_path.read_text())
        control_formula, control_leaves, _ = build_cell(profile, control_parent, fixture, "full_lock")
        control_archive = PARENT / "q1419_partial_pin/runs" / f"{name}_full_lock/system.xcnf.gz"
        control_raw = gzip.decompress(control_archive.read_bytes())
        assert serialized_sha(control_formula) == hashlib.sha256(control_raw).hexdigest()
        assert control_leaves == leaves
        _, _, _, _, control_selector = build_balanced(
            degree, weight, control_parent["raw_preimage_x_coordinates"])
        assert control_selector == selector
        interleaved = [leaves[leaf][bit] for bit in range(degree) for leaf in range(4)]
        assert len(interleaved) == 4 * degree
        assert len(set(interleaved)) == len(interleaved)
        assert all(1 <= value <= formula.variables for value in interleaved + selector)
        cells[name] = {"curve_id": ordinary_parent["curve_id"],
                       "ordinary_workload_id": ordinary_parent["workload_id"],
                       "factor_base_actual_B": ordinary_parent["factor_base_actual_B"],
                       "factor_base_enumerated_set_sha256": ordinary_parent["factor_base_enumerated_set_sha256"],
                       "ordinary_source_receipt_sha256": sha(ordinary_receipt),
                       "ordinary_original_xcnf_sha256": hashlib.sha256(ordinary_raw).hexdigest(),
                       "control_original_xcnf_sha256": hashlib.sha256(control_raw).hexdigest(),
                       "control_parent_receipt_sha256": sha(control_parent_path),
                       "control_fixture_receipt_sha256": sha(fixture_path),
                       "original_variables": formula.variables,
                       "selector_priority": selector,
                       "interleaved_leaves_priority": interleaved,
                       "pair_mid_first_ids": [value for pair in mids for value in pair]}
        print(name, "selector", selector, "interleaved", len(interleaved),
              "source_matched", True)
    output = {"proposal_id": "Q1467", "candidate_id": None,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": sha(Path(__file__)),
              "q1466_freeze_sha256": sha(Q1466 / "freeze.json"),
              "balanced_source_sha256": sha(PARENT / "chain_s3_balanced_multitarget.py"),
              "q1419_build_cell_source_sha256": sha(PARENT / "q1419_partial_pin/run_cell.py"),
              "cells": cells}
    (HERE / "order_manifest.json").write_text(json.dumps(output, indent=2,
                                                         sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
