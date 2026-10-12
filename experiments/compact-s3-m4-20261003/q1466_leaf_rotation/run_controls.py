#!/usr/bin/env python3
"""Check the Q1466 wide batched-root join on archived partial witnesses."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1455 = PARENT / "q1455_joint_tail"
BINARY = HERE / "native_solver"
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, join  # noqa: E402
from q1455_joint_tail.native_inputs import make_case  # noqa: E402

OUTPUT = HERE / "control_result.json"
PAIR_CAP = 250000


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_row(name: str) -> dict:
    n = 53 if "n53" in name else 83
    parent_run = Q1455 / "runs" / name
    parent_receipt = json.loads((parent_run / "receipt.json").read_text())
    raw, varmap, targets, formula, meta, variables, clauses = make_case(name)
    assert gzip.decompress((parent_run / "system.cnf.gz").read_bytes()) == raw
    assert (parent_run / "variables.txt").read_bytes() == varmap
    assert (parent_run / "targets.txt").read_bytes() == targets
    with tempfile.TemporaryDirectory(prefix=f"q1466-{name}-") as folder:
        cnf = Path(folder) / "system.cnf"
        model = Path(folder) / "model.txt"
        cnf.write_bytes(raw)
        completed = subprocess.run(
            [str(BINARY),
             str(PARENT / f"q1420_root_theory/n{n}_field.txt"),
             str(cnf), str(parent_run / "variables.txt"), str(model),
             "1000000", "60", str(parent_run / "targets.txt"),
             str(PAIR_CAP), "joint_tail_leaf_quarter_shift"],
            capture_output=True, text=True, timeout=75)
        assert completed.returncode == 0, (completed.returncode,
                                           completed.stderr,
                                           completed.stdout[-1200:])
        report = json.loads(completed.stdout)
        assert report["status"] == 10
        assert report["pair_cap"] == PAIR_CAP
        assert report["joint_eligible_checks"] > 0
        assert report["batch_inverse_batches"] > 0
        assert report["batch_denominators"] >= report[
            "batch_inverse_batches"]
        assert report["batch_root_inputs"] == sum(report["root_cache_misses"])
        assert report["joint_pair0_root_calls"] == (
            report["root_cache_hits"][0] + report["root_cache_misses"][0] +
            report["root_batch_reuses"][0])
        assert report["joint_pair1_root_calls"] == (
            report["root_cache_hits"][1] + report["root_cache_misses"][1] +
            report["root_batch_reuses"][1])
        target_values = [int(line, 16) for line in
                         targets.decode().splitlines()[1:]]
        onb = field.Onb(n)
        sampled = 0
        for expected, key in (("no_chain", "joint_rejection_snapshots"),
                              ("x_only_witness", "joint_hit_snapshots")):
            for snapshot in report[key]:
                leaves = tuple(PartialLeaf(int(mask, 16), int(ones, 16))
                               for mask, ones in zip(
                                   snapshot["leaf_fixed_mask_onb_hex"],
                                   snapshot["leaf_ones_onb_hex"]))
                observed = join(onb, leaves, target_values[
                    snapshot["target_preimage_index"]],
                    meta["normal_basis_weight_bound"], PAIR_CAP)
                assert observed["status"] == expected, (name, observed)
                assert observed["pair_candidate_counts"] == snapshot[
                    "pair_candidate_counts"]
                sampled += 1
        parent = json.loads((PARENT /
            "q1438_dense_base/solver_protocol.json").read_text())
        relation = model_relation(
            raw, formula, meta, variables, clauses, model,
            parent["instances"][str(n)])
        assert relation["status"] == "verified_four_point_relation"
    return {"case": name, "degree_n": n,
            "curve_id": parent_receipt["curve_id"],
            "parent_receipt_sha256": sha(parent_run / "receipt.json"),
            "joint_checks": report["joint_eligible_checks"],
            "joint_no_chain_rejections": report[
                "joint_no_chain_rejections"],
            "snapshots_independently_checked": sampled,
            "verified_relation": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = [check_row(name) for name in (
        "n53_partial_control", "n83_partial_control")]
    result = {"kind": "q1466_wide_batch_root_controls",
              "proposal_id": "Q1466", "candidate_id": None,
              "isogeny": "none", "status": "pass",
              "pair_candidate_cap": PAIR_CAP,
              "rows": rows, "binary_sha256": sha(BINARY),
              "source_sha256": sha(Path(__file__))}
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1466 wide batched-root controls: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1466", "control_rows": rows}))


if __name__ == "__main__":
    main()
