#!/usr/bin/env python3
"""Freeze width-three equivalence and Q1464 matched inputs before timing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1464 = PARENT / "q20261011_wdsat_workprobe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    equivalence = json.loads((HERE / "equivalence_check.json").read_text())
    q1464_freeze = json.loads((Q1464 / "freeze.json").read_text())
    q1464_verification = json.loads((Q1464 / "verification.json").read_text())
    assert protocol["proposal_id"] == prepared["proposal_id"] == equivalence["proposal_id"] == "Q1465"
    assert protocol["candidate_id"] is protocol["run_id"] is prepared["candidate_id"] is None
    assert equivalence["status"] == q1464_verification["status"] == "PASS"
    assert len(q1464_verification["runs"]) == 8
    assert equivalence["transform_source_sha256"] == sha(HERE / "prepare.py")
    cells = {}
    for degree in (53, 83):
        name = f"n{degree}"
        parent = q1464_freeze["cells"][name]
        for kind in ("full_lock", "ordinary"):
            cell = f"{name}_{kind}"
            item = prepared["cells"][cell]
            archive = HERE / f"{cell}.xcnf.gz"
            assert sha(archive) == item["derived_archive_sha256"]
            parent_source_key = "ordinary_source_archive_sha256" if kind == "ordinary" else "control_source_archive_sha256"
            assert item["source_archive_sha256"] == parent[parent_source_key]
            cells[cell] = {"curve_id": parent["curve_id"],
                           "kind": kind, "degree": degree,
                           "workload_id": parent["ordinary_workload_id"] if kind == "ordinary" else None,
                           "factor_base_actual_B": parent["factor_base_actual_B"],
                           "factor_base_folded_columns_K": parent["factor_base_folded_columns_K"],
                           "factor_base_enumerated_set_sha256": parent["factor_base_enumerated_set_sha256"],
                           "public_target": parent["public_target"] if kind == "ordinary" else None,
                           "source_archive_sha256": item["source_archive_sha256"],
                           "derived_archive_sha256": item["derived_archive_sha256"],
                           "derived_raw_sha256": item["derived_raw_sha256"],
                           "derived_variables": item["stats"]["derived_variables"],
                           "original_variables": item["stats"]["original_variables"]}
    output = {"proposal_id": "Q1465", "candidate_id": None,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "freeze_source_sha256": sha(Path(__file__)),
              "prepare_source_sha256": sha(HERE / "prepare.py"),
              "prepare_receipt_sha256": sha(HERE / "prepare_receipt.json"),
              "equivalence_source_sha256": sha(HERE / "check_equivalence.py"),
              "equivalence_check_sha256": sha(HERE / "equivalence_check.json"),
              "build_source_sha256": sha(HERE / "build.py"),
              "q1460_build_source_sha256": sha(PARENT / "q20261011_wdsat_shared_prefix/build.py"),
              "q1464_build_source_sha256": sha(Q1464 / "build.py"),
              "q1464_freeze_sha256": sha(Q1464 / "freeze.json"),
              "q1464_verification_sha256": sha(Q1464 / "verification.json"),
              "upstream_commit": protocol["solver"]["upstream_commit"],
              "cells": cells}
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1465 frozen", len(cells), "cells")


if __name__ == "__main__":
    main()
