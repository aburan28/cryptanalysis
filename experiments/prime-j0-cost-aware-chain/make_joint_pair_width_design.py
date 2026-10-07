#!/usr/bin/env python3
"""Freeze two and three-word point formats before fresh scalar inputs."""

import hashlib
import json
import struct
from pathlib import Path

from make_joint_pair_map import build
from run import representatives


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    top_path = ROOT / "joint-pair-top-design.json"
    inputs_path = ROOT / "joint-pair-top-inputs/inputs.json"
    top = json.loads(top_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    preferred, reps, action = build()
    records = []
    for record in top["records"]:
        curve = record["curve"]
        order = record["order"]
        omega = 7702216 if curve == "glv-j0-32" else 52411309604954017
        identity_reps = sum((x + omega * y) % order == 0 for x, y in reps)
        if identity_reps:
            raise AssertionError("the packed pair table contains an identity point")
        counters = {"scalars": 0, "nonzero_pairs": 0, "rotated_pairs": 0,
                    "omega_squared_pairs": 0, "fallbacks": 0}
        for case in inputs["cases"]:
            if case["curve"]["name"] != curve:
                continue
            scalar_path = inputs_path.parent / case["scalar_file"]
            assert sha256(scalar_path) == case["scalar_file_sha256"]
            for (scalar,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
                _, a, b = min(representatives(order, omega, scalar),
                              key=lambda candidate: candidate[0])
                x, y = a + b, -b
                for _ in range(record["pair_positions"]):
                    residues = []
                    for _ in range(2):
                        rx, ry = x % 16, y % 16
                        residues.append((rx << 4) | ry)
                        dx, dy = preferred[(rx, ry)]
                        x, y = (x - dx) // 16, (y - dy) // 16
                    packed = action[(residues[0] << 8) | residues[1]]
                    orbit, code = packed & 16383, packed >> 14
                    if orbit != 16383:
                        counters["nonzero_pairs"] += 1
                        counters["rotated_pairs"] += code % 3 != 0
                        counters["omega_squared_pairs"] += code % 3 == 2
                counters["fallbacks"] += bool(x or y)
                counters["scalars"] += 1
        assert counters["scalars"] == 16384 and counters["fallbacks"] == 0
        slots = record["point_entries"]
        records.append({"curve": curve, "order": order, "omega_eigen": omega,
                        "point_entries": slots, "identity_representatives": identity_reps,
                        "word32_table_bytes": slots * 32,
                        "word24_table_bytes": slots * 24,
                        "word16_table_bytes": slots * 16,
                        "training": counters})
    design = {
        "schema": 1, "status": "frozen_training_design",
        "scope": "variable-time fixed-base public-scalar multiplication on two exact j=0 study curves",
        "method": "retain the proven bounded pair orbit set; compare 24-byte (x,y,beta*x) and 16-byte (x,y) nonidentity point formats against the existing 32-byte (x,y,beta*x,identity) format",
        "field_cost_rule": "24-byte format reconstructs beta^2*x as -(x+beta*x); 16-byte format computes beta*x or beta^2*x by one online field multiplication when the unit action needs it",
        "measurement_gate": "fresh disjoint correctness and operation panel first; CPU ratio only with host-level isolation receipt",
        "base_top_design_sha256": sha256(top_path),
        "training_inputs_sha256": sha256(inputs_path),
        "pair_map_header_sha256": sha256(ROOT.parents[1] / "src/generated/joint_pair_map.h"),
        "top_map_header_sha256": sha256(ROOT.parents[1] /
                                         "src/generated/joint_pair_top_map.h"),
        "source_sha256": sha256(Path(__file__)),
        "records": records,
    }
    path = ROOT / "joint-pair-width-design.json"
    path.write_text(json.dumps(design, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"design_sha256": sha256(path), "records": records}, sort_keys=True))


if __name__ == "__main__":
    main()
