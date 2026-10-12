#!/usr/bin/env python3
"""Freeze the exact two-root pair, discriminator, and N83 public inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1485 = HERE.parent / "q20261011_n83_common_bit_probe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    previous = json.loads((Q1485 / "freeze.json").read_text())
    parent = json.loads((Q1485 / "build_receipt.json").read_text())
    assert protocol["proposal_id"] == "Q1489"
    assert protocol["variants"] == ["order_only", "root_domain"]
    assert [previous["inputs"][n]["workload_id"] for n in
            ("selected", "holdout")] == [protocol["selected_workload_id"],
                                        protocol["holdout_workload_id"]]
    source = Path(parent["patched_source_path"])
    assert sha(source) == parent["patched_wdsat_c_sha256"]
    roots = previous["supported_middle_root_coords"]
    discriminator = next(i for i in range(83) if (roots[0] ^ roots[1]) >> i & 1)
    assert discriminator == 6
    priority = list(range(2, 334)) + [417 + discriminator, 2140, 2141]
    assert len(priority) == len(set(priority)) == 335
    frozen = {
        "proposal_id": "Q1489", "candidate_id": None, "run_id": None,
        "files_sha256": {n: sha(HERE / n) for n in
                         ("protocol.json", "freeze.py", "build.py", "run.py",
                          "analyze.py", "validate.py")},
        "q1485_freeze_sha256": sha(Q1485 / "freeze.json"),
        "q1485_build_sha256": sha(Q1485 / "build_receipt.json"),
        "q1485_phase4_receipts_sha256": {
            n: sha(Q1485 / "runs" / f"{n}_phase4" / "receipt.json")
            for n in ("selected", "holdout")},
        "parent_source_path": str(source),
        "parent_source_sha256": sha(source),
        "parent_config_sha256": sha(source.parent / "config.h"),
        "supported_pair1_bits": previous["supported_pair1_bits"],
        "supported_middle_root_coords": roots,
        "root_discriminator_bit": discriminator,
        "root_discriminator_variable": 417 + discriminator,
        "priority": priority,
        "mask_schedule": previous["mask_schedule"],
        "inputs": previous["inputs"],
    }
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1489 frozen", sha(HERE / "freeze.json")[:12])


if __name__ == "__main__":
    main()
