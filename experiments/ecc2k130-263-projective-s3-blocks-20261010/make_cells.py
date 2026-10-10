#!/usr/bin/env python3
"""Compose exactly partitioned leaf/intermediate SAT controls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import common


ref = common.ref


def exact_units(mode, inputs, choice, witness):
    if mode not in ("intermediate_free", "leaf_free"):
        raise ValueError("unknown control mode")
    bits = []
    for index, leaf in enumerate(witness["leaves"]):
        common.parent_cells.word(bits, f"s{index}", leaf["mask"],
                                 24, inputs)
        if mode == "intermediate_free":
            x, z, _ = ref.leaf(leaf["mask"], witness["alpha"])
            if (leaf["raw_point_normalized"][0] != x
                    or leaf["z"] != z):
                raise ValueError("parent leaf witness changed")
            common.parent_cells.word(bits, f"x{index}", x,
                                     ref.DEGREE, inputs)
            common.parent_cells.word(bits, f"z{index}", z,
                                     ref.DEGREE, inputs)
    if mode == "leaf_free":
        for index, point in enumerate(witness["intermediates"]):
            common.parent_cells.word(bits, f"t{index}", point["x"],
                                     ref.DEGREE, inputs)
            bits.append((inputs[f"f:{index}"], int(point["finite"])))
    for bit, variable in enumerate(choice):
        bits.append((variable, 0))
    if len({literal for literal, _ in bits}) != len(bits):
        raise ValueError("duplicate fixed input variable")
    units = sorted(literal if value else -literal
                   for literal, value in bits)
    if len(units) != (1718 if mode == "intermediate_free" else 674):
        raise ValueError("unit count differs from frozen protocol")
    return units


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=("source", "descendant_native"),
                        required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    config, parent_config, _ = common.load_config()
    witness, build, base, inputs, base_row = common.parent_inputs(
        args.policy, config, parent_config)
    choice = build["target_selector_variables"]
    prepared = {mode: exact_units(mode, inputs, choice, witness)
                for mode in config["modes"]}
    parent_positive = set(common.parent_cells.exact_units(
        args.policy, "positive", inputs, choice, witness))
    parent_mask_only = set(common.parent_cells.exact_units(
        args.policy, "free", inputs, choice, witness))
    if (set(prepared["intermediate_free"])
            | set(prepared["leaf_free"])) != parent_positive:
        raise ValueError("released blocks do not cover positive control")
    if (set(prepared["intermediate_free"])
            & set(prepared["leaf_free"])) != parent_mask_only:
        raise ValueError("released blocks do not meet at mask-only control")
    cells = {}
    for mode in config["modes"]:
        prefix = args.out_dir / (args.policy + "_" + mode)
        delta = prefix.with_suffix(".units.txt")
        formula = prefix.with_suffix(".xcnf")
        if delta.exists() or formula.exists():
            parser.error("refusing to overwrite SAT input")
        delta.parent.mkdir(parents=True, exist_ok=True)
        units = prepared[mode]
        delta.write_text("".join(f"{literal} 0\n" for literal in units))
        vars_, total, count = common.parent_audit.compose_cell(
            base, delta.read_bytes(), formula)
        cells[mode] = {
            "unit_count": count,
            "unit_delta_sha256": ref.sha(delta),
            "xcnf_sha256": ref.sha(formula),
            "xcnf_bytes": formula.stat().st_size,
            "vars": vars_,
            "total_constraints": total,
            "selected_target_choice": 0,
        }
    result = {
        "schema": "ecc2k130-263-projective-s3-search-block-cells-v1",
        "status": "PASS_EXACT_INPUT_PARTITION",
        "policy": args.policy,
        "config_sha256": ref.sha(common.HERE / "CONFIG.json"),
        "common_source_sha256": ref.sha(common.HERE / "common.py"),
        "producer_sha256": ref.sha(Path(__file__)),
        "parent_base_raw_sha256": base_row["raw_sha256"],
        "parent_base_gzip_sha256": base_row["gzip_sha256"],
        "parent_base_receipt_sha256": ref.sha(
            common.PARENT / "runs/R1" / (args.policy + "_control_base.json")),
        "parent_input_vars_sha256": ref.sha(
            common.PARENT / "runs/R1" /
            (args.policy + "_control_base.inputs.json")),
        "parent_positive_unit_delta_sha256": ref.sha(
            common.PARENT / "runs/R1" / (args.policy + "_positive.units.txt")),
        "parent_mask_only_unit_delta_sha256": ref.sha(
            common.PARENT / "runs/R1" / (args.policy + "_free.units.txt")),
        "cells": cells,
    }
    out = args.out_dir / (args.policy + "_cells.json")
    common.write_json(out, result)
    print(json.dumps({"policy": args.policy, "status": result["status"],
                      "units": {m: c["unit_count"] for m, c in cells.items()}},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
