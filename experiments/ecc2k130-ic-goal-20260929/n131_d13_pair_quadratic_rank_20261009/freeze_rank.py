#!/usr/bin/env python3
"""Bind the exact sample, both binaries, runner, and limits before rank work."""

import json
from pathlib import Path

import freeze

HERE = Path(__file__).resolve().parent


def main():
    output = HERE / "rank_protocol.json"
    if output.exists():
        raise FileExistsError(output)
    base = json.loads((HERE / "protocol.json").read_text())
    sample = json.loads((HERE / "sample_result.json").read_text())
    if sample["sample_sha256"] != freeze.sha(HERE / "sample.bin"):
        raise ValueError("exact sample changed")
    names = ("rank.cpp", "audit_rank.cpp", "rank", "audit_rank",
             "run_rank.py", "freeze_rank.py")
    receipt = {
        "status": "FROZEN", "kind": "n131_d13_pair_quadratic_rank_binaries",
        "proposal_id": base["proposal_id"], "curve_id": base["curve_id"],
        "sample_sha256": sample["sample_sha256"],
        "base_protocol_sha256": freeze.sha(HERE / "protocol.json"),
        "sample_rows": base["sample_rows"],
        "features": base["quadratic_features"],
        "per_method_wall_cap_seconds": base["rank_wall_cap_seconds"],
        "rss_cap_bytes": base["rss_cap_bytes"],
        "source_sha256": {name: freeze.sha(HERE / name) for name in names},
        "compiler": {
            "rank": "clang++ -O3 -std=c++17 -Ithird_party/sage-binary/local/include -Lthird_party/sage-binary/local/lib -Wl,-rpath,/Volumes/SSD990/cryptanalysis/third_party/sage-binary/local/lib rank.cpp -lm4ri -o rank",
            "audit_rank": "clang++ -O3 -std=c++17 audit_rank.cpp -o audit_rank",
        },
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "rows": receipt["sample_rows"],
                      "features": receipt["features"]}))


if __name__ == "__main__":
    main()
