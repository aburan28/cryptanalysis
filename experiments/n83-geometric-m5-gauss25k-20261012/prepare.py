#!/usr/bin/env python3
"""Freeze three bounded CryptoMiniSat XOR-matrix diagnostics on one XCNF."""

import hashlib
import json
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-m5-fixedtarget16-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    assert not output.exists()
    parent_protocol_path = PARENT / "protocol.json"
    parent_result_path = PARENT / "width16_ordinary.json"
    parent_protocol = json.loads(parent_protocol_path.read_text())
    parent_result = json.loads(parent_result_path.read_text())
    assert parent_protocol["proposal_id"] == "Q2026101250"
    assert parent_result["proposal_id"] == "Q2026101250"
    assert parent_result["workload_id"] == parent_protocol["workload_id"]
    assert len(parent_result["attempts"]) >= 1
    attempt = parent_result["attempts"][0]
    xcnf_path = PARENT / attempt["xcnf_gzip"]
    assert sha(xcnf_path) == attempt["xcnf_gzip_sha256"]
    solver_path = Path(parent_protocol["solver"]["path"])
    assert sha(solver_path) == parent_protocol["solver"]["sha256"]
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    sources = [Path(__file__), HERE / "run.py", PARENT / "run.py",
               ROOT / "experiments/m5-s3-gate-20261004/run_gate.py"]
    protocol = {
        "kind": "n83_fixed_target_xcnf_gaussian_matrix_diagnostic_protocol",
        "proposal_id": "Q2026101251",
        "candidate_id": None,
        "curve_id": parent_protocol["curve_id"],
        "workload_id": parent_protocol["workload_id"],
        "public_point_onb_raw": parent_protocol["workload"]["public_point_onb_raw"],
        "parent_protocol_sha256": sha(parent_protocol_path),
        "parent_result_sha256": sha(parent_result_path),
        "xcnf_gzip": str(xcnf_path.relative_to(ROOT)),
        "xcnf_gzip_sha256": sha(xcnf_path),
        "xcnf_raw_sha256": attempt["xcnf_raw_sha256"],
        "xcnf_raw_bytes": attempt["xcnf_raw_bytes"],
        "solver_path": str(solver_path),
        "solver_sha256": sha(solver_path),
        "max_conflicts": parent_protocol["solver"]["max_conflicts"],
        "wall_seconds_per_arm": 60,
        "sampled_solver_rss_stop_bytes": 4294967296,
        "rss_monitor_library": f"psutil {psutil.__version__}",
        "arms": [
            {"name": "default", "extra_flags": []},
            {"name": "maxcols25000", "extra_flags": ["--maxmatrixcols", "25000"]},
            {"name": "maxcols25000_persistent", "extra_flags": [
                "--maxmatrixcols", "25000", "--autodisablegauss", "0"]},
        ],
        "stop_on_verified_relation": True,
        "timing_tier": "exploratory_local_unisolated",
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in sources},
        "sage_runtime_info_sha256": sha(runtime_path),
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "frozen", "arms": [a["name"] for a in protocol["arms"]]}))


if __name__ == "__main__":
    main()
