#!/usr/bin/env python3
"""Audit the complete affine-layer versus XYZZ Tier 1 panel."""

import argparse
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
    "c24e37df66ad4b1a891f1805798a0887": ("tier1-affine-rules.json","tier1-affine-manifest.json"),
    "fe00f695389443f08d6cbf003f1a8b7e": ("tier1-affine-rules.json","tier1-affine-manifest.json"),
    "251bb8443cad471ab3e6162307fd0c46": ("tier1-affine-cpu40-rules.json","tier1-affine-cpu40-manifest.json"),
}


def audit(job):
    assert job in JOBS
    rules_name,manifest_name = JOBS[job]
    auditor.PANELS = {96: (job,rules_name,manifest_name)}
    result = auditor.audit(96)
    folder = HERE / job
    rules = auditor.load(HERE / rules_name)
    summary = auditor.load(folder / "summary.json")
    runs = auditor.lines(folder / "runs.jsonl")
    reference = "/workspace/bench-sources/prime-j0-xyzz-batch-size-native"
    candidate = "/workspace/bench-sources/prime-j0-affine-layer-native"
    artifacts = summary["artifact_sha256"]
    for prefix,tag in ((reference,"reference"),(candidate,"candidate")):
        assert artifacts[f"{prefix}/target/release/eisenstein_fixed"] == rules[f"{tag}_binary_sha256"]
        assert artifacts[f"{prefix}/src/bin/eisenstein_fixed.rs"] == rules[f"{tag}_front_source_sha256"]
        assert artifacts[f"{prefix}/src/bin/eisenstein_fixed/unit_orbit_windows.rs"] == rules[f"{tag}_windows_source_sha256"]
    for row in runs:
        if row["case"] == "compare":
            assert row["fields"].get("batch_size") == "128"
            if row["variant"] == "candidate":
                assert row["fields"].get("scheme") == "affine_layer_tree"
    result["ratio_definition"] = "XYZZ final-only batch online wall time / affine-layer batch online wall time"
    result["candidate_shared_inversion_rounds_per_full_batch"] = 4
    result["reference_shared_inversion_rounds_per_full_batch"] = 1
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job",choices=JOBS,default=next(iter(JOBS)))
    args = parser.parse_args()
    print(json.dumps(audit(args.job),sort_keys=True,indent=2))
