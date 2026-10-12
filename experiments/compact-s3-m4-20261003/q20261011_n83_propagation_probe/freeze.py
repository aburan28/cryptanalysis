#!/usr/bin/env python3
"""Freeze the exact Q1473 binary, target, inputs, and Q1474 scripts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1473 = HERE.parent / "q20261011_selector_polarity"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "freeze.json"
    assert not output.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior = json.loads((Q1473 / "freeze.json").read_text())
    build = json.loads((Q1473 / "build_receipt.json").read_text())
    smoke = json.loads((Q1473 / "smoke_receipt.json").read_text())
    target = json.loads((Q1473 / "target.json").read_text())
    assert smoke["status"] == "PASS" and len(smoke["rows"]) == 4
    assert all(row["status"] == "SAT_REPLAYED_XCNF" for row in smoke["rows"])
    assert smoke["binary_sha256"] == build["binary_sha256"]
    assert protocol["workload_id"] == target["workload_id"]
    assert protocol["curve_id"] == target["curve_id"]
    assert protocol["factor_base_actual_B"] == target["factor_base_actual_B"]
    assert protocol["factor_base_folded_columns_K"] == target["factor_base_folded_columns_K"]
    assert protocol["isogeny"] == target["isogeny"] == "none"
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    cell = prior["cells"]["ordinary"]
    for key in ("derived", "source"):
        assert sha(Path(cell[f"{key}_archive_path"])) == cell[f"{key}_archive_sha256"]
    files = {name: sha(HERE / name) for name in
             ("protocol.json", "freeze.py", "run.py", "validate.py")}
    frozen = {
        "proposal_id": "Q1474", "candidate_id": None, "run_id": None,
        "files_sha256": files,
        "q1473_freeze_sha256": sha(Q1473 / "freeze.json"),
        "q1473_build_sha256": sha(Q1473 / "build_receipt.json"),
        "q1473_smoke_sha256": sha(Q1473 / "smoke_receipt.json"),
        "q1473_target_sha256": sha(Q1473 / "target.json"),
        "binary_path": build["binary_path"],
        "binary_sha256": build["binary_sha256"],
        "ordinary_cell": cell,
        "phase_schedule": prior["phase_schedule"],
        "workload_id": protocol["workload_id"]}
    output.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print("Q1474 frozen", frozen["binary_sha256"][:12])


if __name__ == "__main__":
    main()
