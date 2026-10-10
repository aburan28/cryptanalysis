#!/usr/bin/env python3
"""Bind the exact N41 W6 join source, input, executable, and search limits."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
HELPER = GOAL / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
SCREEN = GOAL / "n41_n131_diagonal_atom_20261010/screen.json"
PATHS = {"script": Path(__file__), "source": HERE / "join_w6.cpp",
         "binary": HERE / "join_w6", "helper": HELPER,
         "export_script": HERE / "export_w6.py", "export_receipt": HERE / "w6_export.json",
         "screen": SCREEN, "input": HERE / "w6_input.txt",
         "sage_runtime": HERE / "sage_runtime_info.json"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    export = json.loads((HERE / "w6_export.json").read_text())
    assert export["status"] == "PASS_FROZEN_W6_SIX_ROTATION_INPUT"
    assert export["source_sha256"]["input"] == sha(HERE / "w6_input.txt")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    compiler = subprocess.check_output(["c++", "--version"], text=True).splitlines()[0]
    record = {
        "status": "FROZEN_BEFORE_N41_W6_PUBLIC_QUERY",
        "kind": "six_same_rotation_w6_diagonal_pairs_two_seed_equalities",
        "candidate_id": None, "curve_id": export["curve_id"],
        "public_target_q": export["public_target_q"],
        "target_count": 1, "paired_rotations": export["paired_rotations"],
        "actual_factor_base_points_B": 384, "folded_columns_K": 26,
        "summands": 12, "workers": 1,
        "max_accepted_online_probes": 20000000,
        "online_cap_seconds": 600, "rss_cap_bytes": 4 * 1024**3,
        "index_policy": "reusable target-independent free four-atom group index",
        "relation_policy": "six unordered signed same-rotation pairs; pair 2 and 3 share seed sum; pair 4 and 5 share seed sum; all twelve folded columns distinct; exact subgroup sum equals supplied Q",
        "compiler": compiler,
        "compile_command": "c++ -std=c++17 -O3 -DNDEBUG join_w6.cpp -o join_w6",
        "source_sha256": {key: sha(path) for key, path in PATHS.items()},
    }
    with (HERE / "w6_protocol.json").open("x") as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": record["status"], "binary_sha256": record["source_sha256"]["binary"]}))


if __name__ == "__main__":
    main()
