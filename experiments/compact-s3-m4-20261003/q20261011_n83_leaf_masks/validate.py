#!/usr/bin/env python3
"""Validate Q1481's frozen mask grid, exact logs, root samples, and rankings."""
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
Q1479 = PARENT / "q20261011_n83_distinct_roots"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT.parent.parent / "ecc2k130/codegen"))
from chain_s3 import evaluate_s3  # noqa: E402
from field import Onb  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def root_count(onb: Onb, a: int, b: int) -> int:
    if not a and not b:
        return 0
    if not a or not b or a == b:
        return 1
    ab = onb.mul(a, b)
    total_sq = onb.sqr(onb.add(a, b))
    constant = onb.add(onb.sqr(ab), onb.one())
    rhs = onb.mul(onb.mul(total_sq, constant), onb.sqr(onb.inv(ab)))
    return 0 if onb.trace(rhs) else 2


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    analysis = json.loads((HERE / "analysis.json").read_text())
    sample_path = HERE / "root_samples.json"
    samples = json.loads(sample_path.read_text())
    assert {protocol["proposal_id"], frozen["proposal_id"], drive["proposal_id"],
            analysis["proposal_id"]} == {"Q1481"}
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert sha(Q1479 / "build_receipt.json") == frozen["q1479_build_sha256"]
    assert sha(Q1479 / "analyze.py") == frozen["q1479_analyze_source_sha256"]
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert build["source_sha256"] == sha(HERE / "build.py")
    assert sha(HERE / "mask_schedule.json") == frozen["mask_schedule_sha256"]
    spec = importlib.util.spec_from_file_location("q1481_build_replay", HERE / "build.py")
    assert spec is not None and spec.loader is not None
    patcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patcher)
    with tempfile.TemporaryDirectory(prefix="q1481_replay_",
                                     dir="/Volumes/SSD990/llm/tmp") as temp:
        path = Path(temp)
        shutil.copy2(Path(frozen["parent_source_dir"]) / "wdsat.c",
                     path / "wdsat.c")
        assert patcher.patch(path, frozen["mask_schedule"]) == build[
            "patched_wdsat_c_sha256"]
    assert sha(HERE / "freeze.json") == drive["freeze_sha256"] == analysis[
        "freeze_sha256"]
    assert sha(HERE / "drive_receipt.json") == analysis["drive_sha256"]
    assert sha(HERE / "analyze.py") == analysis["analysis_source_sha256"]
    assert sha(sample_path) == analysis["root_samples_sha256"]
    assert len(drive["rows"]) == drive["new_ordinary_attempts"]
    onb = Onb(83)
    for item in drive["rows"]:
        name, phase = item["input"], item["phase"]
        assert name in ("selected", "holdout") and phase in protocol[
            "polarity_phases"]
        folder = HERE / "runs" / f"{name}_phase{phase}"
        row_path = folder / "receipt.json"
        assert sha(row_path) == item["receipt_sha256"]
        row = json.loads(row_path.read_text())
        assert row["status"] == item["status"]
        assert row["workload_id"] == frozen["inputs"][name]["workload_id"]
        assert row["input_sha256"] == frozen["inputs"][name]["derived_sha256"]
        assert row["binary_sha256"] == build["binary_sha256"]
        assert row["freeze_sha256"] == sha(HERE / "freeze.json")
        stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        assert sha(stdout) == row["stdout_sha256"] and sha(stderr) == row[
            "stderr_sha256"]
        log = stderr.read_text()
        count = len(frozen["mask_schedule"][str(phase)]["flip_ids"])
        assert log.splitlines().count("Q1472_PHASE 0 0") == 1
        assert log.splitlines().count("Q1473_SELECTOR_PHASE 0 2140 2141") == 1
        assert log.splitlines().count(f"Q1481_MASK {phase} {count}") == 1
        assert log.splitlines().count("Q1469_ORDER q1478_leafpair_first 168") == 1
        observed = [bits for _, bits in re.findall(
            r"^Q1479_PAIR1 (\d+) ([01]{166})$", log, re.M)]
        sample_key = f"{name}_phase{phase}"
        assert observed == [r["leaf_bits"] for r in samples[sample_key]]
        assert len(set(observed)) == len(observed) == row["sampled_pair1_count"]
        if row["status"] == "CHECKPOINT_TERMINATED":
            assert row["branch_lower_bound"] == protocol["branch_checkpoint"]
            assert row["marker_ok"] and row["search_started"]
            assert row["distinct_summary_at_cap"][1] == len(observed)
            assert sum(row["distinct_summary_at_cap"][1:]) == row[
                "ready_at_cap"][4]
            assert stdout.stat().st_size == 0
        for sample in samples[sample_key]:
            bits = sample["leaf_bits"]
            a = onb.fromCoords(int(bits[:83][::-1], 2))
            b = onb.fromCoords(int(bits[83:][::-1], 2))
            assert sample["leaf0_weight"] == bits[:83].count("1") <= 5
            assert sample["leaf1_weight"] == bits[83:].count("1") <= 5
            assert sample["root_count"] == root_count(onb, a, b)
            for value in sample["root_coords"]:
                assert evaluate_s3(onb, a, b, onb.fromCoords(value)) == 0
        cell = next(c for c in analysis["cells"][name] if c["phase"] == phase)
        assert cell["receipt_sha256"] == sha(row_path)
        assert cell["rootless_pair_count_sampled"] == sum(
            r["root_count"] == 0 for r in samples[sample_key])
        assert cell["field_api_entries_sampled_root_queries"] == sum(
            r["field_api_entries"] for r in samples[sample_key])
        if phase == 0 and row["status"] == "CHECKPOINT_TERMINATED":
            prior = json.loads((Q1479 / "runs" /
                                f"{name}_q1478_leafpair_first" /
                                "receipt.json").read_text())
            assert row["ready_at_cap"] == prior["ready_checkpoints"][-1]
            assert row["work_at_cap"] == prior["work_checkpoints"][-1]
    for name, cells in analysis["cells"].items():
        completed = [c for c in cells if c["status"] == "CHECKPOINT_TERMINATED"]
        expected = [c["phase"] for c in sorted(
            completed, key=lambda c: (-c["rootless_per_million_combined_calls"],
                                      -c["distinct_per_million_combined_calls"],
                                      c["combined_propagation_calls_at_cap"],
                                      c["phase"]))]
        assert analysis["pointwise_phase_rankings"][name] == expected
    print("PASS Q1481", len(drive["rows"]), analysis["pointwise_phase_rankings"])


if __name__ == "__main__":
    main()
