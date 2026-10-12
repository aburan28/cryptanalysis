#!/usr/bin/env python3
"""Replay Q1490 source and verify every frozen sweep and holdout receipt."""
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
Q1489 = HERE.parent / "q20261012_n83_root_domain_branch"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    samples = json.loads((HERE / "root_samples.json").read_text())
    assert all(x["proposal_id"] == "Q1490" for x in
               (protocol, frozen, build, drive, analysis))
    assert all(x["candidate_id"] is None for x in
               (protocol, frozen, build, drive, analysis))
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest, name
    assert sha(Q1489 / "freeze.json") == frozen["q1489_freeze_sha256"]
    assert sha(Q1489 / "build_receipt.json") == frozen["q1489_build_sha256"]
    assert sha(Q1489 / "analyze.py") == frozen["q1489_analysis_source_sha256"]
    assert sha(Path(frozen["parent_source_path"])) == frozen[
        "parent_source_sha256"]
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert sha(Path(build["patched_source_path"])) == build[
        "patched_wdsat_c_sha256"]
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    spec = importlib.util.spec_from_file_location("q1490_sweep", HERE / "sweep.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="q1490_replay_",
                                     dir="/Volumes/SSD990/llm/tmp") as temp:
        source = Path(temp)
        shutil.copy2(frozen["parent_source_path"], source / "wdsat.c")
        assert module.patch(source, frozen["differing_positions"]) == build[
            "patched_wdsat_c_sha256"]
    subprocess.run(["python3", str(Q1489 / "validate.py")], check=True,
                   capture_output=True)
    assert analysis["analysis_source_sha256"] == sha(HERE / "sweep.py")
    assert analysis["freeze_sha256"] == drive["freeze_sha256"] == sha(
        HERE / "freeze.json")
    assert analysis["drive_sha256"] == sha(HERE / "drive_receipt.json")
    assert analysis["root_samples_sha256"] == sha(HERE / "root_samples.json")
    ids = frozen["selected_variants"]
    assert drive["selected_variants"] == ids
    assert len(ids) == len(frozen["differing_positions"]) == 34
    assert len(drive["rows"]) == drive["new_ordinary_attempts"]
    assert len(drive["rows"]) == len(ids) + len(drive["promoted_variants"])
    assert len(drive["promoted_variants"]) <= 3
    assert [r["variant"] for r in drive["rows"] if r["input"] == "selected"] == ids
    assert [r["variant"] for r in drive["rows"] if r["input"] == "holdout"] == (
        drive["promoted_variants"])
    selected = []
    for item in drive["rows"]:
        name, variant = item["input"], item["variant"]
        folder = HERE / "runs" / f"{name}_{variant}"
        row = json.loads((folder / "receipt.json").read_text())
        point = analysis["points"][f"{name}_{variant}"]
        assert row["input"] == name and row["variant"] == variant
        assert row["status"] == item["status"] == point["status"]
        assert row["workload_id"] == frozen["inputs"][name]["workload_id"]
        assert row["bit_index"] == frozen["variants"][variant]["position"]
        assert point["bit_index"] == row["bit_index"]
        assert sha(folder / "receipt.json") == item["receipt_sha256"]
        assert point["receipt_sha256"] == item["receipt_sha256"]
        assert sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert row["binary_sha256"] == build["binary_sha256"]
        assert row["freeze_sha256"] == sha(HERE / "freeze.json")
        log = (folder / "solver.stderr.txt").read_text()
        assert len(re.findall(r"^Q1490_BIT ", log, re.M)) == (
            1 if row["marker_ok"] else 0)
        assert len(samples[f"{name}_{variant}"]) == row["sampled_pair1_count"]
        assert sum(point["sampled_root_count_distribution"].values()) == (
            row["sampled_pair1_count"])
        assert all(x["leaf0_weight"] == x["leaf1_weight"] == 5 for x in
                   samples[f"{name}_{variant}"])
        if row["status"] == "CHECKPOINT_TERMINATED":
            assert row["work_at_cap"] is not None
            assert row["distinct_summary_at_cap"] is not None
            assert point["combined_cnf_xor_calls_at_cap"] == (
                row["work_at_cap"][1] + row["work_at_cap"][2])
            assert point["distinct_pair1_count_at_cap"] == (
                row["distinct_summary_at_cap"][1])
            assert row["distinct_summary_at_cap"][1] == row["sampled_pair1_count"]
            if name == "selected":
                selected.append(row)
        else:
            assert point["combined_cnf_xor_calls_at_cap"] is None
    ordered = sorted(selected, key=lambda r: (
        -r["distinct_summary_at_cap"][1],
        r["work_at_cap"][1] + r["work_at_cap"][2], r["bit_index"]))
    assert [r["variant"] for r in ordered[:3]] == drive["promoted_variants"]
    assert drive["selection_eligible_count"] == len(selected)
    assert analysis["complete_n131_solve_work_log2"] is None
    print("PASS Q1490", drive["promoted_variants"], len(drive["rows"]))


if __name__ == "__main__":
    main()
