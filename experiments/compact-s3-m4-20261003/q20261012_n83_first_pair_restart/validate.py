#!/usr/bin/env python3
"""Replay Q1488 instrumentation and validate all first-pair receipts."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1481 = HERE.parent / "q20261011_n83_leaf_masks"
Q1479 = HERE.parent / "q20261011_n83_distinct_roots"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    samples = json.loads((HERE / "root_samples.json").read_text())
    older = json.loads((Q1481 / "root_samples.json").read_text())
    assert all(x["proposal_id"] == "Q1488" for x in
               (protocol, frozen, build, drive, analysis))
    assert all(x["candidate_id"] is None for x in
               (protocol, frozen, build, drive, analysis))
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest, name
    assert sha(Q1481 / "freeze.json") == frozen["q1481_freeze_sha256"]
    assert sha(Q1481 / "build_receipt.json") == frozen["q1481_build_sha256"]
    assert sha(Q1481 / "root_samples.json") == frozen["q1481_root_samples_sha256"]
    assert sha(Q1479 / "analyze.py") == frozen["q1479_analyze_source_sha256"]
    assert sha(Path(frozen["parent_source_path"])) == frozen[
        "parent_source_sha256"]
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert sha(Path(build["patched_source_path"])) == build[
        "patched_wdsat_c_sha256"]
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    spec = importlib.util.spec_from_file_location("q1488_first_pair", HERE / "first_pair.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="q1488_replay_",
                                     dir="/Volumes/SSD990/llm/tmp") as temp:
        source = Path(temp)
        shutil.copy2(frozen["parent_source_path"], source / "wdsat.c")
        assert module.patch(source) == build["patched_wdsat_c_sha256"]
    subprocess.run(["python3", str(Q1481 / "validate.py")], check=True,
                   capture_output=True)
    assert analysis["analysis_source_sha256"] == sha(HERE / "first_pair.py")
    assert analysis["freeze_sha256"] == drive["freeze_sha256"] == sha(
        HERE / "freeze.json")
    assert analysis["drive_sha256"] == sha(HERE / "drive_receipt.json")
    assert analysis["root_samples_sha256"] == sha(HERE / "root_samples.json")
    assert len(drive["rows"]) == drive["new_ordinary_attempts"] == 18
    assert [(r["input"], r["phase"]) for r in drive["rows"]] == [
        (n, i) for n in ("selected", "holdout") for i in range(9)]
    for item in drive["rows"]:
        name, phase = item["input"], item["phase"]
        key = f"{name}_phase{phase}"
        folder = HERE / "runs" / key
        row = json.loads((folder / "receipt.json").read_text())
        point = analysis["points"][key]
        assert row["status"] == item["status"] == point["status"]
        assert row["workload_id"] == frozen["inputs"][name]["workload_id"]
        assert row["flip_count"] == len(frozen["mask_schedule"][str(phase)]["flip_ids"])
        assert sha(folder / "receipt.json") == item["receipt_sha256"]
        assert point["receipt_sha256"] == item["receipt_sha256"]
        assert sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert row["binary_sha256"] == build["binary_sha256"]
        assert row["freeze_sha256"] == sha(HERE / "freeze.json")
        assert sha(Q1481 / "runs" / key / "receipt.json") == frozen[
            "q1481_phase_receipts_sha256"][key]
        log = (folder / "solver.stderr.txt").read_text()
        markers = re.findall(
            r"^Q1488_FIRST_PAIR (\d+) (\d+) (\d+) ([01]{166})$", log, re.M)
        assert len(markers) == (1 if row["marker_seen"] else 0)
        if row["status"] == "FIRST_PAIR_TERMINATED":
            assert row["marker_ok"] and row["search_started"]
            assert len(markers) == 1
            assert row["first_pair_branch"] == int(markers[0][0])
            assert row["first_pair_cnf_calls"] == int(markers[0][1])
            assert row["first_pair_xor_calls"] == int(markers[0][2])
            assert row["first_pair_bits"] == markers[0][3]
            assert row["first_pair_bits"] == older[key][0]["leaf_bits"]
            assert samples[key]["root_coords"] == older[key][0]["root_coords"]
            assert samples[key]["root_count"] == point["root_count"]
            assert point["first_pair_combined_calls"] == (
                row["first_pair_cnf_calls"] + row["first_pair_xor_calls"])
            assert 0 < point["first_pair_combined_calls"] <= point[
                "full_32768_branch_combined_calls"]
        else:
            assert point["first_pair_combined_calls"] is None
    assert analysis["selected_unique_pairs"] == 9
    assert analysis["complete_n131_solve_work_log2"] is None
    print("PASS Q1488", analysis["first_pair_completed_attempts"])


if __name__ == "__main__":
    main()
