#!/usr/bin/env python3
"""Source-formula product screen for the canonical U14 XYZZ evaluator."""

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
    ordinary_products = 10 * mixed  # XYZZ mixed addition: eight M and two S.
    result = {
        "schema": 1,
        "kind": "source-formula-product-screen",
        "cases": len(rows),
        "ordinary_mixed_additions": mixed,
        "unit_rotations": rotations,
        "montgomery_u14_xyzz_products": 36 * ordinary_products + 23 * rotations,
        "canonical_solinas_u14_xyzz_products": 23 * (ordinary_products + rotations),
        "source_comparison_sha256": digest(PAIRED / "comparison.json"),
        "paired_rows_sha256": digest(paired),
        "model_source_sha256": digest(Path(__file__)),
        "scope": "ordinary mixed-addition and unit-rotation field products only",
    }
    assert result["montgomery_u14_xyzz_products"] == 19_357_121
    assert result["canonical_solinas_u14_xyzz_products"] == 12_434_881
    (HERE / "model.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
