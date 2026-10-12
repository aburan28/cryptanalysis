#!/usr/bin/env python3
"""Freeze leaf-only mask lists and exact solver/input sources before build."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1479 = PARENT / "q20261011_n83_distinct_roots"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior = json.loads((Q1479 / "freeze.json").read_text())
    parent_build = json.loads((Q1479 / "build_receipt.json").read_text())
    schedule = json.loads((HERE / "mask_schedule.json").read_text())
    spec = importlib.util.spec_from_file_location("q1481_schedule_for_freeze",
                                                  HERE / "mask_schedule.py")
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert schedule == generator.schedule()
    assert list(map(int, schedule)) == protocol["polarity_phases"]
    assert all(set(row["flip_ids"]) <= set(range(2, 334)) for row in
               schedule.values())
    assert [prior["inputs"][n]["workload_id"] for n in ("selected", "holdout")] == protocol[
        "workload_ids"]
    source = Path(parent_build["patched_source_path"]).parent
    assert sha(source / "wdsat.c") == parent_build["patched_wdsat_c_sha256"]
    assert sha(source / "config.h") == parent_build["config_sha256"]
    for name in ("selected", "holdout"):
        item = prior["inputs"][name]
        for key in ("derived", "source", "target"):
            assert sha(Path(item[f"{key}_path"])) == item[f"{key}_sha256"]
    frozen = {"proposal_id": "Q1481", "candidate_id": None, "run_id": None,
              "files_sha256": {n: sha(HERE / n) for n in
                               ("protocol.json", "mask_schedule.py", "freeze.py",
                                "build.py", "run.py", "analyze.py", "validate.py")},
              "mask_schedule_sha256": sha(HERE / "mask_schedule.json"),
              "mask_schedule": schedule,
              "q1479_freeze_sha256": sha(Q1479 / "freeze.json"),
              "q1479_build_sha256": sha(Q1479 / "build_receipt.json"),
              "q1479_analyze_source_sha256": sha(Q1479 / "analyze.py"),
              "parent_source_dir": str(source),
              "parent_wdsat_c_sha256": sha(source / "wdsat.c"),
              "parent_config_sha256": sha(source / "config.h"),
              "inputs": {n: prior["inputs"][n] for n in ("selected", "holdout")},
              "root_oracle_source_sha256": sha(PARENT / "s3_root_oracle.py"),
              "counted_onb_source_sha256": sha(
                  PARENT / "q20261011_operation_account/counted_onb.py"),
              "field_source_sha256": sha(PARENT.parent.parent /
                                         "ecc2k130/codegen/field.py")}
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1481 frozen", [len(schedule[str(i)]["flip_ids"])
                            for i in protocol["polarity_phases"]])


if __name__ == "__main__":
    main()
