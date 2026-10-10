#!/usr/bin/env python3
"""Freeze the exact receipts and analysis sources before calculation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
PARENT = ROOT / "experiments/compact-s3-m4-rational-root-scan-20261010"
BASE_PATHS = {
    "N53_W3": OLD / "bases/n53_weight3_orbits.json.gz",
    "N83_W5": OLD / "bases/n83_weight5_full_orbits.json",
    "N131_W5": OLD / "runs/n131_q1413_projected_x_w5.json",
    "N131_W6": OLD / "runs/n131_q1413_projected_x_w6.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = {
        "schema": "q20261010123500-freeze-v2",
        "proposal_id": "Q20261010123500",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "source_sha256": {name: sha(HERE / name)
                          for name in ("bound.py", "audit.py", "PROTOCOL.md")},
        "base_receipt_sha256": {label: sha(path)
                                for label, path in BASE_PATHS.items()},
        "n131_protocol_sha256": sha(OLD / "protocol.json"),
        "n83_kernel_receipt_sha256": sha(
            PARENT / "runs/n83_control_w4096.scan.json"),
        "input_law": "relation-query stream Q_i with uniform nonidentity subgroup marginal for every i; entire complete left schedule and query assignment independent of joint target vector; query correlation allowed",
        "rank_success_numerator": 19,
        "rank_success_denominator": 20,
        "left_fanout_values": [1, 2, 8],
        "source_sha256_self": sha(Path(__file__)),
    }
    path = HERE / "freeze.json"
    assert not path.exists()
    path.write_text(json.dumps(frozen, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(path)}))


if __name__ == "__main__":
    main()
