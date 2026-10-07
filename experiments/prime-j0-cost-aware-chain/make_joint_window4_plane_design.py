#!/usr/bin/env python3
"""Freeze the two-x-coordinate unit plane before its held-out fixture."""

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make(output):
    hot_design = HERE / "joint-window4-hot-design.json"
    hot_map = ROOT / "src/generated/joint_window4_hot.h"
    if json.loads(hot_design.read_text()).get("status") != "frozen_retrospective_design":
        raise ValueError("selected-representative design is not frozen")
    design = {
        "schema": 1,
        "status": "frozen_algebraic_design",
        "base_hot_design_sha256": sha256(hot_design),
        "base_hot_map_sha256": sha256(hot_map),
        "base_mode": "joint-window4-hot-pos",
        "candidate_mode": "joint-window4-xplane-pos",
        "table_rule": "for every affine table point (x,y), store the extra Montgomery-field element x_beta=beta*x; retain (x,y) and the same orbit/action map",
        "online_unit_rule": {
            "power_0": "x",
            "power_1": "x_beta",
            "power_2": "-(x+x_beta) mod p",
            "negative_sign": "negate y modulo p",
        },
        "algebraic_invariant": "beta^2+beta+1=0 mod p; in Montgomery representation x_beta2=-(x+x_beta) mod p",
        "online_field_operation_model": {
            "unit_multiplications": 0,
            "power_2_additions": 1,
            "power_2_negations": 1,
        },
        "preparation_field_operation_model": "one extra field multiplication for each finite prepared table point",
        "scope": "variable-time fixed-base multiplication of public scalars on the two exact frozen j=0 curves",
        "measurement_gate": "compare paired release/UBSan correctness first; promote CPU ratios only with host-level isolated receipt",
        "source_sha256": sha256(Path(__file__)),
    }
    content = json.dumps(design, indent=2, sort_keys=True).encode() + b"\n"
    if output.exists() and output.read_bytes() != content:
        raise ValueError("frozen plane design changed")
    output.write_bytes(content)
    print(json.dumps({"design_sha256": hashlib.sha256(content).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_joint_window4_plane_design.py OUTPUT")
    make(Path(sys.argv[1]))
