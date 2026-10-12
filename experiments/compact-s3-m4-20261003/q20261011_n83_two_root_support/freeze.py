#!/usr/bin/env python3
"""Freeze the exact two-root pair and parent solver before compilation."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1482 = PARENT / "q20261011_n83_rootless_nogood"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT.parent.parent / "ecc2k130/codegen"))
from chain_s3 import evaluate_s3  # noqa: E402
from field import Onb  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_freeze = json.loads((Q1482 / "freeze.json").read_text())
    parent_build = json.loads((Q1482 / "build_receipt.json").read_text())
    samples = json.loads((Q1482 / "root_samples.json").read_text())
    assert protocol["proposal_id"] == "Q1483"
    assert protocol["polarity_phases"] == [4]
    assert [parent_freeze["inputs"][n]["workload_id"]
            for n in ("selected", "holdout")] == protocol["workload_ids"]
    left, right = samples["selected"], samples["holdout"]
    assert len(left) == len(right) == 1
    assert left[0]["leaf_bits"] == right[0]["leaf_bits"]
    assert left[0]["root_coords"] == right[0]["root_coords"]
    bits, roots = left[0]["leaf_bits"], left[0]["root_coords"]
    assert len(bits) == 166 and bits[:83].count("1") == bits[83:].count("1") == 5
    assert len(roots) == 2 and roots[0] != roots[1]
    onb = Onb(83)
    a = onb.fromCoords(int(bits[:83][::-1], 2))
    b = onb.fromCoords(int(bits[83:][::-1], 2))
    assert a and b and [onb.toCoords(c) for c in s3_roots(onb, a, b)] == roots
    for root in roots:
        assert evaluate_s3(onb, a, b, onb.fromCoords(root)) == 0
    source = Path(parent_build["patched_source_path"]).parent
    assert sha(source / "wdsat.c") == parent_build["patched_wdsat_c_sha256"]
    frozen = {"proposal_id": "Q1483", "candidate_id": None, "run_id": None,
              "files_sha256": {n: sha(HERE / n) for n in
                               ("protocol.json", "freeze.py", "build.py",
                                "run.py", "analyze.py", "validate.py")},
              "supported_pair1_bits": bits,
              "supported_middle_root_coords": roots,
              "support_proof": "both exact roots of S3 for one complete pair-1 assignment; assigned middle bits must be consistent with at least one root",
              "q1482_root_samples_sha256": sha(Q1482 / "root_samples.json"),
              "q1482_freeze_sha256": sha(Q1482 / "freeze.json"),
              "q1482_build_sha256": sha(Q1482 / "build_receipt.json"),
              "q1482_phase4_receipts_sha256": {
                  n: sha(Q1482 / "runs" / f"{n}_phase4" / "receipt.json")
                  for n in ("selected", "holdout")},
              "parent_source_dir": str(source),
              "parent_wdsat_c_sha256": sha(source / "wdsat.c"),
              "parent_config_sha256": sha(source / "config.h"),
              "mask_schedule": parent_freeze["mask_schedule"],
              "inputs": {n: parent_freeze["inputs"][n]
                         for n in ("selected", "holdout")},
              "s3_oracle_source_sha256": sha(PARENT / "s3_root_oracle.py"),
              "field_source_sha256": sha(PARENT.parent.parent /
                                         "ecc2k130/codegen/field.py")}
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1483 frozen", hashlib.sha256(bits.encode()).hexdigest()[:12])


if __name__ == "__main__":
    main()
