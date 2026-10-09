#!/usr/bin/env python3
"""Freeze the second, sixteen-equation public-Q filter panel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPER = HERE / "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "query16_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first sixteen-equation query protocol")
    rank = json.loads((HERE / "rank16_result.json").read_text())
    control = json.loads((HERE / "rank16_control.json").read_text())
    first = json.loads((HERE / "query_result.json").read_text())
    if (rank["status"] != "EXACT_QUADRATIC_BIN_FILTERS" or
            rank["training_violations"] != 0 or
            control["status"] != "EXIT_SUCCESS" or
            control["filters_sha256"] != sha(HERE / "filters16.bin") or
            first["status"] != "COMPLETE_PANEL"):
        raise ValueError("previous filter and query prerequisites changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_public_q_seed_bin_quadratic_filter16_panel",
        "proposal_id": "Q20261009232800", "candidate_id": None,
        "curve_id": first["curve_id"], "public_target_q": first["public_target_q"],
        "valid_prefix_cap": 8192, "seed_bins": 3969,
        "selected_equations_per_bin": 16,
        "pair_rotations": [0, 10, 20, 30],
        "phase_boundary": "target-dependent query begins at first Q-minus-prefix operation after target-independent input and filter-transpose setup, and ends after 8192 distinct-column prefixes",
        "decision_rule": "Screen every suffix seed-sum bin with all exact quadratic equations selected for it; compare survivor counts against the eight-equation panel on the same ordered prefixes.",
        "compiler": "clang++ -O3 -std=c++17 -Wall -Wextra query_filter16.cpp -o query_filter16",
        "limits": {"workers": 1, "query_wall_seconds": 120,
                   "rss_bytes": 4294967296},
        "input_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "query_protocol_v3.json", "query_result.json",
            "query_audit.json", "public_input.txt", "public_input_receipt.json",
            "rank16_protocol.json", "rank16_result.json", "rank16_control.json",
            "filters16.bin")},
        "source_sha256": {name: sha(HERE / name) for name in (
            "query_filter16.cpp", "query_filter16", "run_query16.py",
            "freeze_query16.py")},
        "helper_sha256": sha(HELPER),
        "claim_boundary": "N41 filter stage; exact leaf resolution and N131 transfer require separate gates",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
