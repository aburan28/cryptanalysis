#!/usr/bin/env python3
"""Replay certified five-neighbor reduction on disjoint scalar fixtures."""

import argparse
import json
from pathlib import Path
import platform
import struct
import sys

from check_joint_pair_panel import independent_atlas, model_case, run, sha256, unit_images
from make_joint_pair_five_design import AXIAL, FULL, certificate, reduce
from run import lattice


ROOT = Path(__file__).resolve().parent
MODES = ("joint-pair-top-triple-five-wave128", "joint-pair-top-double-five-wave128",
         "joint-pair-top-triple-five-pos", "joint-pair-top-double-five-pos",
         "joint-pair-top-triple-wave128", "joint-pair-top-double-wave128",
         "joint-pair-top-triple-pos", "joint-pair-top-double-pos",
         "joint-window4-xplane-pos", "fixed-comb9")


def validate_fresh(inputs, inputs_path):
    excluded = {"glv-j0-32": set(), "j0-56": set()}
    if inputs.get("source_sha256") != sha256(ROOT / "make_joint_pair_five_inputs.py") or \
            len(inputs.get("prior_manifest_sha256", {})) != 16:
        raise ValueError("fresh five-neighbor fixture source or custody changed")
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
                raise ValueError("fresh five-neighbor fixture is not disjoint: " + case["id"])
            excluded[curve].add(value)


