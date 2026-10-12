#!/usr/bin/env python3
"""Replay the fresh scalar fixture through full, exact, direct, and atlas modes."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess


ROOT = Path(__file__).resolve().parent
MODES = ("tau3-fused-pos", "tau3-scatter-pos", "tau3-scatter-direct-pos",
         "tau3-scatter-atlas-pos")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(stdout):
    return dict(part.split("=", 1) for part in stdout.strip().split() if "=" in part)


def run(binary, mode, case, scalar_path):
    point_index = case["id"].rsplit("point", 1)[1]
    argv = [str(binary), mode, case["curve"]["name"], point_index, str(scalar_path)]
    result = subprocess.run(argv, cwd=ROOT.parents[1], capture_output=True, text=True,
                            check=False)
    return {"mode": mode, "case_id": case["id"], "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "fields": parse(result.stdout) if result.returncode == 0 else {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    build_cache = binary.parent / "CMakeCache.txt"
    if not build_cache.is_file():
        parser.error("CMakeCache.txt must sit beside the native binary")
    inputs_path = ROOT / "tau3-scatter-atlas-inputs/inputs.json"
    design_path = ROOT / "tau3-scatter-design.json"
    policy_path = ROOT / "tau3-scatter-direct-design.json"
    layout_path = ROOT / "tau3-scatter-atlas-design.json"
    exact_path = ROOT / "tau3-scatter-atlas-exact-panel.json"
    direct_path = ROOT / "tau3-scatter-atlas-direct-panel.json"
    inputs = json.loads(inputs_path.read_text())
    exact = json.loads(exact_path.read_text())
    direct = json.loads(direct_path.read_text())
    if (inputs["design_sha256"] != sha256(design_path) or
        inputs["policy_sha256"] != sha256(policy_path) or
        inputs["layout_sha256"] != sha256(layout_path) or
        exact["inputs_sha256"] != sha256(inputs_path) or
        direct["inputs_sha256"] != sha256(inputs_path) or
        direct["exact_panel_sha256"] != sha256(exact_path)):
        parser.error("frozen inputs, policy, or model hash changed")
    exact_rows = {row["case_id"]: row for row in exact["rows"]}
    direct_rows = {row["case_id"]: row for row in direct["rows"]}
    rows = []
    for index, case in enumerate(inputs["cases"]):
        scalar_path = ROOT / "tau3-scatter-atlas-inputs" / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            parser.error("frozen scalar file changed: " + case["id"])
        order = MODES[index % 4:] + MODES[:index % 4]
        current = [run(binary, mode, case, scalar_path) for mode in order]
        rows.extend(current)
        if any(row["exit_code"] or row["fields"].get("verified") != "1" for row in current):
            continue
        fields = {row["mode"]: row["fields"] for row in current}
        full, optimum, greedy, atlas = (fields[mode] for mode in MODES)
        exact_want = exact_rows[case["id"]]
        direct_want = direct_rows[case["id"]]
        shared = ("curve", "point_index", "count", "base_x", "base_y",
                  "endo_lambda", "input_digest", "output_digest")
        valid = (
            all(full.get(key) == variant.get(key) for variant in (optimum, greedy, atlas)
                for key in shared) and
            full["curve"] == case["curve"]["name"] and
            full["point_index"] == case["id"].rsplit("point", 1)[1] and
            full["count"] == str(case["count"]) and
            full["base_x"] == case["base_x"] and full["base_y"] == case["base_y"] and
            int(full["adds"]) == exact_want["base_adds"] == direct_want["base_adds"] and
            int(optimum["adds"]) == exact_want["scatter_adds"] == direct_want["exact_adds"] and
            int(greedy["adds"]) == int(atlas["adds"]) == direct_want["direct_adds"] and
            int(optimum["scatter_pairs"]) == exact_want["matched_pairs"] and
            int(greedy["scatter_pairs"]) == int(atlas["scatter_pairs"]) ==
            direct_want["direct_matched_pairs"] and
            int(full["fallbacks"]) == int(optimum["fallbacks"]) ==
            int(greedy["fallbacks"]) == int(atlas["fallbacks"]) == 0 and
            int(optimum["point_entries"]) == int(greedy["point_entries"]) ==
            int(atlas["point_entries"]) ==
            int(optimum["scatter_preparation_checks"]) ==
            int(greedy["scatter_preparation_checks"]) ==
            int(atlas["scatter_preparation_checks"]) == exact_want["point_entries"] and
            int(atlas["static_map_bytes"]) > int(greedy["static_map_bytes"]))
        for row in current:
            row["gate_pass"] = valid

    passed = len(rows) == 4 * len(inputs["cases"]) and all(row.get("gate_pass") for row in rows)
    report = {"schema": 1, "status": "pass" if passed else "fail",
              "cpu_timing_claim": None, "host_exploratory": True, "isolated_receipt": None,
              "host": {"system": platform.system(), "machine": platform.machine(),
                       "processor": platform.processor()},
              "online_interval": "native 4096-scalar batch computation excluding preparation and verification; local timing exploratory",
              "policy_sha256": sha256(policy_path), "layout_sha256": sha256(layout_path),
              "design_sha256": sha256(design_path),
              "inputs_sha256": sha256(inputs_path), "exact_panel_sha256": sha256(exact_path),
              "direct_panel_sha256": sha256(direct_path), "source_sha256": sha256(Path(__file__)),
              "bench_source_sha256": sha256(ROOT / "bench.c"),
              "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
              "map_header_sha256": sha256(ROOT.parents[1] / "src/generated/tau3_scatter.h"),
              "atlas_header_sha256": sha256(ROOT.parents[1] /
                                            "src/generated/tau3_scatter_atlas.h"),
              "binary_sha256": sha256(binary), "cmake_cache_sha256": sha256(build_cache),
              "rows": rows}
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "rows": len(rows),
                      "verified_cases": sum(all(row.get("gate_pass") for row in rows[i:i + 4])
                                            for i in range(0, len(rows), 4))}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
