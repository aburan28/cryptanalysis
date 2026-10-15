#!/usr/bin/env python3
"""Freeze a same-fixture affine-layer tree versus XYZZ batch panel."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-batch-inversion-crossover-20261015"
OLD_REFERENCE = "/workspace/bench-sources/prime-j0-nearest-orbit-136531-native-batch"
REFERENCE = "/workspace/bench-sources/prime-j0-xyzz-batch-size-native"
CANDIDATE = "/workspace/bench-sources/prime-j0-affine-layer-native"
REFERENCE_FRONT = "4df1be9f9046774f1f8720e1ba8e4c379df559c7171b636221fa9f572ac03cc8"
REFERENCE_WINDOWS = "7272a3a818dac0fd38e028f91ba4bb75630a40849fc2375bdd0d14b20483ce62"
REFERENCE_BINARY = "c12828226c997b608cc2b6d407e9eaaedff9c38e89a94b24d5f0713d01a6645e"
CANDIDATE_FRONT = "f3c3b072af59b7835b3fd79b895202e22ad27f0cb4fff537a36aab4a13bcb60f"
CANDIDATE_WINDOWS = "cecb27d0fc425425607c7867ab4616d5c0bac7889d90b4ccfefaf2181be6d3fd"
CANDIDATE_BINARY = "cfb4b98679b6f8030f841b44e3dfb5132a403301238ee31285752249c5b99cd7"


def freeze():
    plan = json.loads((PARENT / "tier1-size2-manifest.json").read_text())
    rules = json.loads((PARENT / "tier1-size2-rules.json").read_text())
    rules.update({
        "purpose": "same-point 128-output affine-layer batch tree versus XYZZ final-only batch inversion",
        "batch_law": "128 frozen independent scalar outputs and 96 passes per arm; candidate batch-inverts affine pair denominators at each of four tree layers, reference batch-inverts final XYZZ ZZZ values",
        "timing_boundary": "Rust Instant times 96 passes over the same 128 frozen scalar multiplications and affine recovery after table preparation. Both variants verify all 12288 outputs outside the interval. This is batch throughput.",
        "arm_order": "A/A XYZZ batch, comparison, A/A XYZZ batch; runner alternates reference/candidate order",
        "reference_front_source_sha256": REFERENCE_FRONT,
        "reference_windows_source_sha256": REFERENCE_WINDOWS,
        "reference_binary_sha256": REFERENCE_BINARY,
        "candidate_front_source_sha256": CANDIDATE_FRONT,
        "candidate_windows_source_sha256": CANDIDATE_WINDOWS,
        "candidate_binary_sha256": CANDIDATE_BINARY,
        "comparison_acceptance": "all 16 comparison pairs valid, both adjacent A/A gates pass, paired bootstrap95 log-ratio interval entirely above or below one",
    })
    rules.pop("reference_source_sha256",None)
    (HERE / "tier1-affine-rules.json").write_text(json.dumps(rules,sort_keys=True,indent=2)+"\n")
    reference = [f"{REFERENCE}/target/release/eisenstein_fixed",
                 "--benchmark-split-prime-batch-inverse-size", "128", "96"]
    candidate = [f"{CANDIDATE}/target/release/eisenstein_fixed",
                 "--benchmark-split-prime-affine-layer", "128", "96"]
    for case in plan["cases"]:
        case["reference"] = reference
        case["candidate"] = candidate if case["id"] == "compare" else reference
    plan["artifacts"] = [path for path in plan["artifacts"]
                         if not path.startswith(f"{OLD_REFERENCE}/")
                         and not path.endswith("/tier1-size2-rules.json")]
    plan["artifacts"] += [
        f"{CANDIDATE}/Cargo.lock",f"{CANDIDATE}/Cargo.toml",
        f"{CANDIDATE}/src/bin/eisenstein_fixed.rs",
        f"{CANDIDATE}/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
        f"{CANDIDATE}/src/bin/mixed640_bench_fixture.json",
        f"{CANDIDATE}/native_affine_layer_overlay.py",
        f"{CANDIDATE}/linux-test.log",f"{CANDIDATE}/linux-build.log",
        f"{CANDIDATE}/affine-layer-screen.stdout",
        f"{CANDIDATE}/affine-layer-screen.stderr",
        f"{CANDIDATE}/target/release/eisenstein_fixed",
        "/workspace/isolated-bench/panels/tier1-affine-rules.json",
    ]
    plan["artifacts"] = sorted(set(plan["artifacts"]))
    plan["measurement_boundary"] = rules["timing_boundary"]
    (HERE / "tier1-affine-manifest.json").write_text(json.dumps(plan,sort_keys=True,indent=2)+"\n")


if __name__ == "__main__":
    freeze()
