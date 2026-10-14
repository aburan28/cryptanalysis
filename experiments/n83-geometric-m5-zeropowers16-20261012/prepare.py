#!/usr/bin/env python3
"""Freeze the aligned-power width-16 stage on the existing N83 target."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODEGEN = ROOT / "ecc2k130/runner/codegen"
WIDTH = ROOT / "experiments/n83-geometric-width15-16-20261012"
PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
M5 = ROOT / "experiments/m5-s3-gate-20261004"
S3 = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(CODEGEN))

import curves  # noqa: E402
import field  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    protocol_path = HERE / "protocol.json"
    assert not protocol_path.exists()
    parent_dir = ROOT / "experiments/n83-geometric-m5-fixedpowers16-20261012"
    parent_path = parent_dir / "protocol.json"
    parent = json.loads(parent_path.read_text())
    assert parent["proposal_id"] == "Q2026101246"
    parent_result_path = parent_dir / "width16_ordinary.json"
    assert json.loads(parent_result_path.read_text())["status"] == "bounded_unknown"
    frontier_path = WIDTH / "frontier.json"
    frontier = json.loads(frontier_path.read_text())
    assert frontier["status"] == "complete_geometry_stage"
    assert frontier["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    replay_path = WIDTH / "independent_sage_replay.json"
    replay = json.loads(replay_path.read_text())
    assert replay["status"] == "PASS"
    identity_path = PAIR / "runs/n83_knownlog_orbit_base_k48194.json"
    identity = json.loads(identity_path.read_text())
    model = identity["curve_identity_record"]["curve"]
    assert identity["curve_id"] == frontier["curve_id"]
    order = model["subgroup_order"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(model["generator"])
    assert curves.isPrimeBig(order)
    assert curve.mul(generator, order) is None
    public = tuple(parent["workload"]["public_point_onb_raw"])
    assert public is not None and curve.onCurve(public)
    assert curve.mul(public, order) is None
    workload = parent["workload"]
    workload_id = parent["workload_id"]
    assert hashlib.sha256(canonical(workload)).hexdigest()[:12] == workload_id
    rows = []
    for dimension in (16,):
        row = next(row for row in frontier["rows"]
                   if row["dimension"] == dimension and
                   row["offset_onb_coordinates"] == 1 << 81)
        base_path = WIDTH / row["canonical_key_file"]
        assert sha(base_path) == row["canonical_key_sha256"]
        assert base_path.stat().st_size == 21 * row["folded_columns_K"]
        rows.append({"dimension": dimension, "offset_onb_coordinates": 1 << 81,
                     "K": row["folded_columns_K"],
                     "B": row["actual_usable_points_B_before_folding"],
                     "base_file": str(base_path.relative_to(ROOT)),
                     "base_sha256": sha(base_path),
                     "five_subset_first_moment": row["five_subset_first_moment"]})
    solver = Path(shutil.which("cryptominisat5") or "")
    assert solver.is_file(), "CryptoMiniSat is required for native XOR XCNF"
    sources = [Path(__file__), HERE / "run.py", M5 / "build_m5.py",
               M5 / "run_gate.py", S3 / "chain_s3.py",
               S3 / "chain_s3_multitarget.py",
               S3 / "cofactor_preimages.py", CODEGEN / "curves.py",
               CODEGEN / "field.py", PAIR / "orbit_key.py"]
    assert all(path.is_file() for path in sources)
    protocol = {
        "kind": "n83_shifted_width_16_aligned_power_five_summand_protocol",
        "proposal_id": "Q2026101247",
        "candidate_id": None,
        "curve_id": identity["curve_id"],
        "workload_id": workload_id,
        "workload": workload,
        "comparison_variable": "align all five affine-seed Frobenius powers while keeping all 332 rotated target choices",
        "method_comparison_parent": "Q2026101246 width-16 formula with relative powers 0,1,7,23,41 on the same target",
        "base_rows": rows,
        "base_construction": "all rational raw x in gamma82 + span(gamma1,...,gamma_d), projected by cofactor four and folded by sign and Frobenius",
        "leaf_domain": "five affine seeds with aligned relative Frobenius powers 0,0,0,0,0; target selector includes 83 rotations of each raw preimage",
        "fixed_relative_frobenius_powers": [0, 0, 0, 0, 0],
        "summands": 5,
        "target_preimage_policy": "all 83 Frobenius rotations of all four raw cofactor preimages of the public subgroup point",
        "solver": {"path": str(solver), "sha256": sha(solver),
                   "threads": 1, "max_conflicts": 5000000},
        "limits": {"wall_seconds_per_base": 600,
                   "sampled_solver_rss_stop_bytes": 4294967296,
                   "max_models_per_base": 64},
        "run_order": [16],
        "timing_tier": "exploratory_local_unisolated",
        "parent_frontier_sha256": sha(frontier_path),
        "parent_sage_replay_sha256": sha(replay_path),
        "curve_identity_sha256": sha(identity_path),
        "parent_protocol_sha256": sha(parent_path),
        "parent_result_sha256": sha(parent_result_path),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in sources},
        "fixture_scalar_sha256": parent["fixture_scalar_sha256"],
        "fixture_is_input_to_solver": False,
    }
    save(protocol_path, protocol)
    print(json.dumps({"status": "frozen", "workload_id": workload_id,
                      "bases": [[row["dimension"], row["K"], row["B"]]
                                for row in rows]}))


if __name__ == "__main__":
    main()
