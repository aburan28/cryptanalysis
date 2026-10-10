#!/usr/bin/env python3
"""Freeze exact triple geometry, native search, and one-worker limits."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / "protocol.json"
    if path.exists():
        raise FileExistsError(path)
    geometry = json.loads((HERE / "geometry_result.json").read_text())
    assert geometry["status"] == "EXACT_GEOMETRY"
    assert geometry["n41"]["unordered_zero_sum_triples"] == 317
    assert geometry["n131"]["unordered_zero_sum_triples"] == 1439333092
    assert geometry["sha256"]["source"] == sha(HERE / "prepare.py")
    assert geometry["sha256"]["public_input"] == sha(HERE / "input_public.txt")
    assert geometry["sha256"]["control_input"] == sha(HERE / "input_control.txt")
    sources = {
        "freeze": HERE / "freeze.py",
        "prepare": HERE / "prepare.py",
        "join_source": HERE / "join.cpp",
        "join_binary": HERE / "join",
        "runner": HERE / "run.py",
        "audit": HERE / "audit.py",
        "runtime": HERE / "sage_runtime_info.json",
        "screen": GOAL / "n131_w18_four_pairs/screen.json",
        "geometry": HERE / "geometry_result.json",
        "n131_valid_bits": HERE / "n131_valid_mask_bits.bin",
        "input_control": HERE / "input_control.txt",
        "input_public": HERE / "input_public.txt",
        "control_witness": HERE / "control_witness.json",
        "helper": GOAL / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp",
    }
    record = {
        "status": "FROZEN", "proposal_id": "Q20261009195000",
        "candidate_id": None, "run_id": None,
        "curve_id_n41": "EC1N41Ckb1h7d5e80d3c4d0",
        "curve_id_n131": "EC1N131Ckb1h136f03e58c98",
        "target_count": 1,
        "public_target": geometry["n41"]["target_q"],
        "input_law": "four zero-sum three-leaf W7 blocks, each with independent signed source points; public N41 point supplied without any pinned leaf",
        "compile_command": ["clang++", "-O3", "-std=c++17", "-Wall",
                            "-Wextra", "-Werror", "-Wno-return-type",
                            str(HERE / "join.cpp"), "-o", str(HERE / "join")],
        "limits": {"setup_seconds": 300, "online_seconds": 120,
                   "parent_seconds": 420, "peak_rss_bytes": 4 * 1024**3,
                   "workers": 1},
        "sha256": {name: sha(source) for name, source in sources.items()},
    }
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "public_target": record["public_target"],
                      "sha256": sha(path)}))


if __name__ == "__main__":
    main()
