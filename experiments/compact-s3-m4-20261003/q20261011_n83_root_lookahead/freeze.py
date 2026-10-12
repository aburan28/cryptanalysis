#!/usr/bin/env python3
"""Freeze two exact ordinary formulas and the root-probe patch source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1473 = PARENT / "q20261011_selector_polarity"
Q1475 = PARENT / "q20261011_n83_polarity_depth"
Q1476 = PARENT / "q20261011_n83_selector_holdout"
SRC = Path("/Volumes/SSD990/llm/tmp/q1473_wdsat_build/n83/src")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior_build = json.loads((Q1473 / "build_receipt.json").read_text())
    smoke = json.loads((Q1473 / "smoke_receipt.json").read_text())
    selected = json.loads((Q1475 / "analysis.json").read_text())
    holdout = json.loads((Q1476 / "analysis.json").read_text())
    assert protocol["proposal_id"] == "Q1477" and smoke["status"] == "PASS"
    assert protocol["ordinary_workloads"] == [selected["workload_id"],
                                                holdout["workload_id"]]
    assert selected["rows"][1]["cnf_calls_over_plain"] < 1
    assert holdout["holdout_flip2140_cnf_calls_over_plain"] > 1
    assert protocol["probe_literals"] == [-2140, 2140]
    assert sha(SRC / "wdsat.c") == prior_build["selector_patch"]["wdsat_c_sha256"]
    assert sha(SRC / "config.h") == prior_build["config_sha256"]
    assert sha(Path(prior_build["binary_path"])) == prior_build["binary_sha256"]
    assert smoke["binary_sha256"] == prior_build["binary_sha256"]
    inputs = {"control": {"path": str(Q1473 / "smoke.xcnf"),
                          "sha256": sha(Q1473 / "smoke.xcnf"),
                          "workload_id": "satisfiable_native_xor_control"}}
    for label, root, workload in (("selected", Q1475, selected["workload_id"]),
                                  ("holdout", Q1476, holdout["workload_id"])):
        archive = (PARENT / "q20261011_wdsat_phase_restart/width4.xcnf.gz"
                   if label == "selected" else Q1476 / "width4.xcnf.gz")
        inputs[label] = {"path": str(archive), "sha256": sha(archive),
                         "workload_id": workload,
                         "analysis_sha256": sha(root / "analysis.json")}
    files = {name: sha(HERE / name) for name in
             ("protocol.json", "freeze.py", "build.py", "run.py", "validate.py")}
    out = {"proposal_id": "Q1477", "candidate_id": None, "run_id": None,
           "files_sha256": files,
           "q1473_build_sha256": sha(Q1473 / "build_receipt.json"),
           "q1473_smoke_sha256": sha(Q1473 / "smoke_receipt.json"),
           "parent_source_dir": str(SRC),
           "parent_wdsat_c_sha256": sha(SRC / "wdsat.c"),
           "parent_config_sha256": sha(SRC / "config.h"),
           "inputs": inputs}
    (HERE / "freeze.json").write_text(json.dumps(out, indent=2,
                                                sort_keys=True) + "\n")
    print("Q1477 root inputs frozen", list(inputs))


if __name__ == "__main__":
    main()
