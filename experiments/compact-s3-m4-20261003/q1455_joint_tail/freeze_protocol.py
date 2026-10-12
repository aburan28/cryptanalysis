#!/usr/bin/env python3
"""Freeze the exact Q1455 joint-pair control panel before its execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1423_target_coupled.target_inputs import target_list  # noqa: E402

OUTPUT = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_protocol() -> dict:
    q1452_path = PARENT / "q1452_known_satisfiable_phi5/controls.json"
    q1452 = json.loads(q1452_path.read_text())
    q1446_path = PARENT / "q1446_joint_pair_span/validation.json"
    q1446 = json.loads(q1446_path.read_text())
    q1436_path = PARENT / "q1436_affine_pair/protocol.json"
    q1436 = json.loads(q1436_path.read_text())
    q1420_path = PARENT / "q1420_root_theory/protocol.json"
    q1420 = json.loads(q1420_path.read_text())
    n83_parent = q1436["workloads"]["n83_free_partner"]
    n83_targets = target_list(83, "free_mids", q1420[
        "workloads"][n83_parent["parent_q1420_key"]])
    assert len(n83_targets) == 4
    controls = {}
    for n in (53, 83):
        base_path = PARENT / f"q1438_dense_base/n{n}_w{4 if n == 53 else 6}_base.json"
        base = json.loads(base_path.read_text())
        source = q1452 if n == 53 else q1446["controls"][1]
        assert base["curve_id"] == ("EC1N53Ckb1hf77aab617904" if n == 53
                                     else "EC1N83Ckb1h876c2921cb64")
        leaves = (source["known_witness_raw_leaf_x"] if n == 53
                  else source["point_relation"]["raw_leaf_x"])
        controls[str(n)] = {
            "curve_id": base["curve_id"],
            "factor_base_actual_B": base[
                "actual_usable_points_B_before_folding"],
            "folded_columns_K": base["signed_frobenius_columns_K"],
            "factor_base_enumerated_set_sha256": base[
                "enumerated_set_sha256"],
            "normal_basis_weight_bound": base["normal_basis_weight_bound"],
            "target_input_role": ("ordinary_known_satisfiable_slice"
                                  if n == 53 else "planted_witness_control"),
            "target_preimage_index": (q1452["target_preimage_index"]
                                      if n == 53 else 3),
            "raw_target_x": (q1452["selected_raw_target_x"]
                             if n == 53 else n83_targets[3]),
            "archived_group_verified_leaf_x": leaves,
            "base_receipt_sha256": sha(base_path),
        }
    source_paths = [HERE / "joint_tail.py", HERE / "run_controls.py",
                    Path(__file__), PARENT / "s3_root_oracle.py",
                    PARENT / "chain_s3.py",
                    PARENT / "q1423_target_coupled/target_inputs.py"]
    input_paths = [q1452_path, q1446_path, q1436_path, q1420_path,
                   HERE / "sage_runtime_info.json"]
    for n in (53, 83):
        input_paths.append(PARENT /
                           f"q1438_dense_base/n{n}_w{4 if n == 53 else 6}_base.json")
    return {
        "kind": "q1455_joint_bounded_pair_control_protocol",
        "proposal_id": "Q1455", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "enumerate weight-bounded completions for both partial leaf "
            "pairs, compute exact S3 pair-output sets, and join those sets "
            "through the selected public-target S3 link without fixing "
            "either pair intermediate first"),
        "claim_boundary": (
            "Exact x-coordinate feasibility control only. A no-chain "
            "outcome is a sound partial-assignment rejection within the "
            "declared weight bound; an x-only witness is not a verified "
            "elliptic-curve relation. These are correctness controls, not "
            "ordinary-query yield or successful-solve performance."),
        "n3_full_leaf_target_cases": 6 ** 4 * 7,
        "n3_partial_cases": 128,
        "n3_random_seed": 1455,
        "archived_controls": controls,
        "archived_witness_free_bits_per_leaf": 4,
        "archived_witness_pair_candidate_cap": 256,
        "source_sha256": {str(path.relative_to(HERE if path.parent == HERE
                                               else PARENT)): sha(path)
                          for path in source_paths},
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in input_paths},
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_protocol()
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1455 frozen joint-pair control protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1455", "degrees": [3, 53, 83]}))


if __name__ == "__main__":
    main()
