#!/usr/bin/env python3
"""Reproduce or verify the frozen cached-W16 query protocol byte for byte."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w16_fivepair_sat_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record():
    base = json.loads((HERE / "protocol.json").read_text())
    core = json.loads((HERE / "core_result.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    assert base["status"] == "FROZEN_BEFORE_W16_CACHED_CORE"
    assert core["status"] == "PASS_REUSABLE_W16_SOURCE_CORE"
    assert control["status"] == "PASS_CACHED_W16_FULL_XCNF_AND_GROUP_CONTROL"
    paths = {"query": HERE / "query.py", "runner": HERE / "run.py",
             "core_source": HERE / "core.py", "core": HERE / "core.pickle.gz",
             "core_result": HERE / "core_result.json",
             "base_protocol": HERE / "protocol.json",
             "control_result": HERE / "control_result.json",
             "control_formula": HERE / "control.xcnf.gz",
             "input": OLD / "fivepair_input.json",
             "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}
    return {"status": "FROZEN_BEFORE_CACHED_W16_QUERY",
            "candidate_id": None, "curve_id": base["curve_id"],
            "target_law": base["target_law"],
            "target_q": base["target_q"],
            "fixed_first_pair_columns": base["fixed_first_pair_columns"],
            "workers": 1, "wall_cap_seconds": 120,
            "parent_safe_stop_seconds": 115,
            "rss_cap_bytes": 4*1024**3,
            "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                             "--random=20261010", "--maxconfl=20000000",
                             "--maxtime=106"],
            "source_sha256": {name: sha(path) for name, path in paths.items()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    expected = (json.dumps(record(), sort_keys=True, indent=2) + "\n").encode()
    path = HERE / "query_protocol.json"
    if args.verify:
        assert path.read_bytes() == expected
        print("PASS_BYTE_IDENTICAL_FROZEN_QUERY_PROTOCOL")
    else:
        with path.open("xb") as stream:
            stream.write(expected)
        print("FROZEN_BEFORE_CACHED_W16_QUERY")


if __name__ == "__main__":
    main()
