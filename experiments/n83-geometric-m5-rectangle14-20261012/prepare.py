#!/usr/bin/env python3
"""Freeze the N83 rectangle width-14 PDP stage on the prior public point."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/n83-geometric-rectangle14-20261012"
PRIOR_STAGE = ROOT / "experiments/n83-geometric-m5-normalized14-20261012"
PARENT = PRIOR_STAGE
IDENTITY = ROOT / "experiments/koblitz-pair-claw-20260929/runs/n83_knownlog_orbit_base_k48194.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    assert not output.exists(), "refusing to overwrite frozen protocol"
    parent_path = PARENT / "protocol.json"
    prior_run = PRIOR_STAGE / "width14_ordinary.json"
    basis_path = BASE / "basis_manifest.json"
    union_path = BASE / "rectangle.json"
    union_replay_path = BASE / "independent_sage_replay.json"
    parent = json.loads(parent_path.read_text())
    basis = json.loads(basis_path.read_text())
    union = json.loads(union_path.read_text())
    union_replay = json.loads(union_replay_path.read_text())
    identity = json.loads(IDENTITY.read_text())
    assert parent["workload_id"] == "df4396f4d8fc"
    assert union["status"] == "complete_geometry"
    assert union_replay["status"] == "PASS"
    assert basis["factor_base_key_sha256"] == union["key_sha256"]
    assert basis["effective_columns_K"] == union["folded_columns_K"] == 8532
    assert basis["actual_subgroup_points_B"] == union["actual_usable_points_B_before_folding"] == 1416312
    assert basis["curve_id"] == parent["curve_id"] == identity["curve_id"]
    assert sha(BASE / "rectangle_keys.bin") == union["key_sha256"]
    assert parent["solver"]["threads"] == 1
    assert sha(Path(parent["solver"]["path"])) == parent["solver"]["sha256"]
    row = {
        "dimension": 14,
        "offset_onb_coordinates": basis["affine_offset_onb_coordinates"],
        "basis_onb_coordinates": basis["basis_onb_coordinates"],
        "K": union["folded_columns_K"], "B": union["actual_usable_points_B_before_folding"],
        "base_file": str((BASE / "rectangle_keys.bin").relative_to(ROOT)),
        "base_sha256": union["key_sha256"],
        "factor_base_policy": "four-coset rectangle affine width-14 base, cofactor four, sign/Frobenius closure"
    }
    sources = [
        HERE / "prepare.py", HERE / "run.py", HERE / "control.py",
        ROOT / "ecc2k130/runner/codegen/curves.py",
        ROOT / "ecc2k130/runner/codegen/field.py",
        ROOT / "experiments/koblitz-pair-claw-20260929/orbit_key.py",
        ROOT / "experiments/m5-s3-gate-20261004/build_m5.py",
        ROOT / "experiments/m5-s3-gate-20261004/run_gate.py",
        ROOT / "experiments/compact-s3-m4-20261003/chain_s3.py",
        ROOT / "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
        ROOT / "experiments/compact-s3-m4-20261003/cofactor_preimages.py",
        ROOT / "experiments/compact-s3-m4-20261003/run_group_add_probe.py",
    ]
    assert all(path.is_file() for path in sources)
    protocol = {
        "kind": "n83_rectangle_width14_orbit_complete_five_summand_protocol",
        "proposal_id": "Q2026101291",
        "candidate_id": None,
        "curve_id": parent["curve_id"],
        "workload_id": parent["workload_id"],
        "workload": parent["workload"],
        "base_rows": [row],
        "summands": 5,
        "leaf_domain": "first leaf normalized to an affine seed; four other leaves independently select sign/Frobenius orbit members from exact rectangle width-14 base",
        "target_preimage_policy": parent["target_preimage_policy"],
        "solver": parent["solver"],
        "limits": parent["limits"],
        "run_order": [14],
        "timing_tier": "exploratory_local_unisolated",
        "comparison_variable": "factor-base affine width-14 subspace and exact keys; same target, summand count, orbit selectors, solver and limits",
        "basis_manifest_file": str(basis_path.relative_to(ROOT)),
        "basis_manifest_sha256": sha(basis_path),
        "base_receipt_file": str(union_path.relative_to(ROOT)),
        "base_receipt_sha256": sha(union_path),
        "base_replay_sha256": sha(union_replay_path),
        "parent_protocol_sha256": sha(parent_path),
        "parent_ordinary_result_sha256": sha(prior_run),
        "curve_identity_sha256": sha(IDENTITY),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in sources},
        "fixture_scalar_sha256": parent["fixture_scalar_sha256"],
        "fixture_is_input_to_solver": False,
    }
    output.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "frozen", "workload_id": protocol["workload_id"],
                      "K": row["K"], "B": row["B"]}), flush=True)


if __name__ == "__main__":
    main()
