#!/usr/bin/env python3
"""Freeze Q1478 source/input identities before the distinct-pair run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1478 = HERE.parent / "q20261011_n83_leaf_exposure"
FIELD = HERE.parent.parent.parent / "ecc2k130/codegen/field.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior_build = json.loads((Q1478 / "build_receipt.json").read_text())
    prior_freeze = json.loads((Q1478 / "freeze.json").read_text())
    prior_drive = json.loads((Q1478 / "drive_receipt.json").read_text())
    assert protocol["proposal_id"] == "Q1479"
    assert [prior_freeze["inputs"][name]["workload_id"]
            for name in ("selected", "holdout")] == protocol["workload_ids"]
    assert prior_drive["new_ordinary_attempts"] == 4
    for name in ("selected", "holdout"):
        for key in ("derived", "source", "target"):
            item = prior_freeze["inputs"][name]
            assert sha(Path(item[f"{key}_path"])) == item[f"{key}_sha256"]
    source = Path(prior_build["patched_source_path"]).parent
    assert sha(source / "wdsat.c") == prior_build["patched_wdsat_c_sha256"]
    frozen = {"proposal_id": "Q1479", "candidate_id": None,
              "run_id": None,
              "files_sha256": {name: sha(HERE / name) for name in
                               ("protocol.json", "freeze.py", "build.py",
                                "run.py", "analyze.py", "validate.py")},
              "q1478_build_sha256": sha(Q1478 / "build_receipt.json"),
              "q1478_freeze_sha256": sha(Q1478 / "freeze.json"),
              "q1478_drive_sha256": sha(Q1478 / "drive_receipt.json"),
              "q1478_run_source_sha256": sha(Q1478 / "run.py"),
              "field_source_sha256": sha(FIELD),
              "s3_oracle_source_sha256": sha(HERE.parent / "s3_root_oracle.py"),
              "s3_polynomial_source_sha256": sha(HERE.parent / "chain_s3.py"),
              "counted_onb_source_sha256": sha(
                  HERE.parent / "q20261011_operation_account/counted_onb.py"),
              "parent_source_dir": str(source),
              "parent_wdsat_c_sha256": sha(source / "wdsat.c"),
              "parent_config_sha256": sha(source / "config.h"),
              "inputs": {name: prior_freeze["inputs"][name]
                         for name in ("selected", "holdout")}}
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1479 frozen", protocol["workload_ids"])


if __name__ == "__main__":
    main()
