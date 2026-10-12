#!/usr/bin/env python3
"""Replay exact-corrected quotients against integer-division controls."""

import argparse
import json
from pathlib import Path
import platform
import struct
import sys

from check_joint_pair_five_panel import wave_model
from check_joint_pair_panel import independent_atlas, model_case, run, sha256, unit_images
from make_joint_pair_five_design import AXIAL, FULL, certificate, reduce
from make_joint_pair_guard_design import guard_thresholds, guarded_reduce
from make_joint_pair_qcorr_design import corrected_quotient
from run import lattice


ROOT = Path(__file__).resolve().parent
QCORR = ("joint-pair-top-triple-qcorr-pos", "joint-pair-top-double-qcorr-pos",
         "joint-pair-top-triple-qcorr-wave128", "joint-pair-top-double-qcorr-wave128")
GUARD = ("joint-pair-top-triple-guard-pos", "joint-pair-top-double-guard-pos",
         "joint-pair-top-triple-guard-wave128", "joint-pair-top-double-guard-wave128")
FIVE = tuple(mode.replace("-guard", "-five") for mode in GUARD)
FULL_MODES = tuple(mode.replace("-guard", "") for mode in GUARD)
MODES = QCORR + GUARD + FIVE + FULL_MODES + ("joint-window4-xplane-pos", "fixed-comb9")
SHARED = ("curve", "point_index", "count", "base_x", "base_y", "endo_lambda",
          "input_digest", "output_digest")


