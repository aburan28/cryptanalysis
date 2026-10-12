#!/usr/bin/env python3
"""Freeze the bounded upper-pair table before a new scalar fixture."""

import hashlib
import json
import struct
from pathlib import Path

from make_joint_pair_map import build, unit_actions
from make_joint_pair_top_map import top_sets
from run import representatives


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    pair_path = ROOT / "joint-pair-design.json"
    inputs_path = ROOT / "joint-pair-inputs/inputs.json"
    pair_design = json.loads(pair_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    preferred, reps, _ = build()
    rank = {rep: index for index, rep in enumerate(reps)}
    top = top_sets()
    records = []
    for base in pair_design["records"]:
        curve = base["curve"]
        bound = top[curve]
        top_indices = bound["top_orbits"]
        observed = set()
        checks = 0
        for case in inputs["cases"]:
            if case["curve"]["name"] != curve:
                continue
            scalar_path = inputs_path.parent / case["scalar_file"]
            assert sha256(scalar_path) == case["scalar_file_sha256"]
            for (scalar,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
                _, a, b = min(representatives(base["order"], base["omega_eigen"], scalar),
                              key=lambda candidate: candidate[0])
                x, y = a + b, -b
                for _ in range(base["hex_digit_positions"] - 2):
                    dx, dy = preferred[(x % 16, y % 16)]
                    x, y = (x - dx) // 16, (y - dy) // 16
                assert abs(x) <= bound["top_coordinate_bound"]
                assert abs(y) <= bound["top_coordinate_bound"]
                if x or y:
                    orbit = rank[min(unit_actions(x, y))]
                    assert orbit in top_indices
                    observed.add(orbit)
                checks += 1
        assert checks == 16384
        entries = (base["pair_positions"] - 1) * len(reps) + len(top_indices)
        top_max = bound["top_max_representative_coordinate"]
        top_adds = 2 * (top_max - 1) + sum(
            reps[index][0] != 0 and reps[index][1] != 0 for index in top_indices)
        records.append({"curve": curve, "order": base["order"],
                        "pair_positions": base["pair_positions"],
                        "top_bound_derivation": {
                            "rounded_babai_l1": bound["babai_l1_coordinate_bound"],
                            "coordinate_bounds": bound["bounds_after_each_digit"],
                            "digit_coordinate_bound": 10,
                            "recurrence": "B_next=floor((B+10)/16); radius-2 minimum-L1 is no worse than Babai",
                            "exhaustive_two_digit_pairs": bound["exhaustive_top_coordinate_pairs"],
                            "two_digit_overflows": 0},
                        "top_coordinate_bound": bound["top_coordinate_bound"],
                        "top_orbits": len(top_indices),
                        "top_max_representative_coordinate": top_max,
                        "point_entries": entries,
                        "point_table_bytes": entries * 32,
                        "preparation_adds_model": (base["pair_positions"] - 1) * (
                            2 * 169 + sum(x != 0 and y != 0 for x, y in reps)) + top_adds,
                        "training": {"scalars": checks,
                                     "observed_top_orbits": len(observed),
                                     "full_pair_online_adds": base["training"]["hex_pair_adds"],
                                     "bounded_pair_online_adds": base["training"]["hex_pair_adds"]}})
    design = {
        "schema": 1, "status": "frozen_training_design",
        "scope": "variable-time fixed-base public-scalar multiplication on two exact j=0 study curves",
        "method": "retain the unit-closed pair atlas in every lower position; replace its final full orbit block with the exhaustive subset implied by the GLV Babai L1 bound and two-digit carry recurrence",
        "measurement_gate": "fresh disjoint correctness and operation panel first; CPU ratio only with host-level isolation receipt",
        "base_pair_design_sha256": sha256(pair_path),
        "training_inputs_sha256": sha256(inputs_path),
        "source_sha256": sha256(Path(__file__)),
        "top_map_producer_sha256": sha256(ROOT / "make_joint_pair_top_map.py"),
        "top_map_header_sha256": sha256(REPO / "src/generated/joint_pair_top_map.h"),
        "top_static_bytes": 46176,
        "records": records,
    }
    path = ROOT / "joint-pair-top-design.json"
    path.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"design_sha256": sha256(path), "records": records}, sort_keys=True))


if __name__ == "__main__":
    main()
