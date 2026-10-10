#!/usr/bin/env python3
"""Freeze independent replay of exact sampled rows and feature order."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "../n41_seed_bin_quadratic_filter_20261009"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "audit_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first bidegree-rank audit protocol")
    rank = json.loads((HERE / "rank_result.json").read_text())
    control = json.loads((HERE / "rank_control.json").read_text())
    if (control["status"] != "EXIT_SUCCESS" or
            control["rank_result_sha256"] != sha(HERE / "rank_result.json") or
            rank["status"] != "FULL_FEATURE_RANK" or
            rank["rows"] != 80000):
        raise ValueError("rank prerequisite changed")
    frozen = {
        "status": "FROZEN", "kind": "n41_seed_x_bidegree_2_2_independent_audit",
        "curve_id": rank["curve_id"],
        "sample_rows": 80000, "sage_replayed_orbits": 64,
        "wall_cap_seconds": 180, "rss_cap_bytes": 4294967296,
        "input_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "sample.bin", "sample_indices.bin",
            "sample_receipt.json", "rank_protocol.json", "rank_result.json",
            "rank_control.json", "sage-runtime-info.json")},
        "source_x_orbits_sha256": sha(SOURCE / "x_orbits.bin"),
        "source_geometry_sha256": sha(Path(json.loads((SOURCE / "protocol.json").read_text())["inputs"]["geometry"])),
        "audit_source_sha256": sha(HERE / "audit.py"),
        "freeze_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
