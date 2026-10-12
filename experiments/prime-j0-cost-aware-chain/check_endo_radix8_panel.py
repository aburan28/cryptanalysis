#!/usr/bin/env python3
"""Independently model and replay a held-out signed-radix native panel."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
MODES = ("endo-radix8-pos", "fixed-comb9", "tau3-scatter-atlas-pos")


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


def model_case(case, scalar_path, positions, omega_eigen):
    sys.path[:0] = [str(ROOT), str(ROOT.parents[1])]
    from run import representatives, point_add, point_mul

    modulus, curve_b, order = (case["curve"][key] for key in ("p", "b", "order"))
    point = int(case["base_x"]), int(case["base_y"])
    model_adds = model_rotations = scalar_checks = point_checks = fallbacks = 0
    for index, (scalar,) in enumerate(struct.iter_unpack("<Q", scalar_path.read_bytes())):
        _, a, b = min(representatives(order, omega_eigen, scalar), key=lambda item: item[0])
        coordinates = (a + b, -b)
        assert (coordinates[0] + omega_eigen * coordinates[1] - scalar) % order == 0
        reconstructed = 0
        group_sum = None
        check_group = index < 16 or index % 512 == 0
        for axis, coordinate in enumerate(coordinates):
            position = 0
            while coordinate:
                remainder = coordinate % 256
                digit = remainder - 256 if remainder >= 128 else remainder
                coordinate = (coordinate - digit) // 256
                reconstructed += digit * 256**position * (omega_eigen if axis else 1)
                if digit:
                    model_adds += 1
                    model_rotations += axis
                    if check_group:
                        term = point_mul(point,
                                         (digit * 256**position *
                                          (omega_eigen if axis else 1)) % order,
                                         modulus, curve_b)
                        group_sum = point_add(group_sum, term, modulus, curve_b)
                position += 1
            fallbacks += position > positions
        assert (reconstructed - scalar) % order == 0
        scalar_checks += 1
        if check_group:
            assert group_sum == point_mul(point, scalar, modulus, curve_b)
            point_checks += 1
    return {"adds": model_adds, "rotations": model_rotations,
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
    inputs_path = ROOT / "endo-radix8-inputs/inputs.json"
    design_path = ROOT / "endo-radix8-design.json"
    inputs = json.loads(inputs_path.read_text())
    design = json.loads(design_path.read_text())
    if inputs["design_sha256"] != sha256(design_path):
        parser.error("frozen design changed")
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
        model = model_case(case, scalar_path, design["curve_positions"][curve], omega_eigen)
        model["case_id"] = case["id"]
        models.append(model)
        rotated = MODES[index % 3:] + MODES[:index % 3]
        current = [run(binary, mode, case, scalar_path) for mode in rotated]
        rows.extend(current)
        if any(row["exit_code"] or row["fields"].get("verified") != "1" for row in current):
            continue
        fields = {row["mode"]: row["fields"] for row in current}
        candidate, comb, scatter = (fields[mode] for mode in MODES)
        shared = ("curve", "point_index", "count", "base_x", "base_y",
                  "endo_lambda", "input_digest", "output_digest")
        valid = (
            all(candidate.get(key) == control.get(key) for control in (comb, scatter)
                for key in shared) and
            candidate["curve"] == curve and candidate["count"] == str(case["count"]) and
            candidate["base_x"] == case["base_x"] and
            candidate["base_y"] == case["base_y"] and
            int(candidate["adds"]) == model["adds"] and
            int(candidate["rotations"]) == model["rotations"] and
            int(candidate["fallbacks"]) == model["fallbacks"] == 0 and
            int(candidate["point_entries"]) == design["table_entries"][curve] and
            int(candidate["prep_doubles"]) ==
            8 * (design["curve_positions"][curve] - 1) and
            int(candidate["prep_adds"]) == 127 * design["curve_positions"][curve] and
            int(candidate["prep_layer_inversions"]) == 1 and
            int(comb["fallbacks"]) == int(scatter["fallbacks"]) == 0)
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
