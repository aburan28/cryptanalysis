#!/usr/bin/env python3
"""Evaluate both balanced m6 Boolean programs on archived point controls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import build_formula as circuit
import field as ref


def assign_word(assignments, name, value, width=ref.DEGREE):
    for bit in range(width):
        assignments[(name, bit)] = (value >> bit) & 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite Boolean control receipt")
    started = time.perf_counter()
    verified = ref.read(ref.HERE / "runs/R1/verification.json")
    geometry = ref.read(ref.HERE / "runs/R1/geometry_controls.json")
    if (verified["status"]
            != "PASS_TWO_CURVES_FOUR_LIFTS_AND_M6_CONTROLS"
            or verified["geometry_controls_sha256"]
            != ref.sha(ref.HERE / "runs/R1/geometry_controls.json")):
        raise ValueError("independent geometry replay missing")
    results = {}
    for policy in circuit.POLICIES:
        entry = geometry[policy]
        prog, roots, _, _ = circuit.build_ir(policy, "m6")
        assignments = {("one", 0): 1}
        assign_word(assignments, "target", entry["target_x"])
        for index, row in enumerate(entry["leaves"]):
            assign_word(assignments, "s%d" % index, row["mask"], 24)
            assign_word(assignments, "x%d" % index, row["raw_point"][0])
            assign_word(assignments, "z%d" % index, row["z"])
        for index, value in enumerate(entry["intermediate_x"]):
            assign_word(assignments, "t%d" % index, value)
        if any(prog.evaluate(assignments, roots)):
            raise ArithmeticError("positive control fails Boolean circuit")
        negatives = {}
        for name in ("x0", "z0", "target"):
            altered = dict(assignments)
            altered[(name, 0)] ^= 1
            if not any(prog.evaluate(altered, roots)):
                raise ArithmeticError("single-bit mutation was accepted: " + name)
            negatives[name] = "rejected"
        results[policy] = {"positive_roots_zero": True,
                           "mutations": negatives,
                           "ir_operations": prog.opCount(roots),
                           "leaf_masks": [row["mask"] for row in entry["leaves"]]}
    receipt = {
        "schema": "ecc2k130-263-native-w24-boolean-controls-v1",
        "status": "PASS_TWO_POSITIVE_AND_SIX_NEGATIVE_IR_CONTROLS",
        "config_sha256": ref.sha(ref.HERE / "CONFIG.json"),
        "geometry_verification_sha256": ref.sha(
            ref.HERE / "runs/R1/verification.json"),
        "geometry_controls_sha256": ref.sha(
            ref.HERE / "runs/R1/geometry_controls.json"),
        "circuit_source_sha256": ref.sha(ref.HERE / "build_formula.py"),
        "field_source_sha256": ref.sha(ref.HERE / "field.py"),
        "source_sha256": ref.sha(Path(__file__)),
        "policies": results,
        "wall_seconds": time.perf_counter()-started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": receipt["status"],
                      "wall_seconds": receipt["wall_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
