#!/usr/bin/env python3
"""Check projective Boolean roots on archived n131 cancellation witnesses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import build_projective as circuit
import binary_group as group


HERE = Path(__file__).resolve().parent
ref = group.f


def assign_word(assignments, name, value, width=ref.DEGREE):
    for bit in range(width):
        assignments[(name, bit)] = (value >> bit) & 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite Boolean control")
    started = time.perf_counter()
    small = ref.read(HERE / "runs/R1/small_field.json")
    control = ref.read(HERE / "runs/R1/exceptional_group.json")
    if (small["status"] != "PASS_EXHAUSTIVE_GROUP_LAW_EQUIVALENCE"
            or control["status"]
            != "PASS_TWO_N131_CANCELLATION_GROUP_CONTROLS"
            or control["source_sha256"] != ref.sha(HERE / "exceptional_control.py")
            or control["binary_group_source_sha256"]
            != ref.sha(HERE / "binary_group.py")):
        raise ValueError("small-field or checked-Sage control missing")
    results = {}
    for policy in circuit.POLICIES:
        witness = control["policies"][policy]
        prog, roots, _, _ = circuit.build_ir(policy)
        assignments = {("one", 0): 1}
        assign_word(assignments, "target", witness["target_x"])
        for index, leaf in enumerate(witness["leaves"]):
            x, z, _ = ref.leaf(leaf["mask"], witness["alpha"])
            if (leaf["raw_point_normalized"][0] != x
                    or leaf["z"] != z):
                raise ArithmeticError("leaf is not in frozen W24 base")
            assign_word(assignments, "s%d" % index, leaf["mask"], 24)
            assign_word(assignments, "x%d" % index, x)
            assign_word(assignments, "z%d" % index, z)
        for index, point in enumerate(witness["intermediates"]):
            assign_word(assignments, "t%d" % index, point["x"])
            assignments[("f", index)] = int(point["finite"])
        if any(prog.evaluate(assignments, roots)):
            raise ArithmeticError("valid cancellation fails projective circuit")
        negatives = {}
        for name, bit in (("f", 0), ("t0", 0), ("z0", 0),
                          ("target", 0)):
            changed = dict(assignments)
            changed[(name, bit)] ^= 1
            if not any(prog.evaluate(changed, roots)):
                raise ArithmeticError("mutation accepted: " + name)
            negatives[name] = "rejected"
        results[policy] = {"positive_roots_zero": True,
                           "first_pair_is_infinity": True,
                           "mutations": negatives,
                           "ir_operations": prog.opCount(roots)}
    result = {
        "schema": "ecc2k130-263-projective-s3-boolean-control-v1",
        "status": "PASS_SOURCE_AND_DESCENDANT_EXCEPTIONAL_BOOLEAN_CONTROLS",
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "small_field_sha256": ref.sha(HERE / "runs/R1/small_field.json"),
        "group_control_sha256": ref.sha(HERE / "runs/R1/exceptional_group.json"),
        "builder_sha256": ref.sha(HERE / "build_projective.py"),
        "source_sha256": ref.sha(Path(__file__)),
        "policies": results,
        "wall_seconds": time.perf_counter()-started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"],
                      "wall_seconds": result["wall_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
