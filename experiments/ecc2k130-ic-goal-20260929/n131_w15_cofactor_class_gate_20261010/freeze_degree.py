#!/usr/bin/env python3
"""Freeze the support-restricted algebraic degree panel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert json.loads((HERE / "census.json").read_text())["status"] == \
        "PASS_EXACT_W15_COFACTOR_CLASS_CENSUS"
    receipt = {"status": "FROZEN_BEFORE_W15_COFACTOR_DEGREE_GATES",
               "curve_id": "EC1N131Ckb1heb5f1998f20b",
               "degree_bounds": [1, 2, 3, 4],
               "input_law": "all 16441 support masks in archived table order",
               "sha256": {"script": sha(HERE / "degree_gate.py"),
                          "class_bits": sha(HERE / "class_bits.bin"),
                          "support": sha(SUPPORT),
                          "census": sha(HERE / "census.json")}}
    with (HERE / "degree_protocol.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "degree_bounds": receipt["degree_bounds"]}))


if __name__ == "__main__":
    main()
