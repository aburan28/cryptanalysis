#!/usr/bin/env python3
"""Count a field-linear factorization of the free-selector identity encoding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = ROOT / "experiments/ecc2k130-263-native-w24-m6-20261010"
PARENT = ROOT / "experiments/ecc2k130-263-selector-cut-20261010"
sys.path.insert(0, str(NATIVE))
import field as ref  # noqa: E402
sys.path.insert(0, str(HERE))
import experiment as gate  # noqa: E402


def counts(alpha: int):
    direct = sum(ref.multiply(alpha, ref.reduce(1 << (i+j))).bit_count()
                 for i in range(ref.DEGREE) for j in range(ref.DEGREE))
    linear = sum(ref.multiply(alpha, 1 << i).bit_count()
                 for i in range(ref.DEGREE))
    factored_product = sum(ref.reduce(1 << (i+j)).bit_count()
                           for i in range(ref.DEGREE) for j in range(ref.DEGREE))
    rhs = sum(ref.reduce(1 << (2*i)).bit_count()
              for i in range(ref.DEGREE))
    return {"direct_product_xor_literals": direct,
            "factored_linear_map_xor_literals": linear,
            "factored_product_xor_literals": factored_product,
            "rhs_square_xor_literals": rhs,
            "factored_product_plus_map_ratio_decimal":
                format(direct / (linear + factored_product), ".8f"),
            "direct_and_variables": ref.DEGREE**2,
            "factored_and_variables": ref.DEGREE**2,
            "factored_extra_linear_variables": ref.DEGREE,
            "factored_extra_linear_xors": ref.DEGREE}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    gate.config()
    masks_path = PARENT / "runs/R1/masks.json"
    masks = gate.read(masks_path)["masks"]
    if len(masks) != 8:
        raise ValueError("frozen common-mask panel changed")
    rows = {}
    for policy in gate.POLICIES:
        alpha, _ = ref.coefficients(policy)
        arithmetic = []
        for row in masks:
            x = row["curves"][policy]["x"]
            z = row["curves"][policy]["z"]
            direct = ref.multiply(alpha, ref.multiply(x, z))
            factored = ref.multiply(ref.multiply(alpha, x), z)
            rhs = ref.square(x ^ alpha)
            if direct != factored or direct != rhs:
                raise ArithmeticError("factored identity fails frozen mask")
            arithmetic.append(row["mask"])
        rows[policy] = {"alpha": alpha, "alpha_bit_weight": alpha.bit_count(),
                        **counts(alpha), "checked_frozen_masks": arithmetic}
    result = {
        "schema": "ecc2k130-free-identity-factorization-model-v1",
        "status": "PASS_EXACT_LITERAL_COUNTS_AND_16_ARITHMETIC_CHECKS",
        "classification": "analytical_encoding_size_only; no solver run",
        "source_sha256": gate.sha(HERE / "source.json"),
        "field_source_sha256": gate.sha(NATIVE / "field.py"),
        "masks_sha256": gate.sha(masks_path),
        "model_source_sha256": gate.sha(Path(__file__)),
        "rows": rows}
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    path = gate.RUN / "factorization_model.json"
    if args.write:
        if path.exists() and path.read_text() != content:
            raise ValueError("model receipt changed")
        if not path.exists():
            path.write_text(content)
    print(json.dumps({"status": result["status"],
                      "rows": {key: rows[key]["factored_product_plus_map_ratio_decimal"]
                               for key in rows}}, sort_keys=True))


if __name__ == "__main__":
    main()
