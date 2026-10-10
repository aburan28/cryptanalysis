#!/usr/bin/env python3
"""Freeze the exact six-block public target join before execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
GOAL = PARENT.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths():
    return {
        "prepare.py": HERE / "prepare.py",
        "join.cpp": HERE / "join.cpp",
        "join_binary": HERE / "join",
        "run.py": HERE / "run.py",
        "audit.py": HERE / "audit.py",
        "input.txt": HERE / "input.txt",
        "input_receipt.json": HERE / "input_receipt.json",
        "geometry.json": PARENT / "geometry.json",
        "parent_audit.py": PARENT / "audit.py",
        "helper.cpp": GOAL / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp",
        "public_target.json": GOAL / "n41_adjacent_pairpair/public_target.json",
    }


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    paths = source_paths()
    receipt = json.loads((HERE / "input_receipt.json").read_text())
    if (receipt["input_sha256"] != sha(HERE / "input.txt") or
            receipt["geometry_sha256"] != sha(PARENT / "geometry.json") or
            receipt["public_target_sha256"] != sha(
                GOAL / "n41_adjacent_pairpair/public_target.json") or
            receipt["prepare_sha256"] != sha(HERE / "prepare.py")):
        raise ValueError("prepared input hashes do not match")
    protocol = {"status": "FROZEN", "proposal_id": "Q20261009174000",
                "candidate_id": None, "curve_id": receipt["curve_id"],
                "target_q": [1458168294740, 1672312028033],
                "worker_count": 1, "wall_cap_seconds": 600,
                "rss_cap_bytes": 4 * 1024**3,
                "target_independent_stage": "left triple table",
                "online_stage": "right triple generation, target residual lookup, relation replay",
                "compiler_command": "c++ -O3 -std=c++20 -Wall -Wextra -o join join.cpp",
                "source_sha256": {key: sha(path) for key, path in paths.items()}}
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"],
                      "source_sha256": protocol["source_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
