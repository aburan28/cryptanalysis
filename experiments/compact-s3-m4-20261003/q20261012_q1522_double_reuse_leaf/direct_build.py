#!/usr/bin/env python3
"""Build the direct-output two-product variant on frozen Q1513 inputs."""
import json
from pathlib import Path

import build
import direct_leaf

HERE = Path(__file__).resolve().parent


def main():
    p = build.read(HERE / "direct_protocol.json")
    assert build.sha(HERE / "direct_leaf.py") == p["direct_leaf_source_sha256"]
    assert build.sha(HERE / "build_receipt.json") == p["inverse_variant_build_sha256"]
    assert not (HERE / "direct_build_receipt.json").exists()
    folder = HERE / "direct_formulas"
    folder.mkdir()
    rows = []
    for label in p["inputs"]:
        item = p["inputs"][label]
        original = build.parent.projected_sparse_leaf
        try:
            build.parent.projected_sparse_leaf = direct_leaf.projected_sparse_leaf_direct
            formula, raw, _, _ = build.parent.build(83, item["complement_x_coords"])
        finally:
            build.parent.projected_sparse_leaf = original
        for bits, value in zip(raw, item["pin_raw"]):
            build.parent.pin_bits(formula, bits, value)
        path = folder / f"{label}.xcnf"
        formula.write(path)
        rows.append({"label": label, "formula_sha256": build.sha(path),
                     "variables": formula.variables,
                     "cnf_clauses": len(formula.clauses),
                     "xor_rows": len(formula.xors)})
    build.save(HERE / "direct_build_receipt.json", {
        "proposal_id": "Q1522", "variant": "direct_two_product",
        "protocol_sha256": build.sha(HERE / "direct_protocol.json"),
        "source_sha256": build.sha(Path(__file__)), "rows": rows})
    for row in rows:
        print(row["label"], row["variables"], row["cnf_clauses"], row["xor_rows"])


if __name__ == "__main__":
    main()
