#!/usr/bin/env python3
"""Freeze the target-independent N131 pair-output projection producer."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
CONTROL = BASE / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"
PREVIOUS = BASE / "n131_w15_two_fixed_seeds_public_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {"freezer": HERE / "freeze.py",
            "producer": HERE / "derive_prefix.py",
            "independent_audit": HERE / "audit_prefix.py",
            "checked_sage_runtime": HERE / "sage_runtime_info.json",
            "support": SUPPORT,
            "constructed_input": CONTROL,
            "previous_circuit": PREVIOUS / "circuit.py",
            "previous_protocol": PREVIOUS / "protocol.json"}


def main():
    assert not (HERE / "projection_protocol.json").exists()
    control = json.loads(CONTROL.read_text())
    seeds = [control["masks"][2*i] ^ control["masks"][2*i+1]
             for i in range(2)]
    assert seeds == [12004, 9022]
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    protocol = {"status": "FROZEN_W15_PAIR_OUTPUT_PREFIX_PRODUCER",
                "curve_id": "EC1N131Ckb1heb5f1998f20b",
                "candidate_id": None, "target_count": 0,
                "field_modulus": "t^131+t^13+t^2+t+1",
                "source_dimension": 15, "seeds": seeds,
                "rotations": [0, 13], "prefix_bits": 16,
                "source_masks": 16441, "folded_columns_K": 16381,
                "workers": 1, "producer_wall_cap_seconds": 300,
                "rss_cap_bytes": 4*1024**3,
                "source_sha256": {name: sha(path)
                                  for name, path in sources().items()}}
    with (HERE / "projection_protocol.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": protocol["status"],
                      "seeds": seeds, "prefix_bits": 16}))


if __name__ == "__main__":
    main()
