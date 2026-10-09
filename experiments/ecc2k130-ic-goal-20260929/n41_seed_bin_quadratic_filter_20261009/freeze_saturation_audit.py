#!/usr/bin/env python3
"""Freeze full independent Python GF(2) re-elimination of the N41 bins."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "saturation_audit_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first saturation-audit protocol")
    result = json.loads((HERE / "saturation_result.json").read_text())
    if result["status"] != "EXACT_ALL_BIN_QUADRATIC_RANK_SATURATION":
        raise ValueError("primary exact-rank result changed")
    frozen = {
        "status": "FROZEN", "kind": "n41_all_bin_quadratic_rank_independent_audit",
        "curve_id": result["curve_id"],
        "row_count": 1583568, "bin_count": 3969,
        "feature_count": 821,
        "wall_cap_seconds": 300, "rss_cap_bytes": 4294967296,
        "input_sha256": {name: sha(HERE / name) for name in (
            "saturation_protocol.json", "saturation_result.json", "x_orbits.bin")},
        "audit_source_sha256": sha(HERE / "audit_saturation.py"),
        "freeze_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
