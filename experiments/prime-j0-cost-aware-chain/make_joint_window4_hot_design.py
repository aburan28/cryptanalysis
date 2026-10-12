#!/usr/bin/env python3
"""Select one unit representative per orbit from frozen training frequencies."""

import hashlib
import json
from pathlib import Path
import struct
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_joint_window4_map import actions, build  # noqa: E402
from run import representatives  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make(inputs_path, old_panel_path, output):
    fixture = json.loads(inputs_path.read_text())
    if fixture.get("status") != "fresh_disjoint_fixture" or len(fixture["cases"]) != 8:
        raise ValueError("expected the frozen eight-case joint-window fixture")
    baseline_design = HERE / "joint-window4-design.json"
    if fixture["design_sha256"] != sha256(baseline_design):
        raise ValueError("joint-window training design changed")
    old = json.loads(old_panel_path.read_text())
    endomorphism = {row["case_id"]: int(row["fields"]["endo_lambda"])
                    for row in old["rows"] if row["mode"] == "pos-compact"}
    canonical, codes = build()
    orbit_rank = {rep: rank for rank, rep in enumerate(canonical)}
    curves = {case["curve"]["name"] for case in fixture["cases"]}
    if curves != {"glv-j0-32", "j0-56"}:
        raise ValueError("unexpected curve panel")
    records = []
    for curve in sorted(curves):
        cases = [case for case in fixture["cases"] if case["curve"]["name"] == curve]
        frequencies = {(x, y): 0 for x in range(-8, 8) for y in range(-8, 8)}
        for case in cases:
            order = case["curve"]["order"]
            omega_eigen = (order - endomorphism[case["id"]]) % order
            scalar_path = inputs_path.parent / case["scalar_file"]
            if sha256(scalar_path) != case["scalar_file_sha256"]:
                raise ValueError("training scalar file changed: " + case["id"])
            for (scalar,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
                _, a, b = min(representatives(order, omega_eigen, scalar),
                              key=lambda item: item[0])
                x, y = a + b, -b
                while x or y:
                    dx, dy = x % 16, y % 16
                    if dx >= 8:
                        dx -= 16
                    if dy >= 8:
                        dy -= 16
                    x, y = (x - dx) // 16, (y - dy) // 16
                    if dx or dy:
                        frequencies[(dx, dy)] += 1

        selected = []
        for rep in canonical:
            orbit = actions(*rep)
            total = sum(frequencies.get(pair, 0) for pair in orbit)
            choices = []
            for candidate in orbit:
                saved = frequencies.get(candidate, 0) + frequencies.get(
                    (-candidate[0], -candidate[1]), 0)
                choices.append((total - saved, candidate))
            best_cost, best_rep = min(choices)
            if best_cost < 0 or min(actions(*best_rep)) != rep:
                raise AssertionError("invalid selected representative")
            selected.append(best_rep)

        baseline_rotations = optimized_rotations = actions_count = 0
        for (x, y), frequency in frequencies.items():
            if not frequency:
                continue
            index = (x + 8) * 16 + y + 8
            orbit = codes[index] & 127
            if orbit_rank[min(actions(x, y))] != orbit:
                raise AssertionError("orbit rank changed")
            baseline_rotations += frequency * ((codes[index] >> 7) % 3 != 0)
            moved = actions(*selected[orbit])
            matches = [code for code, pair in enumerate(moved) if pair == (x, y)]
            if len(matches) != 1:
                raise AssertionError("selected unit action is not unique")
            optimized_rotations += frequency * (matches[0] % 3 != 0)
            actions_count += frequency
        if optimized_rotations > baseline_rotations:
            raise AssertionError("training objective worsened")
        records.append({"curve": curve, "training_cases": [case["id"] for case in cases],
                        "training_scalar_count": sum(case["count"] for case in cases),
                        "training_actions": actions_count,
                        "training_rotations_lex": baseline_rotations,
                        "training_rotations_selected": optimized_rotations,
                        "selected_representatives": [list(pair) for pair in selected]})

    design = {"schema": 1, "status": "frozen_retrospective_design",
              "baseline_design_sha256": sha256(baseline_design),
              "baseline_map_header_sha256": sha256(HERE.parents[1] / "src/generated/joint_window4.h"),
              "training_inputs_sha256": sha256(inputs_path),
              "endomorphism_receipt_sha256": sha256(old_panel_path),
              "source_sha256": sha256(Path(__file__)),
              "orbit_rule": "keep the baseline 71 lexicographic orbit ranks; among six unit representatives choose the one maximizing training frequency of itself and its negative, tie-breaking lexicographically",
              "online_rule": "use the selected representative's unit code for each raw balanced radix-16 digit pair; identical joint-window additions and point count",
              "records": records}
    content = json.dumps(design, indent=2, sort_keys=True).encode() + b"\n"
    if output.exists() and output.read_bytes() != content:
        raise ValueError("frozen representative design changed")
    output.write_bytes(content)
    print(json.dumps({"design_sha256": hashlib.sha256(content).hexdigest(),
                      "records": [{"curve": row["curve"],
                                   "lex_rotations": row["training_rotations_lex"],
                                   "selected_rotations": row["training_rotations_selected"]}
                                  for row in records]}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: make_joint_window4_hot_design.py TRAINING_INPUTS OLD_PANEL OUTPUT")
    make(*map(Path, sys.argv[1:]))
