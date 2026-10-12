#!/usr/bin/env python3
"""Freeze the holdout's source, scalar law, base, and selected comparator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1472 = PARENT / "q20261011_wdsat_phase_restart"
Q1473 = PARENT / "q20261011_selector_polarity"
Q1475 = PARENT / "q20261011_n83_polarity_depth"
BASE = PARENT / "bases/n83_weight5_full_orbits.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "input_freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    base = json.loads(BASE.read_text())
    prior = json.loads((Q1475 / "analysis.json").read_text())
    binary = json.loads((Q1473 / "build_receipt.json").read_text())
    smoke = json.loads((Q1473 / "smoke_receipt.json").read_text())
    assert protocol["proposal_id"] == "Q1476"
    assert protocol["workload_id"] is None
    assert runtime["status"] == "verified"
    assert prior["proposal_id"] == "Q1475"
    assert prior["rows"][1]["flip_ids"] == [2140]
    assert prior["plain_vs_selector2140_cnf_reduction_fraction"] > 0
    assert prior["plain_vs_selector2140_xor_reduction_fraction"] > 0
    assert protocol["phase_order"] == [0, 1]
    assert base["curve"]["curve_id"] == protocol["curve_id"]
    fb = base["factor_base"]
    assert fb["actual_usable_points_B_before_folding"] == protocol[
        "factor_base_actual_B"]
    assert fb["signed_frobenius_columns"] == protocol[
        "factor_base_folded_columns_K"]
    assert smoke["status"] == "PASS" and smoke["binary_sha256"] == binary[
        "binary_sha256"]
    assert sha(Path(binary["binary_path"])) == binary["binary_sha256"]
    output = {
        "proposal_id": "Q1476", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "prepare_target_source_sha256": sha(HERE / "prepare_target.py"),
        "input_freeze_source_sha256": sha(Path(__file__)),
        "q1472_generator_sha256": sha(Q1472 / "prepare_target.py"),
        "q1472_target_sha256": sha(Q1472 / "target.json"),
        "base_sha256": sha(BASE),
        "base_enumerated_set_sha256": fb["enumerated_set_sha256"],
        "q1475_analysis_sha256": sha(Q1475 / "analysis.json"),
        "q1473_build_sha256": sha(Q1473 / "build_receipt.json"),
        "q1473_smoke_sha256": sha(Q1473 / "smoke_receipt.json"),
        "binary_path": binary["binary_path"],
        "binary_sha256": binary["binary_sha256"],
        "target_generation_seed": protocol["target_generation_seed"],
        "cofactor_kernel_seed": protocol["cofactor_kernel_seed"],
        "selected_flip_ids": [2140]}
    (HERE / "input_freeze.json").write_text(json.dumps(output, indent=2,
                                                       sort_keys=True) + "\n")
    print("Q1476 input law frozen", protocol["target_generation_seed"])


if __name__ == "__main__":
    main()
