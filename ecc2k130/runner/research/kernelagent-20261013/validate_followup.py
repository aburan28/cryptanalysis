"""Replay the frozen follow-up GPU receipts without rerunning the kernel."""

import datetime
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = "1f8e6847de9e207880bd3be63835c3f56eb182d5"
CORPUS = "c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90"
SCREEN_CASES = {
    "static-barrier-screen": {
        "production_static_barriers": {"GPUFLAGS"},
        "production_static_128": {"GPUFLAGS", "THREADS", "MINBLOCKS"},
    },
    "root-barrier-screen": {"production_skip_root_barriers": {"GPUFLAGS"}},
    "top-half-clmad-screen": {"production_top_half_clmad": {"GPUFLAGS"}},
    "zip-square-screen": {"production_zip_square": {"GPUFLAGS"}},
}


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)


def screen(name, expected_variants):
    path = HERE / f"{name}.json"
    data = path.read_bytes()
    run = json.loads(data)
    rows = {row["name"]: row for row in run["variants"]}
    control = rows["production"]
    checks = {
        "completed": run["ok"] and run["winner"] == "production",
        "pinned_commit": run["baseline_commit"] == BASELINE,
        "expected_variants": set(rows) == {"production", *expected_variants},
        "same_candidate_source": all(
            row["candidate_source_sha256"] == control["candidate_source_sha256"]
            for row in rows.values()),
    }
    for variant, row in rows.items():
        delta = {key for key in set(control["settings"]) | set(row["settings"])
                 if control["settings"].get(key) != row["settings"].get(key)}
        checks[f"{variant}_settings"] = delta == expected_variants.get(variant, set())
        checks[f"{variant}_two_pairs"] = len(row["pairs"]) == 2
        checks[f"{variant}_ratios"] = all(
            close(pair["ratio"], pair["candidate"]["billions_per_second"] /
                  pair["baseline"]["billions_per_second"])
            for pair in row["pairs"]) and close(
                row["median_ratio"], statistics.median(p["ratio"] for p in row["pairs"]))
        checks[f"{variant}_corpus"] = all(
            arm["records"] == 355 and arm["sorted_sha256"] == CORPUS
            and "0 dropped" in arm["output"].lower()
            for pair in row["pairs"] for arm in (pair["baseline"], pair["candidate"]))
    aa = [pair["ratio"] for pair in control["pairs"]]
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "checks": checks,
        "paired_ratios": {variant: [pair["ratio"] for pair in row["pairs"]]
                          for variant, row in rows.items()},
        "above_aa_range": {variant: all(pair["ratio"] > max(aa) for pair in row["pairs"])
                           for variant, row in rows.items() if variant != "production"},
        "passed": all(checks.values()),
    }


def profile(name, expect_reload, require_raw=False):
    path = HERE / f"{name}.json"
    data = path.read_bytes()
    run = json.loads(data)
    output = run["profile"]["output"]
    checks = {
        "pinned_commit": run["baseline_commit"] == BASELINE,
        "walk_profiled": "eccPacked131::walk" in output,
        "22_passes": output.count("finished:") == 22,
        "replay_classification": ("reloaded" in output) == expect_reload,
        "zero_drops": output.count("0 dropped") >= 22,
    }
    if require_raw:
        checks["raw_import"] = run["profile_raw"]["returncode"] == 0
        checks["details_import"] = run["profile_details"]["returncode"] == 0
        checks["native_report_digest"] = len(run["ncu_report_sha256"]) == 64
    return {"sha256": hashlib.sha256(data).hexdigest(), "checks": checks,
            "valid_stable_workload": not expect_reload and all(checks.values()),
            "passed": all(checks.values())}


def main():
    inputs = {name: screen(name, variants) for name, variants in SCREEN_CASES.items()}
    for name in ("production-compute-profile", "production-compute-profile-isolated",
                 "production-stall-profile"):
        inputs[name] = profile(name, expect_reload=name == "production-compute-profile",
                               require_raw=name == "production-stall-profile")
    receipt = {
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "method": "independent JSON replay of frozen DP32 records, paired ratios, source/config identity, and profiler replay classification",
        "inputs": inputs,
        "all_passed": all(item["passed"] for item in inputs.values()),
    }
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
