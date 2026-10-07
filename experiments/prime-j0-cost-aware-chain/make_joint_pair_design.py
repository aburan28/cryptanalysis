#!/usr/bin/env python3
"""Freeze the unit-closed two-window experiment from the previous fixture."""

import hashlib
import json
import struct
from pathlib import Path

from make_joint_pair_map import build
from run import representatives


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recode(x, y, preferred, positions):
    digits = []
    for _ in range(positions):
        dx, dy = preferred[(x % 16, y % 16)]
        digits.append((dx, dy))
        x, y = (x - dx) // 16, (y - dy) // 16
    return digits, x == 0 and y == 0


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
    return digits, x == 0 and y == 0


def pair_adds(digits):
    return sum(any(digit != (0, 0) for digit in digits[i:i + 2])
               for i in range(0, len(digits), 2))


def main():
    training_path = ROOT / "joint-window4-zero-inputs/inputs.json"
    prior_design_path = ROOT / "joint-window4-zero-design.json"
    training = json.loads(training_path.read_text())
    prior = json.loads(prior_design_path.read_text())
    preferred, reps, action = build()
    assert len(reps) == 11061 and len(action) == 65536
    records = []
    for prior_record in prior["records"]:
        curve = prior_record["curve"]
        order = prior_record["order"]
        eigen = prior_record["omega_eigen"]
        positions = 4 if curve == "glv-j0-32" else 8
        counters = {"scalars": 0, "baseline_adds": 0, "baseline_pair_adds": 0,
                    "hex_pair_adds": 0, "baseline_overflows": 0, "hex_overflows": 0,
                    "scalar_identity_checks": 0}
        for case in training["cases"]:
            if case["curve"]["name"] != curve:
                continue
            scalar_file = training_path.parent / case["scalar_file"]
            assert sha256(scalar_file) == case["scalar_file_sha256"]
            for (scalar,) in struct.iter_unpack("<Q", scalar_file.read_bytes()):
                _, a, b = min(representatives(order, eigen, scalar),
                              key=lambda candidate: candidate[0])
                x, y = a + b, -b
                old, old_fits = balanced(x, y, prior_record["positions"])
                digits, fits = recode(x, y, preferred, positions)
                assert sum((dx + eigen * dy) * 16**i
                           for i, (dx, dy) in enumerate(digits)) % order == scalar
                counters["scalars"] += 1
                counters["baseline_adds"] += sum(digit != (0, 0) for digit in old)
                counters["baseline_pair_adds"] += pair_adds(old)
                counters["hex_pair_adds"] += pair_adds(digits)
                counters["baseline_overflows"] += not old_fits
                counters["hex_overflows"] += not fits
                counters["scalar_identity_checks"] += 1
        assert counters["scalars"] == 16384 and counters["hex_overflows"] == 0
        zero_sequences = 256**prior_record["positions"] - 255**prior_record["positions"]
        records.append({"curve": curve, "order": order, "omega_eigen": eigen,
                        "single_window_positions": prior_record["positions"],
                        "pair_positions": positions // 2, "hex_digit_positions": positions,
                        "nonzero_point_entries": (positions // 2) * len(reps),
                        "point_table_bytes": (positions // 2) * len(reps) * 32,
                        "zero_window_coverage_upper_bound": {
                            "digit_strings_with_a_zero": zero_sequences,
                            "fraction_numerator": zero_sequences,
                            "fraction_denominator": order},
                        "training": counters})
    design = {
        "schema": 1,
        "status": "frozen_training_design",
        "scope": "variable-time fixed-base multiplication of public scalars on two exact j=0 study curves",
        "method": "reduce with the existing GLV lattice; recode into a 259-element unit-closed radix-16 Eisenstein alphabet; combine adjacent digits and use one packed two-x point per global six-unit orbit",
        "measurement_gate": "fresh disjoint correctness and operation panel first; CPU ratio only with host-level isolation receipt",
        "base_zero_design_sha256": sha256(prior_design_path),
        "training_inputs_sha256": sha256(training_path),
        "map_producer_sha256": sha256(ROOT / "make_joint_pair_map.py"),
        "map_header_sha256": sha256(REPO / "src/generated/joint_pair_map.h"),
        "source_sha256": sha256(Path(__file__)),
        "alphabet": {"radix": 16, "residue_orbits": 44, "digits": 259,
                     "duplicate_residue_classes": 3, "pair_coefficients": 66367,
                     "pair_orbits_including_identity": len(reps) + 1,
                     "static_map_bytes": 306900,
                     "max_pair_representative_coordinate": 170},
        "records": records,
    }
    path = ROOT / "joint-pair-design.json"
    path.write_text(json.dumps(design, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"design_sha256": sha256(path), "records": records}, sort_keys=True))


if __name__ == "__main__":
    main()
