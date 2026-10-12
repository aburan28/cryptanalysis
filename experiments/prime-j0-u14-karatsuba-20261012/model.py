#!/usr/bin/env python3
"""Frozen source-product screen for the two-level Karatsuba Solinas mode."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PAIRED = HERE.parent / "prime-j0-u14-u12-paired-20261012"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    comparison = json.loads((PAIRED / "comparison.json").read_text())
    paired = PAIRED / "paired.jsonl"
    assert digest(paired) == comparison["paired_sha256"]
    rows = [json.loads(line) for line in paired.read_text().splitlines()]
    assert len(rows) == comparison["totals"]["cases"] == 4096
    mixed = sum(row["u14_mixed"] for row in rows)
    rotations = sum(row["u14_rotations"] for row in rows)
    assert (mixed, rotations) == (comparison["totals"]["u14_mixed"],
                                  comparison["totals"]["u14_rotations"])
    field_products = 10 * mixed + rotations
    result = {
        "schema": 1,
        "kind": "source-formula-product-screen",
        "cases": len(rows),
        "ordinary_mixed_additions": mixed,
        "unit_rotations": rotations,
        "ordinary_field_products": field_products,
        "schoolbook_wide_limb_products_per_field_product": 16,
        "karatsuba_wide_limb_products_per_field_product": 9,
        "common_fold_constant_products_per_field_product": 7,
        "schoolbook_solinas_limb_products": 23 * field_products,
        "karatsuba_solinas_limb_products": 16 * field_products,
        "paired_rows_sha256": digest(paired),
        "source_comparison_sha256": digest(PAIRED / "comparison.json"),
        "model_source_sha256": digest(Path(__file__)),
        "scope": "ordinary mixed-addition and unit-rotation field products only",
    }
    assert result["schoolbook_solinas_limb_products"] == 12_434_881
    assert result["karatsuba_solinas_limb_products"] == 8_650_352
    (HERE / "model.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
