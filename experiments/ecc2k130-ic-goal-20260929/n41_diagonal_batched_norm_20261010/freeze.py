#!/usr/bin/env python3
"""Freeze the global bucket-product GCD gate before either target case."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n41_diagonal_double_norm_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "protocol.json"
    if path.exists():
        raise FileExistsError(path)
    prior = json.loads((PRIOR / "result.json").read_text())
    assert prior["status"] == "PARTIAL"
    assert [case["status"] for case in prior["cases"]] == ["CENSORED_TIME"]*2
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    sources = {"batch": HERE / "batch.py", "freeze": Path(__file__),
               "prior_run": PRIOR / "run.py", "prior_input": PRIOR / "input.json",
               "prior_protocol": PRIOR / "protocol.json", "prior_result": PRIOR / "result.json",
               "geometry": PRIOR.parent / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json",
               "base": PRIOR.parent / "run_n41_disjoint_s5_sat.py",
               "pair_oracle": PRIOR.parent.parent / "koblitz-polynomial-w-pair-20260925/pair_oracle.py",
               "runtime": HERE / "sage_runtime_info.json"}
    protocol = {"status": "FROZEN_BEFORE_RUN", "candidate_id": None,
                "cases": ["positive", "public"],
                "algorithm": "global products of all left bucket polynomials and all target-dependent right resultants, one GCD per raw target lift, exact localization and group replay",
                "positive_lift_policy": "known control lift only",
                "public_lift_policy": "both exact trace-zero lifts",
                "online_wall_cap_seconds": 300,
                "process_wall_cap_seconds": 360,
                "rss_cap_bytes": 4*1024**3, "workers": 1,
                "source_sha256": {name: sha(source) for name, source in sources.items()}}
    path.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": protocol["status"],
                      "prior_result_sha256": protocol["source_sha256"]["prior_result"],
                      "batch_source_sha256": protocol["source_sha256"]["batch"]}, indent=2))


if __name__ == "__main__":
    main()
