#!/usr/bin/env python3
"""Certify an exact center guard before the five-neighbor L1 search."""

import hashlib
import json
from pathlib import Path
import struct

from make_joint_pair_five_design import AXIAL, certificate, reduce
from run import lattice, nearest_quotient


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guard_thresholds(b1, b2):
    tx = abs(b2[0]) - abs(b2[1])
    ty = abs(b1[1]) - abs(b1[0])
    if tx <= 0 or ty <= 0:
        raise ValueError("basis has no positive dominant-coordinate guard")
    return tx, ty


def guarded_reduce(k, b1, b2, det):
    u0 = nearest_quotient(k * b2[1], det)
    v0 = nearest_quotient(-k * b1[1], det)
    x = k - u0 * b1[0] - v0 * b2[0]
    y = -u0 * b1[1] - v0 * b2[1]
    tx, ty = guard_thresholds(b1, b2)
    if 2 * abs(x) < tx and 2 * abs(y) < ty:
        return (abs(x) + abs(y), x, y, 0, 0), True
    return reduce(k, b1, b2, det, AXIAL), False


def main():
    five_path = ROOT / "joint-pair-five-design.json"
    inputs_path = ROOT / "joint-pair-five-inputs/inputs.json"
    panel_path = ROOT / "joint-pair-five-native-panel.json"
    five = json.loads(five_path.read_text())
    inputs = json.loads(inputs_path.read_text())
    panel = json.loads(panel_path.read_text())
    if five.get("status") != "frozen_proved_design" or \
            inputs.get("design_sha256") != sha256(five_path) or \
            panel.get("status") != "pass" or \
            panel.get("inputs_sha256") != sha256(inputs_path) or \
            len(panel.get("rows", [])) != 80:
        raise ValueError("five-neighbor training custody changed")
    records = []
    for prior in five["records"]:
        curve = prior["curve"]
        b1, b2, det = lattice(prior["order"], prior["omega_eigen"])
        if [list(b1), list(b2)] != prior["basis"] or det != prior["determinant"] or \
                certificate(b1, b2, det) != prior["certificate"]:
            raise ValueError("prior lattice certificate changed")
        tx, ty = guard_thresholds(b1, b2)
        cases = [case for case in inputs["cases"] if case["curve"]["name"] == curve]
        if len(cases) != 4:
            raise ValueError("training cases changed")
        accepted = fallback_center = total = 0
        for case in cases:
            scalar_path = inputs_path.parent / case["scalar_file"]
            if sha256(scalar_path) != case["scalar_file_sha256"]:
                raise ValueError("training scalar custody changed")
            for (k,) in struct.iter_unpack("<Q", scalar_path.read_bytes()):
                candidate, fast = guarded_reduce(k, b1, b2, det)
                control = reduce(k, b1, b2, det, AXIAL)
                if candidate != control:
                    raise ValueError("center guard changed representative")
                accepted += fast
                fallback_center += not fast and control[3:] == (0, 0)
                total += 1
        records.append({"curve": curve, "order": prior["order"],
                        "omega_eigen": prior["omega_eigen"],
                        "basis": prior["basis"], "determinant": det,
                        "short_vector_certificate": prior["certificate"],
                        "horizontal_threshold_strict": tx,
                        "vertical_threshold_strict": ty,
                        "training_scalars": total,
                        "training_center_guard_accepted": accepted,
                        "training_fallback_center": fallback_center})
    design = {"schema": 1, "status": "frozen_proved_design",
              "method": "accept rounded center when both dominant-coordinate inequalities are strict; otherwise run the certified five-neighbor reducer",
              "proof": "For each sign, ||R ± b1||_1 >= |Rx|-|b1x|+|b1y|-|Ry| > ||R||_1 if 2|Ry|<|b1y|-|b1x|. Similarly both signs of b2 lose when 2|Rx|<|b2x|-|b2y|. The prior certificate excludes all other lattice translations. Strict inequalities preserve the prior tie order.",
              "scope": "variable-time public-scalar GLV reduction on two exact j=0 study curves",
              "measurement_gate": "fresh disjoint correctness and operation panel first; CPU timing only with a host-level isolation receipt",
              "base_five_design_sha256": sha256(five_path),
              "training_inputs_sha256": sha256(inputs_path),
              "training_panel_sha256": sha256(panel_path),
              "source_sha256": sha256(Path(__file__)), "records": records}
    output = ROOT / "joint-pair-guard-design.json"
    content = (json.dumps(design, sort_keys=True, indent=2) + "\n").encode()
    if output.exists() and output.read_bytes() != content:
        raise ValueError("frozen center-guard design changed")
    output.write_bytes(content)
    print(json.dumps({"design_sha256": sha256(output), "records": records}, sort_keys=True))


if __name__ == "__main__":
    main()
