#!/usr/bin/env python3
"""Freeze Q1468 exact N53 pair-oracle code, inputs, and limits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
Q1467 = PARENT / "q1467_density_bridge"
PROTOCOL = HERE / "protocol.json"
SOURCES = (
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/"
    "make_inputs.py",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/"
    "pair_oracle.cpp",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/"
    "build.py",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/"
    "run_stage.py",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/"
    "freeze_protocol.py",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/"
    "root_field.hpp",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/"
    "n53_field.txt",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/"
    "n53_w3_26_orbits.json",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/"
    "inputs/n53_planted_unpinned/meta.json",
    "experiments/compact-s3-m4-20261003/q1467_density_bridge/"
    "inputs/n53_ordinary/meta.json",
)
INPUTS = ("base_points.txt", "n53_planted_unpinned_target.txt",
          "n53_ordinary_target.txt", "meta.json")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe() -> dict:
    assert {path.name for path in (HERE / "inputs").iterdir()} == set(INPUTS)
    meta = json.loads((HERE / "inputs/meta.json").read_text())
    assert meta["proposal_id"] == "Q1468"
    assert meta["candidate_id"] is None
    assert meta["isogeny"] == "none"
    assert meta["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert meta["factor_base_actual_B"] == 2756
    assert meta["folded_columns_K"] == 26
    assert meta["base_points_sha256"] == sha(HERE /
        "inputs/base_points.txt")
    for name in ("n53_planted_unpinned", "n53_ordinary"):
        assert meta["targets"][name]["q1467_meta_sha256"] == sha(
            Q1467 / "inputs" / name / "meta.json")
    binary = HERE / "native_oracle"
    compile_receipt_path = HERE / "compile_receipt.json"
    compile_receipt = json.loads(compile_receipt_path.read_text())
    assert compile_receipt["binary_sha256"] == sha(binary)
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    return {
        "kind": "q1468_exact_n53_pair_oracle_protocol",
        "proposal_id": "Q1468", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4mitm",
        "curve_id": meta["curve_id"], "degree_n": 53,
        "factor_base_actual_B": meta["factor_base_actual_B"],
        "folded_columns_K": meta["folded_columns_K"],
        "factor_base_enumerated_set_sha256": meta[
            "factor_base_enumerated_set_sha256"],
        "workloads": meta["targets"],
        "run_order": ["selftest", "n53_planted_unpinned",
                      "n53_ordinary"],
        "complete_cross_column_pair_count": 3651700,
        "native_wall_cap_seconds_per_phase": 600,
        "external_safeguard_seconds": 1250,
        "online_interval": (
            "native query phase after complete target-independent base and "
            "pair-table construction; process and table timing are "
            "supplemental cold-start diagnostics"),
        "claim_scope": (
            "exact presence or absence of a four-point sum with four "
            "distinct folded columns for one N53 public target, subject "
            "to complete enumeration and independent arithmetic replay; "
            "no N83 or N131 cost inference"),
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
        "source_sha256": {relative: sha(ROOT / relative)
                          for relative in SOURCES},
        "input_sha256": {leaf: sha(HERE / "inputs" / leaf)
                         for leaf in INPUTS},
        "compile_receipt_sha256": sha(compile_receipt_path),
        "binary_sha256": sha(binary),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "q1467_solver_protocol_sha256": sha(Q1467 / "solver_protocol.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = describe()
    if args.check:
        assert current == json.loads(PROTOCOL.read_text())
        print("Q1468 exact pair-oracle protocol: PASS")
    else:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(current, indent=2, sort_keys=True) +
                            "\n")
        print(json.dumps({"proposal_id": "Q1468",
                          "protocol_sha256": sha(PROTOCOL),
                          "run_order": current["run_order"]}))


if __name__ == "__main__":
    main()
