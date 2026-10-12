#!/usr/bin/env python3
"""Freeze Q1480's mask schedule, two points, binary, and measurement code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1479 = PARENT / "q20261011_n83_distinct_roots"
Q1472 = PARENT / "q20261011_wdsat_phase_restart"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior = json.loads((Q1479 / "freeze.json").read_text())
    build = json.loads((Q1479 / "build_receipt.json").read_text())
    phases = json.loads((Q1472 / "freeze.json").read_text())["phase_schedule"]
    assert list(map(int, phases)) == protocol["polarity_phases"]
    assert [prior["inputs"][n]["workload_id"] for n in ("selected", "holdout")] == protocol[
        "workload_ids"]
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    for name in ("selected", "holdout"):
        item = prior["inputs"][name]
        for key in ("derived", "source", "target"):
            assert sha(Path(item[f"{key}_path"])) == item[f"{key}_sha256"]
    frozen = {"proposal_id": "Q1480", "candidate_id": None, "run_id": None,
              "files_sha256": {n: sha(HERE / n) for n in
                               ("protocol.json", "freeze.py", "run.py",
                                "analyze.py", "validate.py")},
              "q1479_freeze_sha256": sha(Q1479 / "freeze.json"),
              "q1479_build_sha256": sha(Q1479 / "build_receipt.json"),
              "q1479_analyze_source_sha256": sha(Q1479 / "analyze.py"),
              "q1479_binary_path": build["binary_path"],
              "q1479_binary_sha256": build["binary_sha256"],
              "q1472_freeze_sha256": sha(Q1472 / "freeze.json"),
              "q1472_phase_source_sha256": sha(Q1472 / "phase_schedule.py"),
              "phase_schedule": phases,
              "inputs": {n: prior["inputs"][n] for n in ("selected", "holdout")},
              "root_oracle_source_sha256": sha(PARENT / "s3_root_oracle.py"),
              "counted_onb_source_sha256": sha(
                  PARENT / "q20261011_operation_account/counted_onb.py"),
              "field_source_sha256": sha(PARENT.parent.parent /
                                         "ecc2k130/codegen/field.py")}
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1480 frozen", protocol["polarity_phases"])


if __name__ == "__main__":
    main()
