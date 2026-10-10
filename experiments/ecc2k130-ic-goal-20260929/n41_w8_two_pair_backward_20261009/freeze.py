#!/usr/bin/env python3
"""Freeze source and input bytes before the two-pair table run."""

import json
from pathlib import Path

import build

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / "protocol.json"
    if path.exists():
        raise FileExistsError("preserve first frozen protocol")
    protocol = {"proposal_id": build.PROPOSAL_ID, "candidate_id": None,
                "time_cap_ns": build.LIMIT_NS, "rss_cap_bytes": build.LIMIT_RSS,
                "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
                "target_count": 1, "cold_or_warm": "warm_geometry_target_dependent_table",
                "source_sha256": {str(path): build.sha(path)
                                  for path in build.source_paths()}}
    path.write_text(json.dumps(protocol, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": "FROZEN_SOURCE", "files": len(protocol["source_sha256"])},
                     sort_keys=True))


if __name__ == "__main__":
    main()
