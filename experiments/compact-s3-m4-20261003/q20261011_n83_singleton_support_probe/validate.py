#!/usr/bin/env python3
"""Replay the Q1484 source patch and check frozen ordinary point receipts."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1483 = HERE.parent / "q20261011_n83_two_root_support"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    assert protocol["proposal_id"] == frozen["proposal_id"] == "Q1484"
    assert build["proposal_id"] == drive["proposal_id"] == analysis["proposal_id"] == "Q1484"
    assert all(x["candidate_id"] is None for x in (protocol, frozen, build,
                                                     drive, analysis))
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest, name
    assert sha(Q1483 / "freeze.json") == frozen["q1483_freeze_sha256"]
    assert sha(Q1483 / "build_receipt.json") == frozen["q1483_build_sha256"]
    assert sha(Path(frozen["parent_source_path"])) == frozen[
        "parent_source_sha256"]
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert sha(Path(build["patched_source_path"])) == build[
        "patched_wdsat_c_sha256"]
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    spec = importlib.util.spec_from_file_location("q1484_patch", HERE / "build.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="q1484_replay_",
                                     dir="/Volumes/SSD990/llm/tmp") as temp:
        source = Path(temp)
        shutil.copy2(frozen["parent_source_path"], source / "wdsat.c")
        assert module.patch(source) == build["patched_wdsat_c_sha256"]
    subprocess.run(["python3", str(Q1483 / "validate.py")], check=True,
                   capture_output=True)
    assert analysis["freeze_sha256"] == drive["freeze_sha256"] == sha(
        HERE / "freeze.json")
    assert analysis["drive_sha256"] == sha(HERE / "drive_receipt.json")
    for name in ("selected", "holdout"):
        prior = Q1483 / "runs" / f"{name}_phase4" / "receipt.json"
        current = HERE / "runs" / f"{name}_phase4"
        row = json.loads((current / "receipt.json").read_text())
        point = analysis["points"][name]
        assert sha(prior) == frozen["q1483_phase4_receipts_sha256"][name]
        assert sha(prior) == point["baseline_receipt_sha256"]
        assert sha(current / "receipt.json") == point["receipt_sha256"]
        assert row["status"] == point["status"] == "CHECKPOINT_TERMINATED"
        assert row["workload_id"] == point["workload_id"]
        assert sha(current / "solver.stdout.txt") == row["stdout_sha256"]
        assert sha(current / "solver.stderr.txt") == row["stderr_sha256"]
        assert point["combined_cnf_xor_calls_at_cap"] == point[
            "baseline_combined_cnf_xor_calls_at_cap"]
        assert row["binary_sha256"] == build["binary_sha256"]
    assert drive["new_ordinary_attempts"] == 2
    assert analysis["complete_n131_solve_work_log2"] is None
    print("PASS Q1484", {n: analysis["points"][n][
        "singleton_with_undefined_middle_bits_at_cap"] for n in
        ("selected", "holdout")})


if __name__ == "__main__":
    main()
