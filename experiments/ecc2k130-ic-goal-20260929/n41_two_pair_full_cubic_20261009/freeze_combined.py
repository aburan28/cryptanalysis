#!/usr/bin/env python3
"""Freeze combined coordinate-rank check before execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "combined_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first combined protocol")
    original = json.loads((HERE / "protocol.json").read_text())
    subgroup = json.loads((HERE / "subgroup_coordinate_rank.json").read_text())
    if (original["row_count"] != 80000 or
            subgroup["status"] != "POINT_CAP_REACHED" or
            subgroup["points_sampled"] != 6000):
        raise ValueError("frozen pair or subgroup prerequisite changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_pair_plus_subgroup_coordinate_rank",
        "proposal_id": original["proposal_id"], "candidate_id": None,
        "curve_id": original["curve_id"], "pair_rows": 80000,
        "subgroup_rows": 6000,
        "decision_rule": "Low-pivot GF(2) rank on all 80000 exact two-pair coordinate rows, then the same 6000 deterministic subgroup points. Zero novel rank establishes equal evaluation row spans on these samples.",
        "limits": {"workers": 1, "wall_seconds": 180, "rss_bytes": 4294967296},
        "input_sha256": {name: digest(HERE / name) for name in
                         ("protocol.json", "rank.json", "rows.bin",
                          "subgroup_protocol.json", "subgroup_coordinate_rank.json",
                          "produce.py")},
        "source_sha256": digest(HERE / "combined_coordinate_rank.py"),
        "claim_boundary": "independent combined finite-sample span comparison; symbolic universality on every subgroup point remains unproved",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": digest(output)}))


if __name__ == "__main__":
    main()
