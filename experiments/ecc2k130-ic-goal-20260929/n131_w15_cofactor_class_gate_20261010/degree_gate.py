#!/usr/bin/env python3
"""Certify low-degree polynomial impossibility on the usable W15 masks."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gate(masks, values, degree):
    monomials = sorted((mask for mask in range(1 << 15)
                        if mask.bit_count() <= degree),
                       key=lambda mask: (mask.bit_count(), mask))
    indices = {mask: i for i, mask in enumerate(monomials)}
    width = len(monomials)
    basis = {}
    for row_index, mask in enumerate(masks):
        row = 0
        sub = mask
        while True:
            index = indices.get(sub)
            if index is not None:
                row |= 1 << index
            if sub == 0:
                break
            sub = (sub-1) & mask
        if values[mask]:
            row |= 1 << width
        witness = 1 << row_index
        while row & ((1 << width)-1):
            features = row & ((1 << width)-1)
            pivot = (features & -features).bit_length()-1
            if pivot not in basis:
                basis[pivot] = (row, witness)
                break
            row ^= basis[pivot][0]
            witness ^= basis[pivot][1]
        else:
            if row == (1 << width):
                indices_used = [i for i in range(row_index+1)
                                if witness >> i & 1]
                certificate = [masks[i] for i in indices_used]
                assert sum(values[item] for item in certificate) % 2 == 1
                assert all(sum((item & mono) == mono for item in certificate) % 2 == 0
                           for mono in monomials)
                return {"status": "NO_POLYNOMIAL_OF_DEGREE_AT_MOST_D",
                        "degree_bound": degree,
                        "monomial_count": width,
                        "feature_rank_at_rejection": len(basis),
                        "rows_scanned": row_index+1,
                        "certificate_mask_count": len(certificate),
                        "certificate_masks": certificate}
            assert row == 0
    return {"status": "CONSISTENT", "degree_bound": degree,
            "monomial_count": width, "feature_rank": len(basis),
            "rows_scanned": len(masks)}


def main():
    protocol = json.loads((HERE / "degree_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_COFACTOR_DEGREE_GATES"
    assert protocol["sha256"]["script"] == sha(Path(__file__))
    assert protocol["sha256"]["support"] == sha(SUPPORT)
    assert protocol["sha256"]["class_bits"] == sha(HERE / "class_bits.bin")
    values = (HERE / "class_bits.bin").read_bytes()
    masks = [int(line.split()[0]) for line in SUPPORT.read_text().splitlines()]
    assert len(masks) == len(set(masks)) == 16441
    rows = [gate(masks, values, d) for d in protocol["degree_bounds"]]
    result = {"status": "PASS_EXACT_W15_COFACTOR_DEGREE_GATE",
              "rows": rows,
              "sha256": {"protocol": sha(HERE / "degree_protocol.json"),
                         "script": sha(Path(__file__)),
                         "support": sha(SUPPORT),
                         "class_bits": sha(HERE / "class_bits.bin")}}
    with (HERE / "degree_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "gates": [{"d": row["degree_bound"],
                                 "status": row["status"],
                                 "rows": row["rows_scanned"]}
                                for row in rows]}))


if __name__ == "__main__":
    main()
