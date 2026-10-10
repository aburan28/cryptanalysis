#!/usr/bin/env python3
"""Freeze the bounded Sage replay after the first monitor's permission error."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = {
        "freeze_v2": Path(__file__),
        "run_sage_v2": HERE / "run_sage_v2.py",
        "sage_support_v2": HERE / "sage_support_v2.py",
        "n41_screen":
            GOAL / "n41_n131_diagonal_atom_20261010/screen.json",
        "fouratom_inputs":
            GOAL / "n131_w14_coupled_fouratom_inverse_20261010/inputs.json",
        "sage_runtime_v2": HERE / "sage_runtime_info_v2.json",
        "original_protocol": HERE / "protocol.json",
        "original_result": HERE / "support_n41.json",
        "original_failure": HERE / "failure_v1.json",
    }
    runtime = json.loads(sources["sage_runtime_v2"].read_text())
    assert runtime["status"] == "verified"
    original = json.loads(sources["original_result"].read_text())
    assert original["status"] == "PASS_COMPLETE_N41_FOURATOM_GROUP_SUPPORT"
    protocol = {
        "status": "FROZEN_BEFORE_SAGE_REPLAY_V2",
        "kind": "bounded_replay_of_complete_n41_fouratom_group_support",
        "candidate_id": None,
        "target_count": 0,
        "workers": 1,
        "n41_cap_seconds": 120,
        "rss_cap_bytes": 4 * 1024**3,
        "rss_monitor": "direct launched process; checked Sage launcher execs into Sage after runtime verification",
        "required_result": "byte-identical mathematical counts and public-point membership to original producer",
        "source_sha256": {name: sha(path) for name, path in sources.items()},
    }
    with (HERE / "protocol_v2.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": protocol["status"]}))


if __name__ == "__main__":
    main()
