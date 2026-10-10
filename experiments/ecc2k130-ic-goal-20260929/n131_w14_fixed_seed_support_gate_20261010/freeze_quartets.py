#!/usr/bin/env python3
"""Freeze the exact collision-adjusted quartet-count source and inputs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = {
        "freeze": Path(__file__),
        "script": HERE / "count_quartets.py",
        "w14_support":
            GOAL / "n131_w14_ten_source_gate_20261009/support_w14.tsv",
        "n41_screen":
            GOAL / "n41_n131_diagonal_atom_20261010/screen.json",
        "bounds": HERE / "result_bounds.json",
        "n41_group_support": HERE / "support_n41.json",
    }
    protocol = {
        "status": "FROZEN_BEFORE_QUARTET_COUNT",
        "kind": "exact_xor_zero_distinct_column_quartet_count",
        "candidate_id": None,
        "target_count": 0,
        "workers": 1,
        "cap_seconds": 120,
        "rss_cap_bytes": 4 * 1024**3,
        "source_sha256": {name: sha(path) for name, path in source.items()},
    }
    with (HERE / "quartet_protocol.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": protocol["status"]}))


if __name__ == "__main__":
    main()
