#!/usr/bin/env python3
"""Freeze source identities before the Walsh pair-class census."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert json.loads((HERE / "audit.json").read_text())["status"] == \
        "PASS_INDEPENDENT_SAGE_W15_COFACTOR_CLASS_REPLAY"
    receipt = {"status": "FROZEN_BEFORE_W15_CLASS_SEED_CENSUS",
               "curve_id": "EC1N131Ckb1heb5f1998f20b",
               "seed_law": "all nonzero 15-bit XOR sums of distinct usable W15 masks",
               "sha256": {"script": sha(HERE / "seed_class.py"),
                          "support": sha(SUPPORT),
                          "class_bits": sha(HERE / "class_bits.bin"),
                          "census": sha(HERE / "census.json"),
                          "audit": sha(HERE / "audit.json")}}
    with (HERE / "seed_protocol.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"]}))


if __name__ == "__main__":
    main()
