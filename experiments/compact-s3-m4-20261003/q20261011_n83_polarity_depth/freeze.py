#!/usr/bin/env python3
"""Freeze Q1475 deeper comparison before either solver attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1473 = PARENT / "q20261011_selector_polarity"
Q1474 = PARENT / "q20261011_n83_propagation_probe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior = json.loads((Q1474 / "freeze.json").read_text())
    q1474 = json.loads((Q1474 / "analysis.json").read_text())
    assert q1474["proposal_id"] == "Q1474" and q1474[
        "prefix_dominating_plain_best_phase"] == 1
    assert q1474["prefix_dominating_plain_best_flip_ids"] == [2140]
    assert protocol["phase_order"] == [0, 1]
    assert protocol["workload_id"] == prior["workload_id"]
    assert protocol["curve_id"] == prior["ordinary_cell"]["curve_id"]
    assert protocol["factor_base_actual_B"] == prior["ordinary_cell"][
        "factor_base_actual_B"]
    assert protocol["factor_base_folded_columns_K"] == prior["ordinary_cell"][
        "factor_base_folded_columns_K"]
    assert protocol["isogeny"] == "none"
    for label, file in (("freeze", "freeze.json"), ("build", "build_receipt.json"),
                        ("smoke", "smoke_receipt.json"), ("target", "target.json")):
        assert sha(Q1473 / file) == prior[f"q1473_{label}_sha256"]
    assert sha(Path(prior["binary_path"])) == prior["binary_sha256"]
    for kind in ("derived", "source"):
        cell = prior["ordinary_cell"]
        assert sha(Path(cell[f"{kind}_archive_path"])) == cell[f"{kind}_archive_sha256"]
    files = {name: sha(HERE / name) for name in
             ("protocol.json", "freeze.py", "run.py", "validate.py")}
    frozen = {"proposal_id": "Q1475", "candidate_id": None, "run_id": None,
              "files_sha256": files, "q1474_freeze_sha256": sha(Q1474 / "freeze.json"),
              "q1474_analysis_sha256": sha(Q1474 / "analysis.json"),
              "q1474_runner_sha256": sha(Q1474 / "run.py"),
              "q1473_smoke_sha256": sha(Q1473 / "smoke_receipt.json"),
              "q1473_target_sha256": sha(Q1473 / "target.json"),
              "binary_path": prior["binary_path"],
              "binary_sha256": prior["binary_sha256"],
              "ordinary_cell": prior["ordinary_cell"],
              "phase_schedule": prior["phase_schedule"]}
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1475 frozen", protocol["checkpoint_left_branches"], "branches")


if __name__ == "__main__":
    main()