def validate_fresh(inputs, inputs_path):
    excluded = {"glv-j0-32": set(), "j0-56": set()}
    if inputs.get("source_sha256") != sha256(ROOT / "make_joint_pair_qcorr_inputs.py") or \
            len(inputs.get("prior_manifest_sha256", {})) != 18:
        raise ValueError("fresh quotient-correction fixture custody changed")
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
        scalar_path = inputs_path.parent / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            raise ValueError("new scalar file changed: " + case["id"])
        curve = case["curve"]["name"]
        for (value,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
            if value >= case["curve"]["order"] or value in excluded[curve]:
                raise ValueError("quotient-correction fixture is not disjoint: " + case["id"])
            excluded[curve].add(value)


def qcorr_model(case, scalar_path, record):
    order, multipliers = record["order"], record["multipliers"]
    corrections = checked = 0
    values = [k for (k,) in struct.iter_unpack("<Q", scalar_path.read_bytes())]
    if case["id"].endswith("point0"):
        boundary = [row["scalar"] for row in record["boundary_challenges"]]
        if values[:4] != boundary:
            raise ValueError("frozen near-half challenges changed")
    for scalar in values:
        if scalar == 0:
            continue
        for multiplier in multipliers:
            _, count = corrected_quotient(scalar, multiplier, order)
            corrections += count
            checked += 1
    return {"quotient_checks": checked, "quotient_corrections": corrections}


def guard_model(case, scalar_path, record):
    b1, b2, det = lattice(record["order"], record["omega_eigen"])
    if [list(b1), list(b2)] != record["basis"] or det != record["determinant"] or \
            certificate(b1, b2, det) != record["short_vector_certificate"] or \
            guard_thresholds(b1, b2) != (record["horizontal_threshold_strict"],
                                           record["vertical_threshold_strict"]):
        raise ValueError("guard or short-vector certificate changed")
    accepted = fallback_center = count = 0
    for (scalar,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
        guarded, fast = guarded_reduce(scalar, b1, b2, det)
        five = reduce(scalar, b1, b2, det, AXIAL)
        old = reduce(scalar, b1, b2, det, FULL)
        if guarded != five or guarded[0:3] != old[0:3]:
            raise ValueError("guarded representative or minimum differs from controls")
        accepted += fast and scalar != 0
        fallback_center += not fast and guarded[3:] == (0, 0)
        count += 1
    return {"guard_hits": accepted, "guard_fallback_center": fallback_center,
            "representative_checks": count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    build_cache = binary.parent / "CMakeCache.txt"
    if not build_cache.is_file():
        parser.error("CMakeCache.txt must sit beside the native binary")
    design_path = ROOT / "joint-pair-qcorr-design.json"
    guard_path = ROOT / "joint-pair-guard-design.json"
    five_path = ROOT / "joint-pair-five-design.json"
    wave_path = ROOT / "joint-pair-wave-design.json"
    width_path = ROOT / "joint-pair-width-design.json"
    top_path = ROOT / "joint-pair-top-design.json"
    base_path = ROOT / "joint-pair-design.json"
    inputs_path = ROOT / "joint-pair-qcorr-inputs/inputs.json"
    design = json.loads(design_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    guard = json.loads(guard_path.read_text())
    five = json.loads(five_path.read_text())
    wave = json.loads(wave_path.read_text())
    width = json.loads(width_path.read_text())
    top = json.loads(top_path.read_text())
    base = json.loads(base_path.read_text())
    if inputs.get("design_sha256") != sha256(design_path) or \
            design.get("source_sha256") != sha256(ROOT / "make_joint_pair_qcorr_design.py") or \
            design.get("base_guard_design_sha256") != sha256(guard_path) or \
            design.get("training_inputs_sha256") != sha256(
                ROOT / "joint-pair-guard-inputs/inputs.json") or \
            design.get("training_panel_sha256") != sha256(
                ROOT / "joint-pair-guard-native-panel.json") or \
            guard.get("base_five_design_sha256") != sha256(five_path) or \
            five.get("base_wave_design_sha256") != sha256(wave_path) or \
            wave.get("width_design_sha256") != sha256(width_path) or \
            width.get("base_top_design_sha256") != sha256(top_path) or \
            top.get("base_pair_design_sha256") != sha256(base_path) or \
            width.get("pair_map_header_sha256") != sha256(
                ROOT.parents[1] / "src/generated/joint_pair_map.h") or \
            width.get("top_map_header_sha256") != sha256(
                ROOT.parents[1] / "src/generated/joint_pair_top_map.h"):
        parser.error("frozen quotient-correction design or pair atlas changed")
    validate_fresh(inputs, inputs_path)
    sys.path[:0] = [str(ROOT), str(ROOT.parents[1])]
    from run import point_add, point_mul, representatives
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
    wave_records = {row["curve"]: row for row in wave["records"]}
    guard_records = {row["curve"]: row for row in guard["records"]}
    qcorr_records = {row["curve"]: row for row in design["records"]}
    rows, models = [], []
    for index, case in enumerate(inputs["cases"]):
        scalar_path = inputs_path.parent / case["scalar_file"]
        curve = case["curve"]["name"]
        base_point = (int(case["base_x"]), int(case["base_y"]))
        assert point_mul(base_point, case["curve"]["order"], case["curve"]["p"],
                         case["curve"]["b"]) is None
        model = model_case(case, scalar_path, base_records[curve], preferred, rank, old_rank,
                           selected[curve], point_mul, point_add, representatives)
        (model["rotations"], model["omega_squared_pairs"], model["wave_inversions"],
         model["serial_inversions"]) = wave_model(
             case, scalar_path, base_records[curve], preferred, representatives)
        model.update(guard_model(case, scalar_path, guard_records[curve]))
        model.update(qcorr_model(case, scalar_path, qcorr_records[curve]))
        if model["unit_adds"] != 2 * model["omega_squared_pairs"]:
            raise ValueError("independent operation models differ")
        models.append(model)
        rotated = MODES[index % len(MODES):] + MODES[:index % len(MODES)]
        current = [run(binary, mode, case, scalar_path) for mode in rotated]
        rows.extend(current)
        if any(row["exit_code"] or row["fields"].get("verified") != "1" for row in current):
            for row in current:
                row["gate_pass"] = False
            continue
        fields = {row["mode"]: row["fields"] for row in current}
        pair_fields = [fields[mode] for mode in QCORR + GUARD + FIVE + FULL_MODES]
        baseline = fields["joint-window4-xplane-pos"]
        comb = fields["fixed-comb9"]
        width_record = width_records[curve]
        top_record = top_records[curve]
        valid = (
            all(fields[QCORR[0]].get(key) == control.get(key)
                for control in (*pair_fields[1:], baseline, comb) for key in SHARED) and
            fields[QCORR[0]]["curve"] == curve and
            fields[QCORR[0]]["count"] == str(case["count"]) and
            fields[QCORR[0]]["base_x"] == case["base_x"] and
            fields[QCORR[0]]["base_y"] == case["base_y"] and
            all(int(row["adds"]) == model["adds"] for row in pair_fields) and
            all(int(fields[mode]["unit_adds"]) == model["unit_adds"]
                for mode in (QCORR[0], QCORR[2], GUARD[0], GUARD[2], FIVE[0], FIVE[2],
                             FULL_MODES[0], FULL_MODES[2])) and
            all(int(fields[mode]["unit_adds"]) == 0
                for mode in (QCORR[1], QCORR[3], GUARD[1], GUARD[3], FIVE[1], FIVE[3],
                             FULL_MODES[1], FULL_MODES[3])) and
            all(int(fields[mode]["rotations"]) == model["rotations"]
                for mode in (QCORR[1], QCORR[3], GUARD[1], GUARD[3], FIVE[1], FIVE[3],
                             FULL_MODES[1], FULL_MODES[3])) and
            all(int(fields[mode]["rotations"]) == 0
                for mode in (QCORR[0], QCORR[2], GUARD[0], GUARD[2], FIVE[0], FIVE[2],
                             FULL_MODES[0], FULL_MODES[2])) and
            all(int(fields[mode]["output_inversions"]) == model["serial_inversions"]
                for mode in (QCORR[0], QCORR[1], GUARD[0], GUARD[1], FIVE[0], FIVE[1],
                             FULL_MODES[0], FULL_MODES[1])) and
            all(int(fields[mode]["output_inversions"]) == model["wave_inversions"]
                for mode in (QCORR[2], QCORR[3], GUARD[2], GUARD[3], FIVE[2], FIVE[3],
                             FULL_MODES[2], FULL_MODES[3])) and
            all(int(fields[mode]["guard_hits"]) == model["guard_hits"]
                for mode in QCORR + GUARD) and
            all(int(fields[mode]["guard_hits"]) == 0 for mode in FIVE + FULL_MODES) and
            all(int(fields[mode]["quotient_float_enabled"]) == 1 for mode in QCORR) and
            all(int(fields[mode]["quotient_float_enabled"]) == 0
                for mode in GUARD + FIVE + FULL_MODES) and
            all(int(fields[mode]["quotient_corrections"]) ==
                model["quotient_corrections"] for mode in QCORR) and
            all(int(fields[mode]["quotient_corrections"]) == 0
                for mode in GUARD + FIVE + FULL_MODES) and
            all(int(row["fallbacks"]) == 0 for row in (*pair_fields, baseline, comb)) and
            int(baseline["adds"]) == model["baseline_adds"] and
            int(baseline["unit_adds"]) == model["baseline_unit_adds"] and
            all(int(row["point_entries"]) == width_record["point_entries"]
                for row in pair_fields) and
            all(int(row["plane_entries"]) == width_record["point_entries"]
                for row in pair_fields) and
            all(int(fields[mode]["point_table_bytes"]) == width_record["word24_table_bytes"]
                for mode in (QCORR[0], QCORR[2], GUARD[0], GUARD[2], FIVE[0], FIVE[2],
                             FULL_MODES[0], FULL_MODES[2])) and
            all(int(fields[mode]["point_table_bytes"]) == width_record["word16_table_bytes"]
                for mode in (QCORR[1], QCORR[3], GUARD[1], GUARD[3], FIVE[1], FIVE[3],
                             FULL_MODES[1], FULL_MODES[3])) and
            all(int(row["prep_adds"]) == top_record["preparation_adds_model"]
                for row in pair_fields) and
            all(int(row["prep_doubles"]) == 8 * (top_record["pair_positions"] - 1)
                for row in pair_fields) and
            all(int(row["prep_layer_inversions"]) == top_record["pair_positions"]
                for row in pair_fields) and
            all(int(fields[mode]["online_scratch_bytes"]) == 128 * (4 * 4 + 32 + 2 * 8 + 1)
                for mode in (QCORR[2], QCORR[3], GUARD[2], GUARD[3], FIVE[2], FIVE[3],
                             FULL_MODES[2], FULL_MODES[3])) and
            model["wave_inversions"] <=
            wave_records[curve]["wave_output_inversions_upper_bound_per_case"])
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
              "base_guard_design_sha256": sha256(guard_path),
              "base_five_design_sha256": sha256(five_path),
              "width_design_sha256": sha256(width_path),
              "top_design_sha256": sha256(top_path),
              "inputs_sha256": sha256(inputs_path), "source_sha256": sha256(Path(__file__)),
              "independent_model_source_sha256": sha256(ROOT / "check_joint_pair_panel.py"),
              "five_check_source_sha256": sha256(ROOT / "check_joint_pair_five_panel.py"),
              "guard_check_source_sha256": sha256(ROOT / "check_joint_pair_guard_panel.py"),
              "guard_design_source_sha256": sha256(ROOT / "make_joint_pair_guard_design.py"),
              "qcorr_design_source_sha256": sha256(ROOT / "make_joint_pair_qcorr_design.py"),
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
                      "guard_hits": sum(model["guard_hits"] for model in models),
                      "quotient_corrections": sum(model["quotient_corrections"]
                                                   for model in models),
                      "group_checks": sum(model["group_checks"] for model in models)},
                     sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
