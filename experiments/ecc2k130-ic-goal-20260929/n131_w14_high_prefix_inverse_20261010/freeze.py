#!/usr/bin/env python3
"""Freeze W14 high-prefix arithmetic and its positive/uniform panel."""

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_polynomial_pair_inverse_20261010"
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009"
REPLAY = HERE.parents[2].parent / "crypto/research/sat_factor_base_review_20260908/autolab_orbit_extract_20260924"
PANEL = [0, 8, 16, 20, 24, 28, 30, 31, 32, 33, 34, 35, 36, 40, 48]

FILES = {
    "freezer": HERE / "freeze.py",
    "prefix": HERE / "prefix.py",
    "runner": HERE / "run.py",
    "sage_auditor": HERE / "sage_audit.py",
    "runtime": HERE / "sage_runtime_info.json",
    "oracle": SOURCE / "oracle.py",
    "field": REPLAY / "independent_replay.py",
    "inputs": SOURCE / "inputs.json",
    "source_protocol": SOURCE / "protocol.json",
    "source_result": SOURCE / "result.json",
    "source_audit": SOURCE / "sage_audit.json",
    "support": SUPPORT / "support_w14.tsv",
    "support_audit": SUPPORT / "sage_support_audit.json",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    source = json.loads((SOURCE / "protocol.json").read_text())
    inputs = json.loads((SOURCE / "inputs.json").read_text())
    prior = json.loads((SOURCE / "result.json").read_text())
    audit = json.loads((SOURCE / "sage_audit.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert source["status"] == "FROZEN_BEFORE_PAIR_QUERIES"
    assert source["inputs_sha256"] == sha(SOURCE / "inputs.json")
    assert inputs["status"] == "FROZEN_INPUTS"
    assert prior["status"] == "PASS_EXACT_W14_JOINT_PAIR_INVERSE_CONTROLS"
    assert audit["status"].startswith("PASS_")
    assert runtime["status"] == "verified"
    assert len(inputs["positives"]) == 32
    assert len(inputs["controls"]) == 34
    for key, path in FILES.items():
        if not path.exists():
            raise FileNotFoundError((key, path))
    receipt = {
        "status": "FROZEN_HIGH_PREFIX",
        "proposal_id": "Q20261010223000", "candidate_id": None,
        "curve_id": source["curve_id"], "target_count": 0,
        "actual_factor_base_points_B": source["actual_factor_base_points_B"],
        "effective_folded_columns_K": source["effective_folded_columns_K"],
        "factor_base_policy": source["factor_base_policy"],
        "free_low_bit_widths": PANEL,
        "max_projected_nullity": 8,
        "positive_count": 32, "uniform_field_control_count": 32,
        "method": "project onto rows invariant under every low-bit perturbation of z in z^2=u_s^2+(z^2+z)p; enumerate at most 256 coefficient solutions, exact fixed-sum mask inversion, then raw group-prefix replay",
        "wall_cap_seconds": 120, "rss_cap_bytes": 4_294_967_296,
        "files": {key: os.path.relpath(path, HERE)
                  for key, path in FILES.items()},
        "sha256": {key: sha(path) for key, path in FILES.items()},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "files": len(FILES), "sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
