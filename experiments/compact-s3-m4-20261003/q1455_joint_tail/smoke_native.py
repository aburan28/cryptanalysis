#!/usr/bin/env python3
"""Exploratory native partial-witness check before freezing ordinary cells."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from chain_s3 import field  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, join  # noqa: E402
from q1455_joint_tail.native_inputs import make_case  # noqa: E402


def main() -> None:
    parent = json.loads((PARENT /
        "q1438_dense_base/solver_protocol.json").read_text())
    for name in ("n53_partial_control", "n83_partial_control"):
        n = 53 if "n53" in name else 83
        raw, varmap, targets, formula, meta, variables, clauses = make_case(name)
        with tempfile.TemporaryDirectory(prefix=f"q1455-{name}-") as folder:
            tmp = Path(folder)
            cnf, mapping, target_path, model_path = (
                tmp / file for file in ("system.cnf", "variables.txt",
                                        "targets.txt", "model.txt"))
            cnf.write_bytes(raw)
            mapping.write_bytes(varmap)
            target_path.write_bytes(targets)
            cap = 256 if n == 53 else 1024
            completed = subprocess.run(
                [str(HERE / "native_joint_solver"),
                 str(PARENT / f"q1420_root_theory/n{n}_field.txt"),
                 str(cnf), str(mapping), str(model_path),
                 "1000000", "30", str(target_path), str(cap),
                 "joint_tail_leaf_interleave"],
                capture_output=True, text=True, timeout=40)
            assert completed.returncode == 0, (
                name, completed.returncode, completed.stderr,
                completed.stdout[-1500:])
            report = json.loads(completed.stdout)
            assert report["status"] == 10
            assert report["joint_eligible_checks"] > 0
            target_values = [int(line, 16) for line in
                             targets.decode().splitlines()[1:]]
            onb = field.Onb(n)
            for status, key in (("no_chain", "joint_rejection_snapshots"),
                                ("x_only_witness", "joint_hit_snapshots")):
                for snapshot in report[key]:
                    leaves = tuple(PartialLeaf(int(mask, 16), int(ones, 16))
                                   for mask, ones in zip(
                                       snapshot["leaf_fixed_mask_onb_hex"],
                                       snapshot["leaf_ones_onb_hex"]))
                    checked = join(onb, leaves, target_values[
                        snapshot["target_preimage_index"]],
                        meta["normal_basis_weight_bound"], cap)
                    assert checked["status"] == status, (name, checked)
                    assert checked["pair_candidate_counts"] == snapshot[
                        "pair_candidate_counts"]
            relation = model_relation(
                raw, formula, meta, variables, clauses, model_path,
                parent["instances"][str(n)])
            assert relation["status"] == "verified_four_point_relation"
            print(json.dumps({"cell": name,
                              "joint_checks": report["joint_eligible_checks"],
                              "joint_rejections": report[
                                  "joint_no_chain_rejections"],
                              "verified_relation": True,
                              "solve_seconds": report["solve_seconds"]}))


if __name__ == "__main__":
    main()
