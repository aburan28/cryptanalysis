#!/usr/bin/env python3
"""Independently model and replay the fresh unit-closed pair-table panel."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
MODES = ("joint-pair-hex-pos", "joint-window4-xplane-pos", "fixed-comb9")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(stdout):
    return dict(part.split("=", 1) for part in stdout.strip().split() if "=" in part)


def run(binary, mode, case, scalar_path):
    point_index = case["id"].rsplit("point", 1)[1]
    result = subprocess.run([str(binary), mode, case["curve"]["name"], point_index,
                             str(scalar_path)], cwd=ROOT.parents[1], capture_output=True,
                            text=True, check=False)
    return {"mode": mode, "case_id": case["id"], "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "fields": parse(result.stdout) if result.returncode == 0 else {}}


def unit_images(pair):
    answer = []
    for sign in (1, -1):
        x, y = sign * pair[0], sign * pair[1]
        for _ in range(3):
            answer.append((x, y))
            x, y = -y, x - y
    return answer


def norm(pair):
    x, y = pair
    return x * x - x * y + y * y


def independent_atlas():
    unseen = {(x, y) for x in range(16) for y in range(16)}
    residue_orbit = {}
    while unseen:
        representative = min(unseen)
        orbit = {(x % 16, y % 16) for x, y in unit_images(representative)}
        for residue in orbit:
            residue_orbit[residue] = representative
        unseen -= orbit
    alphabet = {(0, 0)}
    for orbit in set(residue_orbit.values()) - {(0, 0)}:
        closest = min(((x, y) for x in range(-16, 17) for y in range(-16, 17)
                       if residue_orbit[(x % 16, y % 16)] == orbit),
                      key=lambda pair: (norm(pair), pair))
        alphabet.update(unit_images(closest))
    options = defaultdict(list)
    for digit in alphabet:
        options[(digit[0] % 16, digit[1] % 16)].append(digit)
    preferred = {residue: min(values,
                              key=lambda pair: (norm(pair), abs(pair[0]) + abs(pair[1]), pair))
                 for residue, values in options.items()}
    coefficients = {(a + 16 * c, b + 16 * d)
                    for a, b in alphabet for c, d in alphabet}
    representatives = sorted({min(unit_images(pair)) for pair in coefficients} - {(0, 0)})
    assert len(alphabet) == 259 and len(preferred) == 256
    assert len(coefficients) == 66367 and len(representatives) == 11061
    return preferred, representatives


def balanced(x, y, positions):
    digits = []
    for _ in range(positions):
        dx, dy = x % 16, y % 16
        if dx >= 8:
            dx -= 16
        if dy >= 8:
            dy -= 16
        digits.append((dx, dy))
        x, y = (x - dx) // 16, (y - dy) // 16
    assert x == y == 0
    return digits


def model_case(case, scalar_path, record, preferred, rank, old_rank, selected, point_mul,
               point_add, representatives):
    modulus, curve_b, order = (case["curve"][key] for key in ("p", "b", "order"))
    omega = record["omega_eigen"]
    point = int(case["base_x"]), int(case["base_y"])
    pairs = record["pair_positions"]
    count = adds = unit_adds = old_adds = old_unit_adds = group_checks = 0
    for index, (scalar,) in enumerate(struct.iter_unpack("<Q", scalar_path.read_bytes())):
        _, a, b = min(representatives(order, omega, scalar), key=lambda item: item[0])
        x, y = a + b, -b
        previous = balanced(x, y, record["single_window_positions"])
        for digit in previous:
            if digit == (0, 0):
                continue
            old_adds += 1
            orbit = old_rank[min(unit_images(digit))]
            code = unit_images(selected[orbit]).index(digit)
            old_unit_adds += 2 * (code % 3 == 2)
        terms = []
        for pair_position in range(pairs):
            digits = []
            for _ in range(2):
                digit = preferred[(x % 16, y % 16)]
                digits.append(digit)
                x, y = (x - digit[0]) // 16, (y - digit[1]) // 16
            coefficient = (digits[0][0] + 16 * digits[1][0],
                           digits[0][1] + 16 * digits[1][1])
            terms.append(coefficient)
            if coefficient != (0, 0):
                adds += 1
                rep = min(unit_images(coefficient))
                assert rep in rank
                code = unit_images(rep).index(coefficient)
                unit_adds += 2 * (code % 3 == 2)
        assert x == y == 0
        assert sum((cx + omega * cy) * 256**position
                   for position, (cx, cy) in enumerate(terms)) % order == scalar
        if index < 16 or index % 512 == 0:
            group_sum = None
            for position, (cx, cy) in enumerate(terms):
                if cx or cy:
                    multiple = ((cx + omega * cy) * 256**position) % order
                    group_sum = point_add(group_sum,
                                          point_mul(point, multiple, modulus, curve_b),
                                          modulus, curve_b)
            assert group_sum == point_mul(point, scalar, modulus, curve_b)
            group_checks += 1
        count += 1
    return {"case_id": case["id"], "scalar_checks": count,
            "group_checks": group_checks, "adds": adds, "unit_adds": unit_adds,
            "baseline_adds": old_adds, "baseline_unit_adds": old_unit_adds,
            "fallbacks": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    build_cache = binary.parent / "CMakeCache.txt"
    if not build_cache.is_file():
        parser.error("CMakeCache.txt must sit beside the native binary")
    design_path = ROOT / "joint-pair-design.json"
    inputs_path = ROOT / "joint-pair-inputs/inputs.json"
    design = json.loads(design_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    if inputs["design_sha256"] != sha256(design_path) or \
            inputs.get("source_sha256") != sha256(ROOT / "make_joint_pair_inputs.py") or \
            len(inputs.get("prior_manifest_sha256", {})) != 12 or \
            design["map_header_sha256"] != sha256(ROOT.parents[1] /
                                                   "src/generated/joint_pair_map.h"):
        parser.error("frozen pair design or map changed")
    excluded = {"glv-j0-32": set(), "j0-56": set()}
    for name, expected_hash in inputs["prior_manifest_sha256"].items():
        prior_path = ROOT / name
        if sha256(prior_path) != expected_hash:
            parser.error("prior manifest changed: " + name)
        for prior_case in json.loads(prior_path.read_text())["cases"]:
            prior_file = prior_path.parent / prior_case["scalar_file"]
            if sha256(prior_file) != prior_case["scalar_file_sha256"]:
                parser.error("prior scalar file changed: " + name)
            excluded[prior_case["curve"]["name"]].update(
                value for (value,) in struct.iter_unpack("<Q", prior_file.read_bytes()))
    for case in inputs["cases"]:
        curve = case["curve"]["name"]
        scalar_path = inputs_path.parent / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            parser.error("new scalar file changed: " + case["id"])
        for (value,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
            if value >= case["curve"]["order"] or value in excluded[curve]:
                parser.error("new fixture is not disjoint: " + case["id"])
            excluded[curve].add(value)
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
    records = {row["curve"]: row for row in design["records"]}
    rows, models = [], []
    for index, case in enumerate(inputs["cases"]):
        scalar_path = inputs_path.parent / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            parser.error("frozen scalar file changed: " + case["id"])
        curve = case["curve"]["name"]
        record = records[curve]
        model = model_case(case, scalar_path, record, preferred, rank, old_rank,
                           selected[curve], point_mul, point_add, representatives)
        models.append(model)
        rotated = MODES[index % 3:] + MODES[:index % 3]
        current = [run(binary, mode, case, scalar_path) for mode in rotated]
        rows.extend(current)
        if any(row["exit_code"] or row["fields"].get("verified") != "1" for row in current):
            continue
        fields = {row["mode"]: row["fields"] for row in current}
        candidate, plane, comb = (fields[mode] for mode in MODES)
        shared = ("curve", "point_index", "count", "base_x", "base_y", "endo_lambda",
                  "input_digest", "output_digest")
        expected_prep_adds = record["pair_positions"] * (
            2 * 169 + sum(x != 0 and y != 0 for x, y in pair_reps))
        valid = (
            all(candidate.get(key) == control.get(key) for control in (comb, plane)
                for key in shared) and
            candidate["curve"] == curve and candidate["count"] == str(case["count"]) and
            candidate["base_x"] == case["base_x"] and
            candidate["base_y"] == case["base_y"] and
            int(candidate["adds"]) == model["adds"] and
            int(candidate["unit_adds"]) == model["unit_adds"] and
            int(plane["adds"]) == model["baseline_adds"] and
            int(plane["unit_adds"]) == model["baseline_unit_adds"] and
            int(candidate["fallbacks"]) == model["fallbacks"] == 0 and
            int(plane["fallbacks"]) == int(comb["fallbacks"]) == 0 and
            int(candidate["point_entries"]) == record["nonzero_point_entries"] and
            int(candidate["point_table_bytes"]) == record["point_table_bytes"] and
            int(candidate["plane_entries"]) == record["nonzero_point_entries"] and
            int(candidate["static_map_bytes"]) == design["alphabet"]["static_map_bytes"] and
            int(candidate["prep_doubles"]) == 8 * (record["pair_positions"] - 1) and
            int(candidate["prep_adds"]) == expected_prep_adds and
            int(candidate["prep_layer_inversions"]) == record["pair_positions"] and
            int(candidate["prep_plane_muls"]) == record["nonzero_point_entries"] and
            int(candidate["prep_temp_heap_bytes"]) == 64 * len(pair_reps) and
            int(candidate["prep_temp_stack_bytes"]) == 2 * 171 * 24)
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
              "map_producer_sha256": sha256(ROOT / "make_joint_pair_map.py"),
              "map_header_sha256": sha256(ROOT.parents[1] / "src/generated/joint_pair_map.h"),
              "bench_source_sha256": sha256(ROOT / "bench.c"),
              "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
              "ec_tau_header_sha256": sha256(ROOT.parents[1] / "src/ec_tau_internal.h"),
              "binary_sha256": sha256(binary), "cmake_cache_sha256": sha256(build_cache),
              "models": models, "rows": rows}
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "rows": len(rows),
                      "scalar_checks": sum(model["scalar_checks"] for model in models),
                      "group_checks": sum(model["group_checks"] for model in models)},
                     sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
