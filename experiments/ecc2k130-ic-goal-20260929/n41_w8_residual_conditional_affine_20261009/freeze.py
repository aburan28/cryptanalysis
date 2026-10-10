#!/usr/bin/env python3
"""Freeze sources and exact input bytes before the N41 structural measurement."""

import json
from pathlib import Path

import run


def main():
    path = run.HERE / "protocol.json"
    if path.exists():
        raise FileExistsError("preserve first protocol")
    record = {"proposal_id": run.PROPOSAL_ID, "candidate_id": None,
              "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "coordinate_systems": ["x", "phi=1/(x+1)"],
              "feature_order": "1, label bits 0..19, label pairs lexicographic, coordinate bits 0..40, coordinate bit times label bit (coordinate-major)",
              "label_bits": "branch[0:2], compact(a4)[2:9], compact(a5)[9:16], signs[16:20]; compact removes fixed-zero mask bit 5",
              "label_feature_dimension": 211, "mixed_feature_dimension": 1072,
              "target_count": 1, "cap_ns": run.CAP_NS,
              "rss_cap_bytes": run.RSS_CAP,
              "source_sha256": {str(p): run.sha(p) for p in run.source_paths()}}
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(run.sha(path))


if __name__ == "__main__":
    main()
