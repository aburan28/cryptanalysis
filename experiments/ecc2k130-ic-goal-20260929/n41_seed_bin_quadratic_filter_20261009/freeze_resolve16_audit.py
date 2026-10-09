#!/usr/bin/env python3
"""Freeze independent Sage replay of the N41 exact relation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE / "../n41_two_free_pair_occupancy_20261009/result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "resolve16_audit_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first resolver-audit protocol")
    result = json.loads((HERE / "resolve16_result.json").read_text())
    control = json.loads((HERE / "resolve16_control.json").read_text())
    if (result["status"] != "FOUND_VERIFIED_RELATION" or
            control["status"] != "EXIT_SUCCESS" or
            control["result_sha256"] != sha(HERE / "resolve16_result.json")):
        raise ValueError("exact resolver prerequisite changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_public_q_compact_filter_sage_relation_audit",
        "curve_id": result["curve_id"], "public_target_q": result["public_target_q"],
        "sampled_exact_suffix_orbits": 128,
        "wall_cap_seconds": 180, "rss_cap_bytes": 4294967296,
        "input_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "resolve16_protocol.json", "resolve16_result.json",
            "resolve16_control.json", "filters16.bin", "x_orbits.bin",
            "sage-runtime-info.json")},
        "prior_census_path": str(PRIOR.resolve()),
        "prior_census_sha256": sha(PRIOR),
        "audit_source_sha256": sha(HERE / "audit_resolve16.py"),
        "freeze_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
