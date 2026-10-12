#!/usr/bin/env python3
"""Freeze source, two ordinary points, and a satisfiable control before runs."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1473 = PARENT / "q20261011_selector_polarity"
Q1472 = PARENT / "q20261011_wdsat_phase_restart"
Q1476 = PARENT / "q20261011_n83_selector_holdout"
Q1419 = PARENT / "q1419_partial_pin/runs/n83_full_lock"
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_record(name: str, folder: Path, source: Path, target: Path) -> dict:
    out = {"derived_path": str(folder / "width4.xcnf.gz"),
           "source_path": str(source), "target_path": str(target)}
    for key in ("derived", "source", "target"):
        p = Path(out[f"{key}_path"])
        out[f"{key}_sha256"] = sha(p)
        if key != "target":
            out[f"{key}_raw_sha256"] = hashlib.sha256(
                gzip.decompress(p.read_bytes())).hexdigest()
    out["workload_id"] = json.loads(target.read_text())["workload_id"]
    return out


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    prior = json.loads((Q1473 / "build_receipt.json").read_text())
    source = Path("/Volumes/SSD990/llm/tmp/q1473_wdsat_build/n83/src")
    assert source.exists()
    assert sha(source / "wdsat.c") == prior["selector_patch"]["wdsat_c_sha256"]
    assert sha(source / "config.h") == prior["config_sha256"]
    selected = input_record("selected", Q1472, Q1472 / "original.xcnf.gz",
                            Q1472 / "target.json")
    holdout = input_record("holdout", Q1476, Q1476 / "original.xcnf.gz",
                           Q1476 / "target.json")
    assert [selected["workload_id"], holdout["workload_id"]] == protocol[
        "workload_ids"]
    for row in (selected, holdout):
        target = json.loads(Path(row["target_path"]).read_text())
        assert target["curve_id"] == protocol["curve_id"]
        assert target["factor_base_actual_B"] == protocol["factor_base_actual_B"]
        assert target["factor_base_folded_columns_K"] == protocol[
            "factor_base_folded_columns_K"]
        assert row["derived_sha256"] == target["derived_archive_sha256"]
        assert row["source_sha256"] == target["original_archive_sha256"]
    control = {"derived_path": str(Q1460 / "n83_full_lock.xcnf.gz"),
               "source_path": str(Q1419 / "system.xcnf.gz"),
               "workload_id": "927a1b51a942"}
    for key in ("derived", "source"):
        p = Path(control[f"{key}_path"])
        control[f"{key}_sha256"] = sha(p)
        control[f"{key}_raw_sha256"] = hashlib.sha256(
            gzip.decompress(p.read_bytes())).hexdigest()
    frozen = {"proposal_id": "Q1478", "candidate_id": None,
              "run_id": None,
              "files_sha256": {name: sha(HERE / name) for name in
                               ("protocol.json", "build.py", "freeze.py",
                                "run.py", "validate.py")},
              "q1473_build_sha256": sha(Q1473 / "build_receipt.json"),
              "q1473_smoke_sha256": sha(Q1473 / "smoke_receipt.json"),
              "parent_source_dir": str(source),
              "parent_wdsat_c_sha256": sha(source / "wdsat.c"),
              "parent_config_sha256": sha(source / "config.h"),
              "inputs": {"control": control, "selected": selected,
                         "holdout": holdout}}
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1478 frozen", selected["workload_id"], holdout["workload_id"])


if __name__ == "__main__":
    main()
