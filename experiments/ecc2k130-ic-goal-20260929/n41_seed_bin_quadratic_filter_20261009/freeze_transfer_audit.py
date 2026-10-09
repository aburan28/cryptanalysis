#!/usr/bin/env python3
"""Freeze independent arithmetic audit of the literal N131 transfer."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTIER = HERE / "../first_pair_generation_frontier.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "transfer_audit_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first transfer-audit protocol")
    transfer = json.loads((HERE / "transfer_result.json").read_text())
    if transfer["status"] != "FAIL_LITERAL_N131_W18_MEMORY_AND_WORK_GATE":
        raise ValueError("literal transfer result changed")
    frozen = {
        "status": "FROZEN", "kind": "literal_n131_transfer_independent_integer_audit",
        "curve_id": transfer["curve_id"],
        "seed_bits": 18, "coordinate_bits": 130, "equations_per_bin": 16,
        "rss_cap_bytes": 4294967296, "wall_cap_seconds": 600,
        "input_sha256": {name: sha(HERE / name) for name in (
            "transfer_protocol.json", "transfer_result.json")},
        "frontier_sha256": sha(FRONTIER),
        "audit_source_sha256": sha(HERE / "audit_transfer.py"),
        "freeze_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
