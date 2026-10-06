#!/usr/bin/env python3
"""Freeze Q1437 source, workload, exact parent geometry, and runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
PROTOCOL = HERE / "protocol.json"
BASE = PARENT / "runs/n131_q1413_projected_x_w6.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make():
    base = json.loads(BASE.read_text())
    assert base["curve_id"] == "EC1N131Ckb1h6816f880945e"
    assert base["actual_usable_points_B_before_folding"] == 6559634788
    assert base["signed_frobenius_columns_K"] == 25036774
    runtime = HERE / "sage_runtime_info.json"
    assert json.loads(runtime.read_text())["status"] == "verified"
    relative = (
        "ecc2k130/codegen/field.py",
        "ecc2k130/codegen/curves.py",
        "experiments/koblitz-pair-claw-20260929/orbit_key.py",
        "experiments/compact-s3-m4-20261003/enumerate_q1413_projected_x.py",
        "experiments/compact-s3-m4-20261003/run_probe.py",
    )
    return {
        "kind": "q1437_frozen_n131_weight7_frontier_protocol",
        "proposal_id": "Q1437", "candidate_id": None,
        "curve_id": base["curve_id"], "isogeny": "none",
        "exact_w6_base_receipt_sha256": sha(BASE),
        "subgroup_order": 680564733841876926932320129493409985129,
        "normal_basis_weight_bound": 7,
        "seed": 2026100407, "sample_size": 100000,
        "independent_control_count": 32,
        "source_sha256": sha(HERE / "screen.py"),
        "verification_source_sha256": sha(HERE / "verify.py"),
        "runtime_info_sha256": sha(runtime),
        "dependencies": {name: {"relative_path": name,
                                "sha256": sha(ROOT / name)}
                         for name in relative},
        "claim_scope": (
            "A sampled, conditional N131 W<=7 factor-base and optimistic "
            "matrix frontier. No actual W7 B/K/digest, ordinary relation "
            "yield, PDP cost, complete 2^x, or challenge admission."),
    }


def main():
    frozen = make()
    if PROTOCOL.exists():
        assert json.loads(PROTOCOL.read_text()) == frozen
        print("Q1437 protocol verified")
    else:
        PROTOCOL.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
        print("Q1437 protocol frozen")


if __name__ == "__main__":
    main()
