#!/usr/bin/env python3
"""Freeze a same-query solver-policy test before launching either attempt."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = PARENT / "n131_d10_bridge_projection_20261009"
FORMULA = SOURCE / "budget1/projected.xcnf"
BRIDGE = PARENT / "n131_d10_xor_bridge_20261009/bridge_cnf/bridge_cnf.xcnf"
RAW = (PARENT / "n131_phi_torsion_frobenius_domains_20261005/m15_d10_static/"
       "single_target_runs/"
       "IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0h91f3d222e01b"
       "W3c1992b7c92fR1/precomputation/target_0001/model_01/query.xcnf")
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RUNTIME = HERE / "sage_runtime_info.json"
PROTOCOL = HERE / "protocol.json"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    if PROTOCOL.exists():
        raise FileExistsError(PROTOCOL)
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    parent = json.loads((SOURCE / "protocol.json").read_text())
    assert sha(FORMULA) == parent["source_sha256"]["formula"]
    assert sha(BRIDGE) == parent["source_sha256"]["bridge"]
    assert sha(RAW) == parent["source_sha256"]["raw"]
    assert sha(SOLVER) == parent["source_sha256"]["solver"]
    assert json.loads((SOURCE / "budget1/independent_elimination_audit.json").read_text())["status"] == "PASS"
    sources = {name: sha(path) for name, path in {
        "formula": FORMULA, "bridge": BRIDGE, "raw": RAW,
        "solver": SOLVER, "runtime": RUNTIME,
        "runner": HERE / "run.py",
        "bridge_audit": PARENT / "n131_d10_xor_bridge_20261009/bridge_cnf/independent_audit.json",
        "projection_audit": SOURCE / "budget1/independent_elimination_audit.json",
        "old_solver_log": SOURCE / "ordinary_precompute_R1/cryptominisat.stdout.txt",
    }.items()}
    record = {
        "status": "FROZEN_PROPOSAL",
        "kind": "n131_d10_exact_bridge_no_xor_rediscovery_solver_policy",
        "proposal_id": "Q20261009190000",
        "candidate_id": None, "run_id": None,
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "source_run_id": parent["source_run_id"],
        "target_count": 1, "batch": False,
        "query_role": "first target-independent precomputation relation query",
        "controlled_change": "--xor=0 disables discovery of new XOR rows from exact CNF bridge clauses; native input XOR rows stay present",
        "same_source_point_formula_and_seed": True,
        "limit": {"preflight_wall_seconds": 90, "full_wall_seconds": 580,
                  "combined_rss_bytes": 4294967296},
        "solver_flags_common": [
            "--threads=1", "--verb=1", "--verbstat=2", "--printsol=1",
            "--restartprint=10000000", "--random=2026100618",
            "--maxmatrixrows=10000", "--maxmatrixcols=15000",
            "--maxnummatrices=10", "--xor=0", "--maxconfl=1000000000000",
        ],
        "stage_clock": "solver launch to exit and drain; source formula build and exact transformations excluded",
        "model_rule": "verify projected, bridge, original XCNFs and independent installed-Sage curve relation before counting a relation",
        "source_sha256": sources,
    }
    PROTOCOL.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN_PROPOSAL", "protocol_sha256": sha(PROTOCOL)}))


if __name__ == "__main__":
    main()
