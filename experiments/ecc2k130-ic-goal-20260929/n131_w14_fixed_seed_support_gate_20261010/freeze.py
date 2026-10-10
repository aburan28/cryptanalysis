#!/usr/bin/env python3
"""Freeze exact sources and resource limits before the support panel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = {
        "freeze": Path(__file__),
        "count_bound": HERE / "count_bound.py",
        "sage_support": HERE / "sage_support.py",
        "run_sage": HERE / "run_sage.py",
        "w14_support":
            GOAL / "n131_w14_ten_source_gate_20261009/support_w14.tsv",
        "n41_screen":
            GOAL / "n41_n131_diagonal_atom_20261010/screen.json",
        "fouratom_inputs":
            GOAL / "n131_w14_coupled_fouratom_inverse_20261010/inputs.json",
        "sage_runtime": HERE / "sage_runtime_info.json",
    }
    runtime = json.loads(sources["sage_runtime"].read_text())
    assert runtime["status"] == "verified"
    protocol = {
        "status": "FROZEN_BEFORE_SUPPORT_GATE",
        "kind": "fixed_seed_four_atom_group_support_and_arity_bound",
        "candidate_id": None,
        "target_count": 0,
        "input_law": (
            "N41 exact complete group output sets from all 63 shared seed sums "
            "with four distinct folded columns; N131 source-mask combinatorial "
            "support upper bounds for one fixed or variable shared seed"
        ),
        "run_order": ["count_bound", "sage_support"],
        "workers": 1,
        "n41_cap_seconds": 120,
        "rss_cap_bytes": 4 * 1024**3,
        "source_sha256": {name: sha(path) for name, path in sources.items()},
    }
    with (HERE / "protocol.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": protocol["status"],
                      "source_count": len(sources)}))


if __name__ == "__main__":
    main()
