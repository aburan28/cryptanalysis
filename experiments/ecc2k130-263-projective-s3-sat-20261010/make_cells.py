#!/usr/bin/env python3
"""Freeze unit deltas and exact SAT inputs from one control-base XCNF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_control as circuit


HERE = Path(__file__).resolve().parent
PARENT = circuit.PARENT
ref = circuit.ref


def word(bits, name, value, width, input_vars):
    for bit in range(width):
        bits.append((input_vars[f"{name}:{bit}"], (value >> bit) & 1))


def exact_units(policy, mode, input_vars, choice, witness):
    bits = []
    for index, leaf in enumerate(witness["leaves"]):
        word(bits, f"s{index}", leaf["mask"], 24, input_vars)
        if mode != "free":
            x, z, _ = ref.leaf(leaf["mask"], witness["alpha"])
            if (leaf["raw_point_normalized"][0] != x
                    or leaf["z"] != z):
                raise ValueError("leaf coordinate differs from checked witness")
            word(bits, f"x{index}", x, ref.DEGREE, input_vars)
            word(bits, f"z{index}", z, ref.DEGREE, input_vars)
    if mode != "free":
        for index, point in enumerate(witness["intermediates"]):
            word(bits, f"t{index}", point["x"], ref.DEGREE, input_vars)
            bits.append((input_vars[f"f:{index}"], int(point["finite"])))
    selected = int(mode == "negative")
    for bit, variable in enumerate(choice):
        bits.append((variable, (selected >> bit) & 1))
    if len({literal for literal, _ in bits}) != len(bits):
        raise ValueError("duplicate fixed input variable")
    return sorted((literal if value else -literal) for literal, value in bits)


def compose(base_path, unit_path, out_path, units):
    with base_path.open("rb") as source, out_path.open("xb") as dest:
        header = source.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("invalid base XCNF header")
        vars_, clauses = map(int, header[2:])
        dest.write(f"p cnf {vars_} {clauses + len(units)}\n".encode())
        for chunk in iter(lambda: source.read(1 << 20), b""):
            dest.write(chunk)
        with unit_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                dest.write(chunk)
    return vars_, clauses + len(units)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=circuit.parent.POLICIES, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    config = ref.read(HERE / "CONFIG.json")
    witness, _ = circuit.check_parent(args.policy, config)
    stem = args.out_dir / (args.policy + "_control_base")
    base_path = stem.with_suffix(".xcnf")
    base_receipt = ref.read(stem.with_suffix(".json"))
    build_guard = ref.read(stem.with_suffix(".build_guard.json"))
    input_path = stem.with_suffix(".inputs.json")
    input_vars = ref.read(input_path)
    if (base_receipt["status"] != "CONTROL_FORMULA_BUILT"
            or base_receipt["formula_sha256"] != ref.sha(base_path)
            or base_receipt["input_vars_sha256"] != ref.sha(input_path)
            or base_receipt["builder_sha256"] != ref.sha(HERE / "build_control.py")
            or build_guard["status"]
            != "PASS_CONTROL_FORMULA_BUILT_WITH_EXTERNAL_GUARD"
            or build_guard["formula_sha256"] != ref.sha(base_path)):
        raise ValueError("control base or external build guard changed")
    choice = base_receipt["target_selector_variables"]
    cells = {}
    for mode in ("positive", "negative", "free"):
        prefix = args.out_dir / (args.policy + "_" + mode)
        delta_path = prefix.with_suffix(".units.txt")
        formula_path = prefix.with_suffix(".xcnf")
        if delta_path.exists() or formula_path.exists():
            parser.error("refusing to overwrite SAT cell")
        units = exact_units(args.policy, mode, input_vars, choice, witness)
        delta_path.write_text("".join(f"{unit} 0\n" for unit in units))
        vars_, clauses = compose(base_path, delta_path, formula_path, units)
        cells[mode] = {
            "unit_count": len(units),
            "selected_target_choice": int(mode == "negative"),
            "unit_delta_sha256": ref.sha(delta_path),
            "xcnf_sha256": ref.sha(formula_path),
            "xcnf_bytes": formula_path.stat().st_size,
            "vars": vars_,
            "total_constraints": clauses,
        }
    result = {
        "schema": "ecc2k130-263-projective-s3-sat-cells-v1",
        "status": "PASS_THREE_EXACT_SAT_INPUTS",
        "policy": args.policy,
        "base_xcnf_sha256": ref.sha(base_path),
        "base_receipt_sha256": ref.sha(stem.with_suffix(".json")),
        "build_guard_sha256": ref.sha(stem.with_suffix(".build_guard.json")),
        "input_vars_sha256": ref.sha(input_path),
        "group_witness_sha256": ref.sha(PARENT / "runs/R1/exceptional_group.json"),
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "producer_sha256": ref.sha(Path(__file__)),
        "cells": cells,
    }
    out = args.out_dir / (args.policy + "_cells.json")
    if out.exists():
        parser.error("refusing to overwrite cell receipt")
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"policy": args.policy, "status": result["status"],
                      "cells": {m: c["unit_count"] for m, c in cells.items()}},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
