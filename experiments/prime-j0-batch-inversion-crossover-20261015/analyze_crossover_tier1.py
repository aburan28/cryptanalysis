#!/usr/bin/env python3
"""Independently audit both frozen size-one/size-two Tier 1 panels."""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-variable-orbit-radix-20261014" / "analyze_tier1.py"
spec = importlib.util.spec_from_file_location("radix_tier1_audit", PARENT)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)
auditor.HERE = HERE
JOBS = {
    1: "44ccef44e8284befa166b3106b1542c2",
    2: "6efe4e5453914fcf9c25ca78ae0d1f04",
}


def audit_size(size):
    job = JOBS[size]
    rules_name = f"tier1-size{size}-rules.json"
    manifest_name = f"tier1-size{size}-manifest.json"
    auditor.PANELS = {96: (job, rules_name, manifest_name)}
    result = auditor.audit(96)
    folder = HERE / job
    rows = auditor.lines(folder / "runs.jsonl")
    compared = [row for row in rows if row["case"] == "compare" and row["variant"] == "candidate"]
    assert len(compared) == 16
    assert all(row["fields"].get("batch_size") == str(size) for row in compared)
    rules = auditor.load(HERE / rules_name)
    summary = auditor.load(folder / "summary.json")
    stem = "/workspace/bench-sources/prime-j0-xyzz-batch-size-native"
    assert summary["artifact_sha256"][f"{stem}/src/bin/eisenstein_fixed.rs"] == rules["candidate_front_source_sha256"]
    assert summary["artifact_sha256"][f"{stem}/src/bin/eisenstein_fixed/unit_orbit_windows.rs"] == rules["candidate_windows_source_sha256"]
    assert summary["artifact_sha256"][f"{stem}/target/release/eisenstein_fixed"] == rules["candidate_binary_sha256"]
    result["batch_size"] = size
    result["inversions_per_128_output_pass"] = 128 // size
    result["ratio_definition"] = "reference individual-inversion online wall time / candidate XYZZ chunk-inversion online wall time"
    return result


if __name__ == "__main__":
    print(json.dumps({str(size): audit_size(size) for size in (1, 2)}, sort_keys=True, indent=2))
