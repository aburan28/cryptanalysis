#!/usr/bin/env python3
"""Freeze pinned WDSat source and exact Q1419 S3 formula inputs."""
from __future__ import annotations
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
UPSTREAM = Path("/private/tmp/wdsat-q1458")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    commit = subprocess.check_output(["git","rev-parse","HEAD"],cwd=UPSTREAM,text=True).strip()
    assert commit == protocol["upstream_solver"]["commit"]
    assert not subprocess.check_output(["git","status","--porcelain"],cwd=UPSTREAM).strip()
    cells = {}
    for name in protocol["cells"]:
        degree = "n53" if name.startswith("n53") else "n83"
        run = PARENT / "q1419_partial_pin/runs" / name
        receipt_file = run / "receipt.json"
        receipt = json.loads(receipt_file.read_text())
        archive = run / "system.xcnf.gz"
        raw = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == receipt["formula_raw_sha256"]
        assert sha(archive) == receipt["formula_archive_sha256"]
        base = protocol["curve_and_base"][degree]
        assert receipt["curve_id"] == base["curve_id"]
        assert receipt["factor_base_actual_B"] == base["factor_base_actual_B"]
        assert receipt["folded_columns_K"] == base["factor_base_folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == base["factor_base_enumerated_set_sha256"]
        assert receipt["isogeny"] == "none"
        cells[name] = {"curve_id":receipt["curve_id"],
                       "workload_id":receipt["workload_id"],
                       "stage_config_id":receipt["stage_config_id"],
                       "receipt_sha256":sha(receipt_file),
                       "formula_archive_sha256":sha(archive),
                       "formula_raw_sha256":receipt["formula_raw_sha256"],
                       "formula":receipt["formula"],
                       "prior_solver_status":receipt["solver_status"]}
    output={"proposal_id":"Q1458","candidate_id":None,"run_id":None,
            "protocol_sha256":sha(HERE / "protocol.json"),
            "freeze_source_sha256":sha(Path(__file__)),
            "build_source_sha256":sha(HERE / "build.py"),
            "upstream_commit":commit,
            "upstream_tree_sha256":subprocess.check_output(
                ["git","rev-parse","HEAD^{tree}"],cwd=UPSTREAM,text=True).strip(),
            "cells":cells}
    (HERE / "freeze.json").write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print("FROZEN Q1458",commit,len(cells))


if __name__=="__main__":main()
