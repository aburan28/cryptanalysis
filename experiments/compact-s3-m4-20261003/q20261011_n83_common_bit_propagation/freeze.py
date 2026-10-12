#!/usr/bin/env python3
"""Freeze the Q1485 source, exact root pair, and ordinary inputs."""
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
    assert protocol["proposal_id"] == "Q1486"
    assert protocol["workload_ids"] == [previous["inputs"][n]["workload_id"]
                                        for n in ("selected", "holdout")]
    source = Path(parent["patched_source_path"])
    assert sha(source) == parent["patched_wdsat_c_sha256"]
    roots = previous["supported_middle_root_coords"]
    assert len(roots) == 2 and roots[0] != roots[1]
    frozen = {
        "proposal_id": "Q1486", "candidate_id": None, "run_id": None,
        "files_sha256": {name: sha(HERE / name) for name in
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
        "common_root_bit_count": previous["common_root_bit_count"],
        "mask_schedule": previous["mask_schedule"],
        "inputs": {n: previous["inputs"][n] for n in ("selected", "holdout")},
    }
    assert frozen["common_root_bit_count"] == 49
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1486 frozen", sha(HERE / "freeze.json")[:12])


if __name__ == "__main__":
    main()
