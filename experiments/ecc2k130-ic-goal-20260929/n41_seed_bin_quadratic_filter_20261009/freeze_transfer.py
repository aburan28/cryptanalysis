#!/usr/bin/env python3
"""Freeze exact N131 transfer arithmetic against the audited W18 frontier."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTIER = HERE / "../first_pair_generation_frontier.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "transfer_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first transfer protocol")
    result = json.loads((HERE / "resolve16_result.json").read_text())
    audit = json.loads((HERE / "resolve16_audit.json").read_text())
    if (result["status"] != "FOUND_VERIFIED_RELATION" or
            audit["status"] != "PASS_INDEPENDENT_SAGE_ORDINARY_RELATION_REPLAY"):
        raise ValueError("N41 prerequisite changed")
    protocol = {
        "status": "FROZEN", "kind": "n131_literal_quadratic_bin_filter_transfer",
        "curve_id": "EC1N131Ckb1h136f03e58c98",
        "proposal_id": "Q20261009232800", "candidate_id": None,
        "field_degree": 131, "subspace_dimension": 18,
        "limits": {"workers": 1, "wall_seconds": 600,
                   "rss_bytes": 4294967296},
        "input_sha256": {name: sha(HERE / name) for name in (
            "resolve16_protocol.json", "resolve16_result.json",
            "resolve16_audit.json", "rank16_protocol.json", "rank16_result.json",
            "query16_protocol.json", "query16_result.json")},
        "frontier_sha256": sha(FRONTIER),
        "producer_sha256": sha(HERE / "transfer_bound.py"),
        "freeze_source_sha256": sha(Path(__file__)),
        "decision_rule": "Reject direct N131 transfer if even a one-bit pair-state domain or the literal fixed-size bin filter table exceeds 4 GiB, or the source's pair-pair enumeration requires more than 600 seconds at its necessary work rate.",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
