#!/usr/bin/env python3
"""Freeze the independent Sage audit of the public-point query panel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "audit_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first audit protocol")
    query = json.loads((HERE / "query_result.json").read_text())
    control = json.loads((HERE / "query_control.json").read_text())
    if (query["status"] != "COMPLETE_PANEL" or
            control["status"] != "EXIT_SUCCESS" or
            control["query_result_sha256"] != sha(HERE / "query_result.json") or
            control["residuals_sha256"] != sha(HERE / "residuals.bin")):
        raise ValueError("query panel prerequisite changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_public_q_quadratic_filter_sage_audit",
        "curve_id": query["curve_id"],
        "checked_residuals": 8192, "screened_residuals": 64,
        "wall_cap_seconds": 180, "rss_cap_bytes": 4294967296,
        "input_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "query_protocol_v3.json", "query_result.json",
            "query_control.json", "public_input.txt", "residuals.bin",
            "x_orbits.bin", "filters.bin", "sage-runtime-info.json")},
        "audit_source_sha256": sha(HERE / "audit_query.py"),
        "freeze_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
