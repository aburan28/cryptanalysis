#!/usr/bin/env python3
"""Replay the fresh bounded-top table against full-pair and classical controls."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import struct
import sys

from check_joint_pair_panel import independent_atlas, model_case, run, sha256


ROOT = Path(__file__).resolve().parent
MODES = ("joint-pair-top-pos", "joint-pair-hex-pos", "joint-window4-xplane-pos",
         "fixed-comb9")


def validate_fresh(inputs, inputs_path):
    excluded = {"glv-j0-32": set(), "j0-56": set()}
    if inputs.get("source_sha256") != sha256(ROOT / "make_joint_pair_top_inputs.py") or \
            len(inputs.get("prior_manifest_sha256", {})) != 13:
        raise ValueError("fresh top fixture source or custody changed")
    for name, expected_hash in inputs["prior_manifest_sha256"].items():
        prior_path = ROOT / name
        if sha256(prior_path) != expected_hash:
            raise ValueError("prior manifest changed: " + name)
        for case in json.loads(prior_path.read_text())["cases"]:
            scalar_path = prior_path.parent / case["scalar_file"]
            if sha256(scalar_path) != case["scalar_file_sha256"]:
                raise ValueError("prior scalar file changed: " + name)
            excluded[case["curve"]["name"]].update(
                value for (value,) in struct.iter_unpack("<Q", scalar_path.read_bytes()))
    for case in inputs["cases"]:
        curve = case["curve"]["name"]
        scalar_path = inputs_path.parent / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            raise ValueError("new scalar file changed: " + case["id"])
        for (value,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
            if value >= case["curve"]["order"] or value in excluded[curve]:
                raise ValueError("fresh top fixture is not disjoint: " + case["id"])
            excluded[curve].add(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    build_cache = binary.parent / "CMakeCache.txt"
    if not build_cache.is_file():
        parser.error("CMakeCache.txt must sit beside the native binary")
    design_path = ROOT / "joint-pair-top-design.json"
    base_path = ROOT / "joint-pair-design.json"
    inputs_path = ROOT / "joint-pair-top-inputs/inputs.json"
    design = json.loads(design_path.read_text())
    base = json.loads(base_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    if inputs.get("design_sha256") != sha256(design_path) or \
            design.get("base_pair_design_sha256") != sha256(base_path) or \
            design.get("top_map_producer_sha256") != sha256(
                ROOT / "make_joint_pair_top_map.py") or \
            design.get("top_map_header_sha256") != sha256(
                ROOT.parents[1] / "src/generated/joint_pair_top_map.h"):
        parser.error("frozen bounded-top design or map changed")
    validate_fresh(inputs, inputs_path)
    sys.path[:0] = [str(ROOT), str(ROOT.parents[1])]
    from run import representatives, point_add, point_mul
    from make_joint_window4_map import build as build_old_map
    preferred, pair_reps = independent_atlas()
    rank = {rep: index for index, rep in enumerate(pair_reps)}
    old_reps, _ = build_old_map()
    old_rank = {rep: index for index, rep in enumerate(old_reps)}
    hot = json.loads((ROOT / "joint-window4-hot-design.json").read_text())
    selected = {row["curve"]: [tuple(pair) for pair in row["selected_representatives"]]
                for row in hot["records"]}
    base_records = {row["curve"]: row for row in base["records"]}
    top_records = {row["curve"]: row for row in design["records"]}
    rows, models = [], []
    for index, case in enumerate(inputs["cases"]):
        scalar_path = inputs_path.parent / case["scalar_file"]
        curve = case["curve"]["name"]
        top_record = top_records[curve]
        model = model_case(case, scalar_path, base_records[curve], preferred, rank, old_rank,
                           selected[curve], point_mul, point_add, representatives)
        models.append(model)
        rotated = MODES[index % len(MODES):] + MODES[:index % len(MODES)]
        current = [run(binary, mode, case, scalar_path) for mode in rotated]
        rows.extend(current)
        if any(row["exit_code"] or row["fields"].get("verified") != "1" for row in current):
            continue
        fields = {row["mode"]: row["fields"] for row in current}
        candidate, full, plane, comb = (fields[mode] for mode in MODES)
        shared = ("curve", "point_index", "count", "base_x", "base_y", "endo_lambda",
                  "input_digest", "output_digest")
        valid = (
            all(candidate.get(key) == control.get(key)
                for control in (full, plane, comb) for key in shared) and
            candidate["curve"] == curve and candidate["count"] == str(case["count"]) and
            candidate["base_x"] == case["base_x"] and
            candidate["base_y"] == case["base_y"] and
            int(candidate["adds"]) == int(full["adds"]) == model["adds"] and
            int(candidate["unit_adds"]) == int(full["unit_adds"]) == model["unit_adds"] and
            int(plane["adds"]) == model["baseline_adds"] and
            int(plane["unit_adds"]) == model["baseline_unit_adds"] and
            int(candidate["fallbacks"]) == int(full["fallbacks"]) ==
            int(plane["fallbacks"]) == int(comb["fallbacks"]) == 0 and
            int(candidate["point_entries"]) == top_record["point_entries"] and
            int(candidate["point_table_bytes"]) == top_record["point_table_bytes"] and
            int(candidate["plane_entries"]) == top_record["point_entries"] and
            int(candidate["static_map_bytes"]) == base["alphabet"]["static_map_bytes"] +
            design["top_static_bytes"] and
            int(candidate["prep_adds"]) == top_record["preparation_adds_model"] and
            int(candidate["prep_doubles"]) == 8 * (top_record["pair_positions"] - 1) and
            int(candidate["prep_layer_inversions"]) == top_record["pair_positions"] and
            int(candidate["prep_plane_muls"]) == top_record["point_entries"] and
            int(candidate["prep_temp_heap_bytes"]) == 64 * len(pair_reps) and
            int(candidate["prep_temp_stack_bytes"]) == 2 * 171 * 24 and
            int(full["point_entries"]) == base_records[curve]["nonzero_point_entries"] and
            int(full["point_table_bytes"]) == base_records[curve]["point_table_bytes"] and
            int(candidate["prep_bytes"]) - int(candidate["point_table_bytes"]) ==
            int(full["prep_bytes"]) - int(full["point_table_bytes"]))
        for row in current:
            row["gate_pass"] = valid
    passed = len(rows) == len(MODES) * len(inputs["cases"]) and \
        all(row.get("gate_pass") for row in rows)
    report = {"schema": 1, "status": "pass" if passed else "fail",
              "cpu_timing_claim": None, "host_exploratory": True, "isolated_receipt": None,
              "host": {"system": platform.system(), "machine": platform.machine(),
                       "processor": platform.processor()},
              "online_interval": "native 4096-scalar batch computation excluding preparation and independent replay; local timing exploratory",
              "design_sha256": sha256(design_path), "base_design_sha256": sha256(base_path),
              "inputs_sha256": sha256(inputs_path), "source_sha256": sha256(Path(__file__)),
              "independent_model_source_sha256": sha256(ROOT / "check_joint_pair_panel.py"),
              "top_map_producer_sha256": sha256(ROOT / "make_joint_pair_top_map.py"),
              "top_map_header_sha256": sha256(ROOT.parents[1] /
                                               "src/generated/joint_pair_top_map.h"),
              "pair_map_header_sha256": sha256(ROOT.parents[1] /
                                                "src/generated/joint_pair_map.h"),
              "bench_source_sha256": sha256(ROOT / "bench.c"),
              "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
              "ec_tau_header_sha256": sha256(ROOT.parents[1] / "src/ec_tau_internal.h"),
              "binary_sha256": sha256(binary), "cmake_cache_sha256": sha256(build_cache),
              "models": models, "rows": rows}
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "rows": len(rows),
                      "scalar_checks": sum(model["scalar_checks"] for model in models),
                      "group_checks": sum(model["group_checks"] for model in models)},
                     sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
