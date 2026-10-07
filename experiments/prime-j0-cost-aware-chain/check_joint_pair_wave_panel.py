#!/usr/bin/env python3
"""Replay fresh affine-wavefront pairs against serial and classical controls."""

import argparse
import json
from pathlib import Path
import platform
import struct
import sys

from check_joint_pair_panel import independent_atlas, model_case, run, sha256, unit_images


ROOT = Path(__file__).resolve().parent
MODES = ("joint-pair-top-triple-wave128", "joint-pair-top-double-wave128",
         "joint-pair-top-triple-pos", "joint-pair-top-double-pos",
         "joint-window4-xplane-pos", "fixed-comb9")


def validate_fresh(inputs, inputs_path):
    excluded = {"glv-j0-32": set(), "j0-56": set()}
    if inputs.get("source_sha256") != sha256(ROOT / "make_joint_pair_wave_inputs.py") or \
            len(inputs.get("prior_manifest_sha256", {})) != 15:
        raise ValueError("fresh wave fixture source or custody changed")
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
                raise ValueError("fresh wave fixture is not disjoint: " + case["id"])
            excluded[curve].add(value)


def wave_model(case, scalar_path, record, preferred, representatives):
    """Count rotations and inverse waves from exact subgroup partial sums."""
    order = case["curve"]["order"]
    omega = record["omega_eigen"]
    rotations = omega_squared = 0
    inverse_waves = set()
    serial_inversions = 0
    for index, (scalar,) in enumerate(struct.iter_unpack("<Q", scalar_path.read_bytes())):
        _, a, b = min(representatives(order, omega, scalar), key=lambda item: item[0])
        x, y = a + b, -b
        partial = 0
        for position in range(record["pair_positions"]):
            digits = []
            for _ in range(2):
                digit = preferred[(x % 16, y % 16)]
                digits.append(digit)
                x, y = (x - digit[0]) // 16, (y - digit[1]) // 16
            pair = (digits[0][0] + 16 * digits[1][0],
                    digits[0][1] + 16 * digits[1][1])
            if pair != (0, 0):
                code = unit_images(min(unit_images(pair))).index(pair)
                rotations += code % 3 != 0
                omega_squared += code % 3 == 2
                contribution = ((pair[0] + omega * pair[1]) * 256**position) % order
                if partial and contribution:
                    inverse_waves.add((index // 128, position))
                partial = (partial + contribution) % order
        assert x == y == 0
        assert partial == scalar
        serial_inversions += scalar != 0
    return rotations, omega_squared, len(inverse_waves), serial_inversions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    build_cache = binary.parent / "CMakeCache.txt"
    if not build_cache.is_file():
        parser.error("CMakeCache.txt must sit beside the native binary")
    design_path = ROOT / "joint-pair-wave-design.json"
    width_path = ROOT / "joint-pair-width-design.json"
    top_path = ROOT / "joint-pair-top-design.json"
    base_path = ROOT / "joint-pair-design.json"
    inputs_path = ROOT / "joint-pair-wave-inputs/inputs.json"
    design = json.loads(design_path.read_text())
    width = json.loads(width_path.read_text())
    top = json.loads(top_path.read_text())
    base = json.loads(base_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    if inputs.get("design_sha256") != sha256(design_path) or \
            design.get("source_sha256") != sha256(ROOT / "make_joint_pair_wave_design.py") or \
            design.get("width_design_sha256") != sha256(width_path) or \
            design.get("training_inputs_sha256") != sha256(
                ROOT / "joint-pair-width-inputs/inputs.json") or \
            design.get("training_panel_sha256") != sha256(
                ROOT / "joint-pair-width-native-panel.json") or \
            design.get("block_size") != 128 or \
            width.get("base_top_design_sha256") != sha256(top_path) or \
            top.get("base_pair_design_sha256") != sha256(base_path) or \
            width.get("pair_map_header_sha256") != sha256(
                ROOT.parents[1] / "src/generated/joint_pair_map.h") or \
            width.get("top_map_header_sha256") != sha256(
                ROOT.parents[1] / "src/generated/joint_pair_top_map.h"):
        parser.error("frozen affine-wavefront design or map changed")
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
    top_records = {row["curve"]: row for row in top["records"]}
    width_records = {row["curve"]: row for row in width["records"]}
    wave_records = {row["curve"]: row for row in design["records"]}
    rows, models = [], []
    for index, case in enumerate(inputs["cases"]):
        scalar_path = inputs_path.parent / case["scalar_file"]
        curve = case["curve"]["name"]
        top_record = top_records[curve]
        width_record = width_records[curve]
        base_point = (int(case["base_x"]), int(case["base_y"]))
        assert point_mul(base_point, case["curve"]["order"], case["curve"]["p"],
                         case["curve"]["b"]) is None
        model = model_case(case, scalar_path, base_records[curve], preferred, rank, old_rank,
                           selected[curve], point_mul, point_add, representatives)
        (model["rotations"], model["omega_squared_pairs"], model["wave_inversions"],
         model["serial_inversions"]) = wave_model(
             case, scalar_path, base_records[curve], preferred, representatives)
        if model["unit_adds"] != 2 * model["omega_squared_pairs"]:
            raise ValueError("independent rotation and unit models differ")
        models.append(model)
        rotated = MODES[index % len(MODES):] + MODES[:index % len(MODES)]
        current = [run(binary, mode, case, scalar_path) for mode in rotated]
        rows.extend(current)
        if any(row["exit_code"] or row["fields"].get("verified") != "1" for row in current):
            continue
        fields = {row["mode"]: row["fields"] for row in current}
        triple_wave, double_wave, triple, double, plane, comb = (fields[mode] for mode in MODES)
        pair_rows = (triple_wave, double_wave, triple, double)
        shared = ("curve", "point_index", "count", "base_x", "base_y", "endo_lambda",
                  "input_digest", "output_digest")
        valid = (
            all(triple_wave.get(key) == control.get(key)
                for control in (double_wave, triple, double, plane, comb) for key in shared) and
            triple_wave["curve"] == curve and triple_wave["count"] == str(case["count"]) and
            triple_wave["base_x"] == case["base_x"] and
            triple_wave["base_y"] == case["base_y"] and
            all(int(row["adds"]) == model["adds"] for row in pair_rows) and
            int(triple_wave["unit_adds"]) == int(triple["unit_adds"]) ==
            model["unit_adds"] and
            int(double_wave["unit_adds"]) == int(double["unit_adds"]) == 0 and
            int(triple_wave["rotations"]) == int(triple["rotations"]) == 0 and
            int(double_wave["rotations"]) == int(double["rotations"]) ==
            model["rotations"] and
            int(triple_wave["output_inversions"]) ==
            int(double_wave["output_inversions"]) == model["wave_inversions"] and
            int(triple["output_inversions"]) == int(double["output_inversions"]) ==
            model["serial_inversions"] and
            model["wave_inversions"] <=
            wave_records[curve]["wave_output_inversions_upper_bound_per_case"] and
            int(plane["adds"]) == model["baseline_adds"] and
            int(plane["unit_adds"]) == model["baseline_unit_adds"] and
            all(int(row["fallbacks"]) == 0 for row in (*pair_rows, plane, comb)) and
            all(int(row["point_entries"]) == width_record["point_entries"]
                for row in pair_rows) and
            all(int(row["point_table_bytes"]) == width_record["word24_table_bytes"]
                for row in (triple_wave, triple)) and
            all(int(row["point_table_bytes"]) == width_record["word16_table_bytes"]
                for row in (double_wave, double)) and
            all(int(row["plane_entries"]) == width_record["point_entries"]
                for row in pair_rows) and
            all(int(row["static_map_bytes"]) == base["alphabet"]["static_map_bytes"] +
                top["top_static_bytes"] for row in pair_rows) and
            all(int(row["prep_adds"]) == top_record["preparation_adds_model"]
                for row in pair_rows) and
            all(int(row["prep_doubles"]) == 8 * (top_record["pair_positions"] - 1)
                for row in pair_rows) and
            all(int(row["prep_layer_inversions"]) == top_record["pair_positions"]
                for row in pair_rows) and
            int(triple_wave["prep_plane_muls"]) == int(triple["prep_plane_muls"]) ==
            width_record["point_entries"] and
            int(double_wave["prep_plane_muls"]) == int(double["prep_plane_muls"]) == 0 and
            all(int(row["prep_temp_heap_bytes"]) == 64 * len(pair_reps)
                for row in pair_rows) and
            all(int(row["prep_temp_stack_bytes"]) == 2 * 171 * 24
                for row in pair_rows) and
            int(triple_wave["prep_bytes"]) == int(triple["prep_bytes"]) and
            int(double_wave["prep_bytes"]) == int(double["prep_bytes"]) and
            int(triple_wave["online_scratch_bytes"]) ==
            int(double_wave["online_scratch_bytes"]) == 128 * (4 * 4 + 32 + 2 * 8 + 1))
        for row in current:
            row["gate_pass"] = valid
    passed = len(rows) == len(MODES) * len(inputs["cases"]) and \
        all(row.get("gate_pass") for row in rows)
    report = {"schema": 1, "status": "pass" if passed else "fail",
              "cpu_timing_claim": None, "host_exploratory": True, "isolated_receipt": None,
              "host": {"system": platform.system(), "machine": platform.machine(),
                       "processor": platform.processor()},
              "online_interval": "native 4096-scalar batch computation excluding preparation and independent replay; local timing exploratory",
              "design_sha256": sha256(design_path),
              "width_design_sha256": sha256(width_path),
              "top_design_sha256": sha256(top_path),
              "base_design_sha256": sha256(base_path),
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
              "subgroup_checks": len(inputs["cases"]), "models": models, "rows": rows}
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "rows": len(rows),
                      "scalar_checks": sum(model["scalar_checks"] for model in models),
                      "group_checks": sum(model["group_checks"] for model in models),
                      "subgroup_checks": report["subgroup_checks"]},
                     sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
