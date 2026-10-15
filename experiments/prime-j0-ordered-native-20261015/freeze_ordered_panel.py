#!/usr/bin/env python3
"""Freeze the ordered-versus-fixed fourteen-position Tier 1 panel."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-fourteen-position-mixed-radix-20261015"
OLD_REFERENCE = "/workspace/bench-sources/prime-j0-nearest-orbit-71023-native-batch"
REFERENCE = "/workspace/bench-sources/prime-j0-nearest-orbit-136531-native-batch"
CANDIDATE = "/workspace/bench-sources/prime-j0-ordered-norm14-native-batch"


def run():
    plan = json.loads((PARENT / "tier1-fixed14-manifest.json").read_text())
    for case in plan["cases"]:
        assert case["reference"] == [f"{OLD_REFERENCE}/target/release/eisenstein_fixed",
                                      "--benchmark-mixed640-batch", "96"]
        case["reference"][0] = f"{REFERENCE}/target/release/eisenstein_fixed"
        if case["id"] == "compare":
            assert case["candidate"][0] == f"{REFERENCE}/target/release/eisenstein_fixed"
            case["candidate"][0] = f"{CANDIDATE}/target/release/eisenstein_fixed"
        else:
            assert case["candidate"][0] == f"{OLD_REFERENCE}/target/release/eisenstein_fixed"
            case["candidate"][0] = f"{REFERENCE}/target/release/eisenstein_fixed"
    plan["artifacts"] = [path for path in plan["artifacts"]
                         if not path.startswith(f"{OLD_REFERENCE}/")
                         and not path.startswith("/workspace/isolated-bench/panels/radix71023-")]
    plan["artifacts"] += [
        f"{CANDIDATE}/Cargo.lock", f"{CANDIDATE}/Cargo.toml",
        f"{CANDIDATE}/src/bin/eisenstein_fixed.rs",
        f"{CANDIDATE}/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
        f"{CANDIDATE}/src/bin/mixed640_bench_fixture.json",
        f"{CANDIDATE}/native_ordered14_overlay.py", f"{CANDIDATE}/linux-test.log",
        f"{CANDIDATE}/linux-build.log", f"{CANDIDATE}/linux-preflight.stdout",
        f"{CANDIDATE}/linux-preflight.stderr",
        f"{CANDIDATE}/target/release/eisenstein_fixed",
        "/workspace/isolated-bench/panels/radixordered14-rules.json",
        "/workspace/isolated-bench/panels/radix136531-screen.json",
        "/workspace/isolated-bench/panels/radix136531-replay.json",
    ]
    plan["artifacts"] = sorted(set(plan["artifacts"]))
    plan["measurement_boundary"] = json.loads(
        (HERE / "tier1-ordered-rules.json").read_text())["timing_boundary"]
    return plan


if __name__ == "__main__":
    print(json.dumps(run(),sort_keys=True,indent=2))