def check_certified_representatives(case, scalar_path, row):
    b1, b2, det = lattice(row["order"], row["omega_eigen"])
    if [list(b1), list(b2)] != row["basis"] or det != row["determinant"] or \
            certificate(b1, b2, det) != row["certificate"]:
        raise ValueError("five-neighbor lattice certificate changed")
    matches = 0
    for (scalar,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
        old = reduce(scalar, b1, b2, det, FULL)
        new = reduce(scalar, b1, b2, det, AXIAL)
        if old[0] != new[0]:
            raise ValueError("five-neighbor minimum differs from full search")
        if old[1:3] != new[1:3]:
            raise ValueError("tie selected a different representative; revise cost model")
        matches += 1
    return matches


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
    design_path = ROOT / "joint-pair-five-design.json"
    wave_path = ROOT / "joint-pair-wave-design.json"
    width_path = ROOT / "joint-pair-width-design.json"
    top_path = ROOT / "joint-pair-top-design.json"
    base_path = ROOT / "joint-pair-design.json"
    inputs_path = ROOT / "joint-pair-five-inputs/inputs.json"
    design = json.loads(design_path.read_text())
    width = json.loads(width_path.read_text())
    top = json.loads(top_path.read_text())
    base = json.loads(base_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    if inputs.get("design_sha256") != sha256(design_path) or \
            design.get("source_sha256") != sha256(ROOT / "make_joint_pair_five_design.py") or \
            design.get("base_wave_design_sha256") != sha256(wave_path) or \
            design.get("base_pair_design_sha256") != sha256(base_path) or \
            design.get("candidate_offsets_in_old_tie_order") != [list(v) for v in AXIAL] or \
            json.loads(wave_path.read_text()).get("width_design_sha256") != sha256(width_path) or \
            design.get("training_inputs_sha256") != sha256(
                ROOT / "joint-pair-wave-inputs/inputs.json") or \
            design.get("training_panel_sha256") != sha256(
                ROOT / "joint-pair-wave-native-panel.json") or \
            width.get("base_top_design_sha256") != sha256(top_path) or \
            top.get("base_pair_design_sha256") != sha256(base_path) or \
            width.get("pair_map_header_sha256") != sha256(
                ROOT.parents[1] / "src/generated/joint_pair_map.h") or \
            width.get("top_map_header_sha256") != sha256(
                ROOT.parents[1] / "src/generated/joint_pair_top_map.h"):
        parser.error("frozen five-neighbor design or map changed")
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
    wave_records = {row["curve"]: row for row in json.loads(wave_path.read_text())["records"]}
    five_records = {row["curve"]: row for row in design["records"]}
    rows, models = [], []
    for index, case in enumerate(inputs["cases"]):
        scalar_path = inputs_path.parent / case["scalar_file"]
        curve = case["curve"]["name"]
        top_record = top_records[curve]
        width_record = width_records[curve]
        base_point = (int(case["base_x"]), int(case["base_y"]))
        assert point_mul(base_point, case["curve"]["order"], case["curve"]["p"],
                         case["curve"]["b"]) is None
        representative_matches = check_certified_representatives(
            case, scalar_path, five_records[curve])
        model = model_case(case, scalar_path, base_records[curve], preferred, rank, old_rank,
                           selected[curve], point_mul, point_add, representatives)
        model["five_representative_matches"] = representative_matches
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
        (five_triple_wave, five_double_wave, five_triple, five_double,
         triple_wave, double_wave, triple, double, plane, comb) = (fields[mode] for mode in MODES)
        pair_rows = (five_triple_wave, five_double_wave, five_triple, five_double,
                     triple_wave, double_wave, triple, double)
        shared = ("curve", "point_index", "count", "base_x", "base_y", "endo_lambda",
                  "input_digest", "output_digest")
        valid = (
            all(five_triple_wave.get(key) == control.get(key)
                for control in (*pair_rows[1:], plane, comb) for key in shared) and
            triple_wave["curve"] == curve and triple_wave["count"] == str(case["count"]) and
            triple_wave["base_x"] == case["base_x"] and
            triple_wave["base_y"] == case["base_y"] and
            all(int(row["adds"]) == model["adds"] for row in pair_rows) and
            all(int(row["unit_adds"]) == model["unit_adds"]
                for row in (five_triple_wave, five_triple, triple_wave, triple)) and
            all(int(row["unit_adds"]) == 0
                for row in (five_double_wave, five_double, double_wave, double)) and
            all(int(row["rotations"]) == 0
                for row in (five_triple_wave, five_triple, triple_wave, triple)) and
            all(int(row["rotations"]) == model["rotations"]
                for row in (five_double_wave, five_double, double_wave, double)) and
            all(int(row["output_inversions"]) == model["wave_inversions"]
                for row in (five_triple_wave, five_double_wave, triple_wave, double_wave)) and
            all(int(row["output_inversions"]) == model["serial_inversions"]
                for row in (five_triple, five_double, triple, double)) and
            model["wave_inversions"] <=
            wave_records[curve]["wave_output_inversions_upper_bound_per_case"] and
            int(plane["adds"]) == model["baseline_adds"] and
            int(plane["unit_adds"]) == model["baseline_unit_adds"] and
            all(int(row["fallbacks"]) == 0 for row in (*pair_rows, plane, comb)) and
            all(int(row["point_entries"]) == width_record["point_entries"]
                for row in pair_rows) and
            all(int(row["point_table_bytes"]) == width_record["word24_table_bytes"]
                for row in (five_triple_wave, five_triple, triple_wave, triple)) and
            all(int(row["point_table_bytes"]) == width_record["word16_table_bytes"]
                for row in (five_double_wave, five_double, double_wave, double)) and
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
            all(int(row["prep_plane_muls"]) == width_record["point_entries"]
                for row in (five_triple_wave, five_triple, triple_wave, triple)) and
            all(int(row["prep_plane_muls"]) == 0
                for row in (five_double_wave, five_double, double_wave, double)) and
            all(int(row["prep_temp_heap_bytes"]) == 64 * len(pair_reps)
                for row in pair_rows) and
            all(int(row["prep_temp_stack_bytes"]) == 2 * 171 * 24
                for row in pair_rows) and
            len({row["prep_bytes"] for row in
                 (five_triple_wave, five_triple, triple_wave, triple)}) == 1 and
            len({row["prep_bytes"] for row in
                 (five_double_wave, five_double, double_wave, double)}) == 1 and
            all(int(row["online_scratch_bytes"]) == 128 * (4 * 4 + 32 + 2 * 8 + 1)
                for row in (five_triple_wave, five_double_wave, triple_wave, double_wave)))
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
              "wave_design_sha256": sha256(wave_path),
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
