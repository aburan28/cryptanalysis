#!/usr/bin/env python3
"""Freeze and prove the exact rootless pair before patching WDSat."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1481 = PARENT / "q20261011_n83_leaf_masks"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT.parent.parent / "ecc2k130/codegen"))
from field import Onb  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_freeze = json.loads((Q1481 / "freeze.json").read_text())
    parent_build = json.loads((Q1481 / "build_receipt.json").read_text())
    parent_analysis = json.loads((Q1481 / "analysis.json").read_text())
    samples = json.loads((Q1481 / "root_samples.json").read_text())
    assert protocol["proposal_id"] == "Q1482"
    assert protocol["polarity_phases"] == [4]
    assert [parent_freeze["inputs"][n]["workload_id"]
            for n in ("selected", "holdout")] == protocol["workload_ids"]
    first = samples["selected_phase4"]
    second = samples["holdout_phase4"]
    assert len(first) == len(second) == 1
    assert first[0]["leaf_bits"] == second[0]["leaf_bits"]
    assert first[0]["root_count"] == second[0]["root_count"] == 0
    bits = first[0]["leaf_bits"]
    assert len(bits) == 166 and bits[:83].count("1") == bits[83:].count("1") == 5
    onb = Onb(83)
    a = onb.fromCoords(int(bits[:83][::-1], 2))
    b = onb.fromCoords(int(bits[83:][::-1], 2))
    assert a and b and not s3_roots(onb, a, b)
    assert [r["phase"] for r in parent_analysis["cells"]["selected"] if
            r["rootless_pair_count_sampled"] and r["phase"] == 4] == [4]
    source = Path(parent_build["patched_source_path"]).parent
    assert sha(source / "wdsat.c") == parent_build["patched_wdsat_c_sha256"]
    frozen = {"proposal_id": "Q1482", "candidate_id": None, "run_id": None,
              "files_sha256": {n: sha(HERE / n) for n in
                               ("protocol.json", "freeze.py", "build.py",
                                "run.py", "analyze.py", "validate.py")},
              "rootless_pair1_bits": bits,
              "rootlessness_proof": "exact S3 quadratic trace via frozen s3_root_oracle; both nonzero leaves, five normal-basis bits each",
              "q1481_root_samples_sha256": sha(Q1481 / "root_samples.json"),
              "q1481_analysis_sha256": sha(Q1481 / "analysis.json"),
              "q1481_freeze_sha256": sha(Q1481 / "freeze.json"),
              "q1481_build_sha256": sha(Q1481 / "build_receipt.json"),
              "q1481_phase4_receipts_sha256": {
                  n: sha(Q1481 / "runs" / f"{n}_phase4" / "receipt.json")
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
    print("Q1482 frozen rootless", hashlib.sha256(bits.encode()).hexdigest()[:12])


if __name__ == "__main__":
    main()
