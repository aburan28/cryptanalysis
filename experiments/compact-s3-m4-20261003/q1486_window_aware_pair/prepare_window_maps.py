#!/usr/bin/env python3
"""Expose Q1482's existing cyclic-window selectors to Q1486 native theory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1482 = PARENT / "q1482_window_s3"
sys.path.insert(0, str(Q1482))
from build_formula import build_cnf  # noqa: E402
sys.path.insert(0, str(PARENT))
from run_probe import field  # noqa: E402
from q1481_window_orbit_base.enumerate_base import OrbitKey  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(case: str, parent: dict) -> tuple[bytes, dict]:
    entry = parent["cases"][case]
    n, role = entry["degree_n"], entry["role"]
    raw, _, targets, formula, meta, variables, clauses = build_cnf(n, role)
    assert hashlib.sha256(raw).hexdigest() == entry["cnf_raw_sha256"]
    assert variables == entry["cnf_variables"]
    assert clauses == entry["cnf_clauses"]
    assert hashlib.sha256(targets).hexdigest() == entry[
        "input_sha256"]["targets.txt"]
    windows = meta["window_selector_variables"]
    leaves = meta["leaf_variables"]
    assert len(windows) == len(leaves) == 4
    assert all(len(row) == n for row in windows)
    assert len({bit for row in windows for bit in row}) == 4 * n
    orbit = OrbitKey(field.Onb(n))
    cycle = orbit.coordinate_cycle
    assert len(cycle) == n and set(cycle) == set(range(n))
    d = meta["nominal_window_dimension_d"]
    masks = []
    for start in range(n):
        allowed = {(start + step) % n for step in range(d)}
        mask = sum(1 << cycle[index] for index in allowed)
        assert mask.bit_count() == d
        masks.append(mask)
    # Verify the map against the actual original CNF construction, not just
    # a parallel window formula. Every selected-window outside-zero clause
    # must be present in the reused Q1482 formula.
    binary = {tuple(row) for row in formula.clauses
              if len(row) == 2 and row[0] < 0}
    checked_clauses = 0
    for leaf in range(4):
        for start, selector in enumerate(windows[leaf]):
            mask = masks[start]
            for coordinate, bit in enumerate(leaves[leaf]):
                if not (mask >> coordinate) & 1:
                    assert (-selector, -bit) in binary
                    checked_clauses += 1
    lines = [f"Q1486WIN1 {n} {d}"]
    lines.extend(" ".join(map(str, row)) for row in windows)
    lines.extend(format(mask, "x") for mask in masks)
    data = ("\n".join(lines) + "\n").encode("ascii")
    receipt = {
        "kind": "q1486_exact_existing_window_selector_map",
        "proposal_id": "Q1486", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "case": case, "curve_id": entry["curve_id"],
        "degree_n": n, "window_dimension_d": d,
        "factor_base_actual_B": entry["factor_base_actual_B"],
        "folded_columns_K": entry["folded_columns_K"],
        "factor_base_enumerated_set_sha256": entry[
            "factor_base_enumerated_set_sha256"],
        "q1482_cnf_raw_sha256": entry["cnf_raw_sha256"],
        "q1482_target_sha256": entry["input_sha256"]["targets.txt"],
        "q1482_variable_map_sha256": entry["input_sha256"]["variables.txt"],
        "existing_window_selector_count": 4 * n,
        "checked_original_window_clauses": checked_clauses,
        "sidecar_map_sha256": hashlib.sha256(data).hexdigest(),
        "source_sha256": sha(Path(__file__)),
        "parent_protocol_sha256": sha(Q1482 / "protocol.json"),
    }
    return data, receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parent = json.loads((Q1482 / "protocol.json").read_text())
    design = json.loads((HERE / "design_protocol.json").read_text())
    assert design["run_order"] == parent["run_order"]
    summaries = []
    for case in design["run_order"]:
        data, receipt = render(case, parent)
        folder = HERE / "inputs" / case
        map_path = folder / "windows.map"
        receipt_path = folder / "map_receipt.json"
        if args.check:
            assert map_path.read_bytes() == data
            assert json.loads(receipt_path.read_text()) == receipt
        else:
            assert not folder.exists(), "refuse overwrite"
            folder.mkdir(parents=True)
            map_path.write_bytes(data)
            receipt_path.write_text(json.dumps(receipt, indent=2,
                                               sort_keys=True) + "\n")
        summaries.append({"case": case,
                          "sidecar_map_sha256": receipt[
                              "sidecar_map_sha256"]})
    print(json.dumps({"status": "checked" if args.check else "frozen",
                      "maps": summaries}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
