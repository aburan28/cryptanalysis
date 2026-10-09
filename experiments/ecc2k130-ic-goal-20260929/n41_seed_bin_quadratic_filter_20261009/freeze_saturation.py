#!/usr/bin/env python3
"""Freeze the exact N41 rank-versus-support-size comparison."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "saturation_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first saturation protocol")
    rank8 = json.loads((HERE / "rank_result.json").read_text())
    rank16 = json.loads((HERE / "rank16_result.json").read_text())
    if (rank8["status"] != "EXACT_QUADRATIC_BIN_FILTERS" or
            rank16["status"] != "EXACT_QUADRATIC_BIN_FILTERS" or
            rank8["training_violations"] != 0 or
            rank16["training_violations"] != 0):
        raise ValueError("exact rank prerequisites changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_seed_bin_quadratic_rank_saturation",
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "proposal_id": "Q20261009232800", "candidate_id": None,
        "feature_count": 821, "bin_count": 3969,
        "decision_rule": "If every bin has rank min(exact support size, 821), all selected bin equations arise from support size below feature count; report every extra rank defect exactly.",
        "input_sha256": {name: sha(HERE / name) for name in (
            "x_orbits.bin", "filters.bin", "filters16.bin",
            "rank_result.json", "rank16_result.json", "rank_protocol.json",
            "rank16_protocol.json")},
        "producer_sha256": sha(HERE / "analyze_saturation.py"),
        "freeze_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
