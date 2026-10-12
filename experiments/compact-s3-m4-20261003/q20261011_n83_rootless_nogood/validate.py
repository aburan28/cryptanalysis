#!/usr/bin/env python3
"""Validate Q1482's exact nogood proof, patched solver, and two raw runs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q20261011_n83_leaf_masks"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT.parent.parent / "ecc2k130/codegen"))
from chain_s3 import evaluate_s3  # noqa: E402
from field import Onb  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    samples_path = HERE / "root_samples.json"
    samples = json.loads(samples_path.read_text())
    assert {protocol["proposal_id"], frozen["proposal_id"], build["proposal_id"],
            drive["proposal_id"], analysis["proposal_id"]} == {"Q1482"}
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert sha(Q1481 / "root_samples.json") == frozen[
        "q1481_root_samples_sha256"]
    assert sha(Q1481 / "build_receipt.json") == frozen["q1481_build_sha256"]
    assert build["freeze_sha256"] == drive["freeze_sha256"] == analysis[
        "freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["source_sha256"] == sha(HERE / "build.py")
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert sha(HERE / "build.stdout.txt") == build["build_stdout_sha256"]
    assert sha(HERE / "build.stderr.txt") == build["build_stderr_sha256"]
    assert sha(samples_path) == analysis["root_samples_sha256"]
    assert sha(HERE / "drive_receipt.json") == analysis["drive_sha256"]
    assert sha(HERE / "analyze.py") == analysis["analysis_source_sha256"]
    bits = frozen["rootless_pair1_bits"]
    assert len(bits) == 166 and bits[:83].count("1") == bits[83:].count("1") == 5
    onb = Onb(83)
    a = onb.fromCoords(int(bits[:83][::-1], 2))
    b = onb.fromCoords(int(bits[83:][::-1], 2))
    assert a and b and not s3_roots(onb, a, b)
    parent_samples = json.loads((Q1481 / "root_samples.json").read_text())
    assert bits == parent_samples["selected_phase4"][0]["leaf_bits"] == parent_samples[
        "holdout_phase4"][0]["leaf_bits"]
    spec = importlib.util.spec_from_file_location("q1482_build_replay",
                                                  HERE / "build.py")
    assert spec is not None and spec.loader is not None
    patcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patcher)
    with tempfile.TemporaryDirectory(prefix="q1482_replay_",
                                     dir="/Volumes/SSD990/llm/tmp") as temp:
        source = Path(temp)
        shutil.copy2(Path(frozen["parent_source_dir"]) / "wdsat.c",
                     source / "wdsat.c")
        assert patcher.patch(source, bits) == build["patched_wdsat_c_sha256"]
    assert [(r["input"], r["phase"]) for r in drive["rows"]] == [
        ("selected", 4), ("holdout", 4)]
    assert drive["new_ordinary_attempts"] == 2
    for item in drive["rows"]:
        name = item["input"]
        folder = HERE / "runs" / f"{name}_phase4"
        row_path = folder / "receipt.json"
        assert sha(row_path) == item["receipt_sha256"]
        row = json.loads(row_path.read_text())
        assert row["status"] == item["status"] == "CHECKPOINT_TERMINATED"
        assert row["binary_sha256"] == build["binary_sha256"]
        assert row["workload_id"] == frozen["inputs"][name]["workload_id"]
        assert row["freeze_sha256"] == sha(HERE / "freeze.json")
        stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        assert sha(stdout) == row["stdout_sha256"] and sha(stderr) == row[
            "stderr_sha256"]
        assert stdout.stat().st_size == 0
        log = stderr.read_text()
        assert log.splitlines().count("Q1472_PHASE 0 0") == 1
        assert log.splitlines().count("Q1473_SELECTOR_PHASE 0 2140 2141") == 1
        assert log.splitlines().count(
            f"Q1481_MASK 4 {len(frozen['mask_schedule']['4']['flip_ids'])}") == 1
        assert row["branch_lower_bound"] == protocol["branch_checkpoint"]
        nogood = [tuple(map(int, value)) for value in re.findall(
            r"^Q1482_NOGOOD (\d+) (\d+) (\d+) (\d+)$", log, re.M)]
        assert [v[0] for v in nogood] == [1 << i for i in range(len(nogood))]
        at_cap = next(v for v in nogood if v[0] == protocol["branch_checkpoint"])
        assert all(v[1] <= w[1] and v[2] <= w[2] and v[3] <= w[3]
                   for v, w in zip(nogood, nogood[1:]))
        assert 0 <= at_cap[3] <= at_cap[1] <= at_cap[2]
        assert at_cap[1:] == (
            analysis["points"][name]["nogood_checks_at_cap"],
            analysis["points"][name]["nogood_bit_tests_at_cap"],
            analysis["points"][name]["nogood_rejections_at_cap"])
        found = [value for _, value in re.findall(
            r"^Q1479_PAIR1 (\d+) ([01]{166})$", log, re.M)]
        assert found == [r["leaf_bits"] for r in samples[name]]
        assert len(set(found)) == len(found)
        for item in samples[name]:
            raw = item["leaf_bits"]
            x = onb.fromCoords(int(raw[:83][::-1], 2))
            y = onb.fromCoords(int(raw[83:][::-1], 2))
            assert item["root_count"] == len(item["root_coords"])
            for value in item["root_coords"]:
                assert evaluate_s3(onb, x, y, onb.fromCoords(value)) == 0
        baseline_path = Q1481 / "runs" / f"{name}_phase4" / "receipt.json"
        assert sha(baseline_path) == frozen["q1481_phase4_receipts_sha256"][name]
        base = json.loads(baseline_path.read_text())
        assert (analysis["points"][name]["baseline_combined_cnf_xor_calls_at_cap"] ==
                base["work_at_cap"][1] + base["work_at_cap"][2])
    print("PASS Q1482", {name: analysis["points"][name][
        "nogood_rejections_at_cap"] for name in ("selected", "holdout")})


if __name__ == "__main__":
    main()
