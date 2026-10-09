#!/usr/bin/env python3
"""Freeze a bounded public-Q solver attempt on the audited d13 formula."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCE = HERE
FORMULA = SOURCE / "budget1/projected.xcnf"
BRIDGE = SOURCE / "bridge_cnf/bridge_cnf.xcnf"
RAW = (PARENT / "n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/"
       "official_q_phi_fiber_d13_m12_v1.xcnf")
PREVIOUS = (PARENT / "n131_d13_projected_public_q_20261009/"
            "public_q_stage_run_R2/cryptominisat.stdout.txt")
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RUNTIME = HERE / "sage_runtime_info.json"
PROTOCOL = HERE / "solver_protocol.json"


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
    projection = json.loads((SOURCE / "budget1/result.json").read_text())
    bridge = json.loads((SOURCE / "bridge_cnf/result.json").read_text())
    assert sha(FORMULA) == projection["source_sha256"]["projected_xcnf"]
    assert sha(BRIDGE) == projection["source_sha256"]["input_xcnf"] == bridge["source_sha256"]["output_xcnf"]
    assert sha(RAW) == parent["input_sha256"] == bridge["source_sha256"]["input_xcnf"]
    assert json.loads((SOURCE / "budget1/independent_elimination_audit.json").read_text())["status"] == "PASS"
    assert json.loads((SOURCE / "component_audit.json").read_text())["status"] == "PASS_COMPONENT_FIT"
    sources = {name: sha(path) for name, path in {
        "formula": FORMULA, "bridge": BRIDGE, "raw": RAW,
        "solver": SOLVER, "runtime": RUNTIME,
        "runner": HERE / "run_public.py",
        "bridge_audit": HERE / "bridge_cnf/independent_audit.json",
        "projection_audit": SOURCE / "budget1/independent_elimination_audit.json",
        "component_audit": SOURCE / "component_audit.json",
        "old_solver_log": PREVIOUS,
    }.items()}
    record = {
        "status": "FROZEN_PROPOSAL",
        "kind": "n131_d13_public_q_exact_bridge_projection_no_xor_rediscovery_solver_policy",
        "proposal_id": "Q20261009190500",
        "candidate_id": None, "run_id": None,
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "target_count": 1, "batch": False,
        "query_role": "one supplied public Q point-decomposition stage",
        "method_change": "exact CNF bridges, fill-limited XOR projection, and --xor=0 to preserve bridge clauses during solver simplification",
        "same_public_q_and_seed_as_previous_projected_probe": True,
        "limit": {"full_wall_seconds": 580, "combined_rss_bytes": 4294967296},
        "solver_flags_common": [
            "--threads=1", "--verb=1", "--verbstat=2", "--printsol=1",
            "--restartprint=10000000", "--random=2026100613",
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
