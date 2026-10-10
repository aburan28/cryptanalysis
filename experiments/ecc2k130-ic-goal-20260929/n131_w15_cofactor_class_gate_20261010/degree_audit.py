#!/usr/bin/env python3
"""Replay each low-degree obstruction without the producer elimination."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((HERE / "degree_result.json").read_text())
    values = (HERE / "class_bits.bin").read_bytes()
    assert result["status"] == "PASS_EXACT_W15_COFACTOR_DEGREE_GATE"
    checked = []
    for row in result["rows"]:
        d = row["degree_bound"]
        assert row["status"] == "NO_POLYNOMIAL_OF_DEGREE_AT_MOST_D"
        masks = row["certificate_masks"]
        assert len(masks) == row["certificate_mask_count"]
        assert sum(values[mask] for mask in masks) % 2 == 1
        monomials = [mask for mask in range(1 << 15)
                     if mask.bit_count() <= d]
        assert len(monomials) == row["monomial_count"]
        assert all(sum((mask & mono) == mono for mask in masks) % 2 == 0
                   for mono in monomials)
        checked.append(d)
    receipt = {"status": "PASS_INDEPENDENT_W15_DEGREE_CERTIFICATES",
               "degree_bounds": checked,
               "sha256": {"script": sha(Path(__file__)),
                          "result": sha(HERE / "degree_result.json"),
                          "class_bits": sha(HERE / "class_bits.bin")}}
    with (HERE / "degree_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "degree_bounds": checked}))


if __name__ == "__main__":
    main()
