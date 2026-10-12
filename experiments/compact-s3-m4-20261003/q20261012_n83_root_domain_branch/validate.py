#!/usr/bin/env python3
"""Replay Q1489 source and audit four paired N83 runs and exact roots."""
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
Q1485 = HERE.parent / "q20261011_n83_common_bit_probe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    samples = json.loads((HERE / "root_samples.json").read_text())
    assert all(x["proposal_id"] == "Q1489" for x in
               (protocol, frozen, build, drive, analysis))
    assert all(x["candidate_id"] is None for x in
               (protocol, frozen, build, drive, analysis))
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest, name
    assert sha(Q1485 / "freeze.json") == frozen["q1485_freeze_sha256"]
    assert sha(Q1485 / "build_receipt.json") == frozen["q1485_build_sha256"]
    assert sha(Path(frozen["parent_source_path"])) == frozen[
        "parent_source_sha256"]
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert sha(Path(build["patched_source_path"])) == build[
        "patched_wdsat_c_sha256"]
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    spec = importlib.util.spec_from_file_location("q1489_patch", HERE / "build.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="q1489_replay_",
                                     dir="/Volumes/SSD990/llm/tmp") as temp:
        source = Path(temp)
        shutil.copy2(frozen["parent_source_path"], source / "wdsat.c")
        assert module.patch(source, frozen["priority"],
                            frozen["root_discriminator_bit"]) == build[
                                "patched_wdsat_c_sha256"]
    subprocess.run(["python3", str(Q1485 / "validate.py")], check=True,
                   capture_output=True)
    assert analysis["analysis_source_sha256"] == sha(HERE / "analyze.py")
    assert analysis["freeze_sha256"] == drive["freeze_sha256"] == sha(
        HERE / "freeze.json")
    assert analysis["drive_sha256"] == sha(HERE / "drive_receipt.json")
    assert analysis["root_samples_sha256"] == sha(HERE / "root_samples.json")
    assert len(drive["rows"]) == drive["new_ordinary_attempts"] == 4
    assert [(r["input"], r["variant"]) for r in drive["rows"]] == [
        (name, variant) for name in ("selected", "holdout")
        for variant in ("order_only", "root_domain")]
    for item in drive["rows"]:
        name, variant = item["input"], item["variant"]
        key = f"{name}_{variant}"
        folder = HERE / "runs" / key
        row = json.loads((folder / "receipt.json").read_text())
        point = analysis["points"][key]
        assert row["status"] == item["status"] == point["status"]
        assert row["workload_id"] == frozen["inputs"][name]["workload_id"]
        assert row["variant"] == variant and row["phase"] == 4
        assert sha(folder / "receipt.json") == item["receipt_sha256"]
        assert point["receipt_sha256"] == item["receipt_sha256"]
        assert sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert row["binary_sha256"] == build["binary_sha256"]
        assert row["freeze_sha256"] == sha(HERE / "freeze.json")
        assert sha(Q1485 / "runs" / f"{name}_phase4" / "receipt.json") == frozen[
            "q1485_phase4_receipts_sha256"][name]
        log = (folder / "solver.stderr.txt").read_text()
        assert len(re.findall(r"^Q1489_DOMAIN [01]$", log, re.M)) == (
            1 if row["marker_ok"] else 0)
        assert len(samples[key]) == row["sampled_pair1_count"]
        assert sum(point["sampled_root_count_distribution"].values()) == len(
            samples[key])
        assert all(x["leaf0_weight"] == x["leaf1_weight"] == 5 for x in
                   samples[key])
        if row["status"] == "CHECKPOINT_TERMINATED":
            assert row["work_at_cap"] is not None
            assert point["combined_cnf_xor_calls_at_cap"] == (
                row["work_at_cap"][1] + row["work_at_cap"][2])
            assert point["distinct_pair1_count_at_cap"] == len(samples[key])
        else:
            assert point["combined_cnf_xor_calls_at_cap"] is None
    assert analysis["complete_n131_solve_work_log2"] is None
    print("PASS Q1489", {k: p["status"] for k, p in analysis["points"].items()})


if __name__ == "__main__":
    main()
