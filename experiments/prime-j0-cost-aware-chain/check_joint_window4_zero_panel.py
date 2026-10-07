#!/usr/bin/env python3
"""Independently model and replay a held-out zero-window native panel."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
MODES = ("joint-window4-zero-pos", "joint-window4-xplane-pos", "fixed-comb9")


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


def unit_actions(x, y):
    result = []
    for sign in (1, -1):
        a, b = sign * x, sign * y
        for _ in range(3):
            result.append((a, b))
            a, b = -b, a - b
    return result


def model_case(case, scalar_path, positions, omega_eigen, selected):
    sys.path[:0] = [str(ROOT), str(ROOT.parents[1])]
    from run import lattice, nearest_quotient, representatives, point_add, point_mul

    modulus, curve_b, order = (case["curve"][key] for key in ("p", "b", "order"))
    point = int(case["base_x"]), int(case["base_y"])
    model_adds = baseline_adds = unit_adds = baseline_unit_adds = 0
    scalar_checks = point_checks = fallbacks = baseline_fallbacks = 0
    attempts = feasible = steered = 0
    from make_joint_window4_map import build
    canonical, _ = build()
    rank = {rep: index for index, rep in enumerate(canonical)}
    v1, v2, determinant = lattice(order, omega_eigen)
    determinant_inverse = pow(determinant, -1, 16)

    def digits(x, y):
        answer = []
        while x or y:
            dx, dy = x % 16, y % 16
            if dx >= 8:
                dx -= 16
            if dy >= 8:
                dy -= 16
            answer.append((dx, dy))
            x, y = (x - dx) // 16, (y - dy) // 16
        return answer

    def unit_cost(digit_pairs):
        additions = unit_additions = 0
        for dx, dy in digit_pairs:
            if not (dx or dy):
                continue
            orbit = rank[min(unit_actions(dx, dy))]
            codes = [code for code, moved in enumerate(unit_actions(*selected[orbit]))
                     if moved == (dx, dy)]
            assert len(codes) == 1
            additions += 1
            unit_additions += 2 * (codes[0] % 3 == 2)
        return additions, unit_additions

    for index, (scalar,) in enumerate(struct.iter_unpack("<Q", scalar_path.read_bytes())):
        _, a, b = min(representatives(order, omega_eigen, scalar), key=lambda item: item[0])
        baseline = (a + b, -b)
        baseline_digits = digits(*baseline)
        base_adds, base_unit_adds = unit_cost(baseline_digits)
        baseline_adds += base_adds
        baseline_unit_adds += base_unit_adds
        baseline_fits = len(baseline_digits) <= positions
        baseline_fallbacks += not baseline_fits
        chosen = baseline_digits
        if scalar:
            attempts += 1
            u0 = nearest_quotient(scalar * v2[1], determinant)
            v0 = nearest_quotient(-scalar * v1[1], determinant)
            u_residue = scalar * v2[1] * determinant_inverse % 16
            v_residue = -scalar * v1[1] * determinant_inverse % 16
            du, dv = (u_residue - u0) % 16, (v_residue - v0) % 16
            if du >= 8:
                du -= 16
            if dv >= 8:
                dv -= 16
            u, v = u0 + du, v0 + dv
            directed = (scalar - u * v1[0] - v * v2[0],
                        -u * v1[1] - v * v2[1])
            assert directed[0] % 16 == directed[1] % 16 == 0
            candidate_digits = digits(*directed)
            if len(candidate_digits) <= positions:
                feasible += 1
                candidate_adds = unit_cost(candidate_digits)[0]
                if not baseline_fits or candidate_adds < base_adds:
                    chosen = candidate_digits
                    steered += 1
        chosen_adds, chosen_unit_adds = unit_cost(chosen)
        model_adds += chosen_adds
        unit_adds += chosen_unit_adds
        fallbacks += len(chosen) > positions
        assert sum((dx + dy * omega_eigen) * 16**position
                   for position, (dx, dy) in enumerate(chosen)) % order == scalar
        group_sum = None
        check_group = index < 16 or index % 512 == 0
        if check_group:
            for position, (dx, dy) in enumerate(chosen):
                if dx or dy:
                    term = point_mul(point, ((dx + dy * omega_eigen) * 16**position) % order,
                                     modulus, curve_b)
                    group_sum = point_add(group_sum, term, modulus, curve_b)
        scalar_checks += 1
        if check_group:
            assert group_sum == point_mul(point, scalar, modulus, curve_b)
            point_checks += 1
    return {"adds": model_adds, "rotations": 0, "unit_adds": unit_adds,
            "baseline_adds": baseline_adds, "baseline_unit_adds": baseline_unit_adds,
            "zero_attempts": attempts, "zero_feasible": feasible, "zero_selected": steered,
            "baseline_fallbacks": baseline_fallbacks,
            "scalar_checks": scalar_checks, "point_checks": point_checks,
            "fallbacks": fallbacks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    build_cache = binary.parent / "CMakeCache.txt"
    if not build_cache.is_file():
        parser.error("CMakeCache.txt must sit beside the native binary")
    inputs_path = ROOT / "joint-window4-zero-inputs/inputs.json"
    design_path = ROOT / "joint-window4-zero-design.json"
    baseline_design = json.loads((ROOT / "joint-window4-design.json").read_text())
    plane_design_path = ROOT / "joint-window4-plane-design.json"
    hot_design_path = ROOT / "joint-window4-hot-design.json"
    hot_design = json.loads(hot_design_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    design = json.loads(design_path.read_text())
    if inputs["design_sha256"] != sha256(design_path):
        parser.error("frozen design changed")
    if design["base_plane_design_sha256"] != sha256(plane_design_path) or \
            design["training_inputs_sha256"] != sha256(
                ROOT / "joint-window4-plane-inputs/inputs.json"):
        parser.error("zero-window design base changed")
    selected = {row["curve"]: [tuple(pair) for pair in row["selected_representatives"]]
                for row in hot_design["records"]}
    old_panel = json.loads((ROOT / "compact-pos-panel.json").read_text())
    eigen = {row["case_id"]: int(row["fields"]["endo_lambda"])
             for row in old_panel["rows"] if row["mode"] == "pos-compact"}
    rows, models = [], []
    for index, case in enumerate(inputs["cases"]):
        scalar_path = inputs_path.parent / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            parser.error("frozen scalar file changed: " + case["id"])
        curve = case["curve"]["name"]
        order = case["curve"]["order"]
        omega_eigen = (order - eigen[case["id"]]) % order
        model = model_case(case, scalar_path, baseline_design["curve_positions"][curve],
                           omega_eigen, selected[curve])
        model["case_id"] = case["id"]
        models.append(model)
        rotated = MODES[index % 3:] + MODES[:index % 3]
        current = [run(binary, mode, case, scalar_path) for mode in rotated]
        rows.extend(current)
        if any(row["exit_code"] or row["fields"].get("verified") != "1" for row in current):
            continue
        fields = {row["mode"]: row["fields"] for row in current}
        candidate, plane, comb = (fields[mode] for mode in MODES)
        shared = ("curve", "point_index", "count", "base_x", "base_y",
                  "endo_lambda", "input_digest", "output_digest")
        valid = (
            all(candidate.get(key) == control.get(key) for control in (comb, plane)
                for key in shared) and
            candidate["curve"] == curve and candidate["count"] == str(case["count"]) and
            candidate["base_x"] == case["base_x"] and
            candidate["base_y"] == case["base_y"] and
            int(candidate["adds"]) == model["adds"] and
            int(candidate["rotations"]) == model["rotations"] and
            int(candidate["unit_adds"]) == model["unit_adds"] and
            int(plane["rotations"]) == 0 and
            int(plane["adds"]) == model["baseline_adds"] and
            int(plane["unit_adds"]) == model["baseline_unit_adds"] and
            int(candidate["zero_attempts"]) == model["zero_attempts"] and
            int(candidate["zero_feasible"]) == model["zero_feasible"] and
            int(candidate["zero_selected"]) == model["zero_selected"] and
            int(plane["zero_attempts"]) == int(plane["zero_selected"]) == 0 and
            int(candidate["fallbacks"]) == model["fallbacks"] == 0 and
            int(candidate["point_entries"]) == baseline_design["entry_counts"][curve] and
            int(candidate["plane_entries"]) == int(candidate["point_entries"]) and
            int(candidate["point_table_bytes"]) == int(plane["point_table_bytes"]) and
            int(candidate["prep_bytes"]) == int(plane["prep_bytes"]) and
            int(candidate["prep_plane_muls"]) == int(candidate["point_entries"]) and
            int(candidate["prep_temp_heap_bytes"]) == int(candidate["point_table_bytes"]) and
            int(candidate["prep_doubles"]) ==
            4 * (baseline_design["curve_positions"][curve] - 1) and
            int(candidate["prep_adds"]) ==
            (14 + sum(bool(x and y) for x, y in selected[curve])) *
            baseline_design["curve_positions"][curve] and
            int(candidate["prep_rotations"]) == 8 * baseline_design["curve_positions"][curve] and
            int(candidate["prep_layer_inversions"]) == 1 and
            int(candidate["static_map_bytes"]) == 1308 and
            int(comb["fallbacks"]) == int(plane["fallbacks"]) == 0)
        for row in current:
            row["gate_pass"] = valid

    passed = len(rows) == 3 * len(inputs["cases"]) and all(row.get("gate_pass") for row in rows)
    report = {"schema": 1, "status": "pass" if passed else "fail",
              "cpu_timing_claim": None, "host_exploratory": True, "isolated_receipt": None,
              "host": {"system": platform.system(), "machine": platform.machine(),
                       "processor": platform.processor()},
              "online_interval": "native 4096-scalar batch computation excluding preparation and independent replay; local timing exploratory",
              "design_sha256": sha256(design_path), "inputs_sha256": sha256(inputs_path),
              "source_sha256": sha256(Path(__file__)),
              "bench_source_sha256": sha256(ROOT / "bench.c"),
              "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
              "ec_tau_header_sha256": sha256(ROOT.parents[1] / "src/ec_tau_internal.h"),
              "map_header_sha256": sha256(ROOT.parents[1] / "src/generated/joint_window4_hot.h"),
              "binary_sha256": sha256(binary), "cmake_cache_sha256": sha256(build_cache),
              "models": models, "rows": rows}
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "rows": len(rows),
                      "scalar_checks": sum(model["scalar_checks"] for model in models),
                      "point_checks": sum(model["point_checks"] for model in models)},
                     sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
