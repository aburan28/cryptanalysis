#!/usr/bin/env python3
"""Freeze source identities before the complete W15 cofactor census."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    receipt = {"status": "FROZEN_BEFORE_W15_COFACTOR_CLASS_CENSUS",
               "curve_id": "EC1N131Ckb1heb5f1998f20b",
               "field_modulus": "t^131+t^13+t^2+t+1",
               "curve": "y^2+xy=x^3+1",
               "subgroup_order": "680564733841876926932320129493409985129",
               "source_width": 15,
               "input_law": "every mask 0..32767; mark the archived 16441 rational masks",
               "rss_cap_bytes": 4294967296,
               "wall_cap_seconds": 180,
               "sha256": {"census": sha(HERE / "census.py"),
                          "support": sha(SUPPORT),
                          "runtime": sha(HERE / "sage_runtime_info.json"),
                          "probe": sha(HERE / "probe.py")}}
    with (HERE / "protocol.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "sha256": receipt["sha256"]}))


if __name__ == "__main__":
    main()
