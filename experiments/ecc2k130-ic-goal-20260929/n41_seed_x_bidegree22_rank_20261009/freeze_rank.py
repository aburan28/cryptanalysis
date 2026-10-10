#!/usr/bin/env python3
"""Freeze source, binary, sample, and bounds for exact M4RI rank."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "rank_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first bidegree-rank execution")
    protocol = json.loads((HERE / "protocol.json").read_text())
    sample = json.loads((HERE / "sample_receipt.json").read_text())
    if (sample["status"] != "FROZEN_EXACT_SAMPLE_WRITTEN" or
            sample["rows"] != protocol["sample_rows"] or
            sample["sample_sha256"] != sha(HERE / "sample.bin") or
            sample["sample_indices_sha256"] != sha(HERE / "sample_indices.bin")):
        raise ValueError("frozen exact sample changed")
    frozen = {
        "status": "FROZEN", "kind": "n41_two_pair_seed_x_bidegree_2_2_m4ri_rank",
        "curve_id": protocol["curve_id"], "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "rows": 80000, "features": 64859,
        "feature_order": protocol["tensor_feature_index"],
        "compiler": "clang++ -O3 -std=c++17 -I/var/tmp/sage-10.9-current/local/include -L/var/tmp/sage-10.9-current/local/lib -Wl,-rpath,/var/tmp/sage-10.9-current/local/lib rank.cpp -lm4ri -o rank",
        "limits": protocol["limits"],
        "input_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "sample.bin", "sample_indices.bin", "sample_receipt.json")},
        "source_sha256": {name: sha(HERE / name) for name in (
            "rank.cpp", "rank", "run_rank.py", "freeze_rank.py")},
        "decision_rule": protocol["decision_rule"],
    }
    output.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
