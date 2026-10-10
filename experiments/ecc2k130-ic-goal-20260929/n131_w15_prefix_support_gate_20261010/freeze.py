#!/usr/bin/env python3
"""Freeze the exact six-pair support inputs before the prefix calculation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
W15 = BASE / "n131_w15_coupled_sixpair_20261010/seed_sum_count.json"
W14 = BASE / "n41_upper_xor_projection_20261010/seed_sum_count.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    sources = {
        "freeze": Path(__file__),
        "calculator": HERE / "calculate.py",
        "independent_audit": HERE / "audit.py",
        "w15_exact_count": W15,
        "w14_exact_count": W14,
    }
    record = {
        "status": "FROZEN_BEFORE_W15_PREFIX_SUPPORT_CALCULATION",
        "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "subgroup_order": "680564733841876926932320129493409985129",
        "wall_budget_seconds": 600,
        "target_law": "uniform subgroup point, including identity",
        "prefix_law": "target-independent distinct prefix outputs",
        "scope": "six W15 same-rotation signed pairs; first two free, last four in two same-seed blocks; same-pair column exclusions only",
        "source_sha256": {name: sha(path) for name, path in sources.items()},
    }
    with (HERE / "protocol.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(record["status"])


if __name__ == "__main__":
    main()
