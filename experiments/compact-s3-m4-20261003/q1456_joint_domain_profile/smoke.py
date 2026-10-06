#!/usr/bin/env python3
"""Check Q1456 domain accounting against exact N53/N83 witness controls."""

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
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, option_count  # noqa: E402
from q1455_joint_tail.native_inputs import make_case  # noqa: E402

OUTPUT = HERE / "control_result.json"


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
    with tempfile.TemporaryDirectory(prefix=f"q1456-{name}-") as folder:
        cnf = Path(folder) / "system.cnf"
        model = Path(folder) / "model.txt"
        cnf.write_bytes(raw)
        completed = subprocess.run(
            [str(HERE / "domain_probe"),
             str(PARENT / f"q1420_root_theory/n{n}_field.txt"),
             str(cnf), str(parent_run / "variables.txt"), str(model),
             "1000000", "10", str(parent_run / "targets.txt"),
             str(256 if n == 53 else 1024)],
            capture_output=True, text=True, timeout=20)
        assert completed.returncode == 0, (completed.returncode,
                                           completed.stderr,
                                           completed.stdout[-1200:])
        report = json.loads(completed.stdout)
        assert report["status"] == 10
        assert report["unique_partial_states"] > 0
        assert len(report["domain_snapshots"]) == report[
            "unique_partial_states"]
        assert sum(row["unique_states"] for row in report[
            "max_pair_log2_histogram"]) == report["unique_partial_states"]
        onb = field.Onb(n)
        for snapshot in report["domain_snapshots"]:
            leaves = [PartialLeaf(int(mask, 16), int(ones, 16))
                      for mask, ones in zip(
                          snapshot["leaf_fixed_mask_onb_hex"],
                          snapshot["leaf_ones_onb_hex"])]
            counts = [option_count(leaf, n, meta[
                "normal_basis_weight_bound"]) for leaf in leaves]
            assert snapshot["pair_candidate_counts"] == [
                counts[0] * counts[1], counts[2] * counts[3]]
        parent = json.loads((PARENT /
            "q1438_dense_base/solver_protocol.json").read_text())
        relation = model_relation(
            raw, formula, meta, variables, clauses, model,
            parent["instances"][str(n)])
        assert relation["status"] == "verified_four_point_relation"
    return {"case": name, "degree_n": n,
            "curve_id": parent_receipt["curve_id"],
            "parent_receipt_sha256": sha(parent_run / "receipt.json"),
            "parent_cnf_archive_sha256": sha(parent_run / "system.cnf.gz"),
            "unique_partial_states": report["unique_partial_states"],
            "min_max_pair_candidates": report["min_max_pair_candidates"],
            "verified_relation": True,
            "snapshot_counts_independently_checked": len(
                report["domain_snapshots"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = [check_row(name) for name in (
        "n53_partial_control", "n83_partial_control")]
    result = {"kind": "q1456_native_domain_profile_control",
              "proposal_id": "Q1456", "candidate_id": None,
              "isogeny": "none", "status": "pass",
              "rows": rows, "binary_sha256": sha(HERE / "domain_probe"),
              "source_sha256": sha(Path(__file__))}
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1456 domain-profile controls: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1456",
                          "control_rows": rows}))


if __name__ == "__main__":
    main()
