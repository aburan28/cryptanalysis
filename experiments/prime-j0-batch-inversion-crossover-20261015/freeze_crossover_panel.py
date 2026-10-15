#!/usr/bin/env python3
"""Freeze the size-one and size-two same-input Tier 1 crossover panels."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-xyzz-batch-inversion-20261015"
OLD = "/workspace/bench-sources/prime-j0-xyzz-batch-inverse-native"
NEW = "/workspace/bench-sources/prime-j0-xyzz-batch-size-native"
BINARY_SHA = "c12828226c997b608cc2b6d407e9eaaedff9c38e89a94b24d5f0713d01a6645e"
SOURCE_SHA = "4df1be9f9046774f1f8720e1ba8e4c379df559c7171b636221fa9f572ac03cc8"
WINDOWS_SHA = "7272a3a818dac0fd38e028f91ba4bb75630a40849fc2375bdd0d14b20483ce62"


def freeze(size):
    assert size in (1, 2)
    base = json.loads((PARENT / "tier1-batch-manifest.json").read_text())
    rules = json.loads((PARENT / "tier1-batch-rules.json").read_text())
    rules["candidate_binary_sha256"] = BINARY_SHA
    rules["candidate_front_source_sha256"] = SOURCE_SHA
    rules["candidate_windows_source_sha256"] = WINDOWS_SHA
    rules["purpose"] = f"same-point 128-output throughput crossover: XYZZ inversion per {size} output(s) against individual affine inversions"
    rules["batch_law"] = f"128 frozen independent scalar outputs, partitioned into {128 // size} chunks of {size}; one inversion per chunk and 96 passes per arm"
    rules["timing_boundary"] = f"Rust Instant times 96 passes over the same 128 frozen scalar multiplications and affine recovery after table preparation; candidate uses one XYZZ inversion per {size}-output chunk, reference one inversion per scalar. All 12288 outputs are checked after the interval. This is batch throughput."
    rules["arm_order"] = "A/A fixed radix14 individual inversion, comparison, A/A fixed radix14 individual inversion; runner alternates reference/candidate order"
    rules["comparison_acceptance"] = "all 16 comparison pairs valid, both adjacent A/A gates pass, paired bootstrap95 log-ratio interval entirely above or below one"
    rules_name = f"tier1-size{size}-rules.json"
    (HERE / rules_name).write_text(json.dumps(rules, sort_keys=True, indent=2) + "\n")
    base["cases"][1]["candidate"] = [f"{NEW}/target/release/eisenstein_fixed", "--benchmark-split-prime-batch-inverse-size", str(size), "96"]
    base["artifacts"] = [p for p in base["artifacts"] if not p.startswith(f"{OLD}/") and not p.endswith("/xyzz-batch-rules.json")]
    base["artifacts"] += [
        f"{NEW}/Cargo.lock", f"{NEW}/Cargo.toml",
        f"{NEW}/src/bin/eisenstein_fixed.rs",
        f"{NEW}/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
        f"{NEW}/src/bin/mixed640_bench_fixture.json",
        f"{NEW}/native_batch_size_overlay.py", f"{NEW}/linux-test.log",
        f"{NEW}/linux-build.log", f"{NEW}/target/release/eisenstein_fixed",
        f"/workspace/isolated-bench/panels/tier1-size{size}-rules.json",
        *[f"{NEW}/screen-{n}.{ext}" for n in (1,2,4,8,16,32,64,128) for ext in ("stdout","stderr")],
    ]
    base["artifacts"] = sorted(set(base["artifacts"]))
    base["measurement_boundary"] = rules["timing_boundary"]
    manifest_name = f"tier1-size{size}-manifest.json"
    (HERE / manifest_name).write_text(json.dumps(base, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    for size in (1, 2):
        freeze(size)
