#!/usr/bin/env python3
"""Freeze the bounded N41 ordinary public-Q row search with exact pair leaves."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPER = HERE / "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "resolve16_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first sixteen-equation resolver protocol")
    query = json.loads((HERE / "query16_result.json").read_text())
    control = json.loads((HERE / "query16_control.json").read_text())
    if (query["status"] != "COMPLETE_PANEL" or
            query["valid_prefixes"] != 8192 or
            control["status"] != "EXIT_SUCCESS" or
            control["query_result_sha256"] != sha(HERE / "query16_result.json") or
            control["residuals_sha256"] != sha(HERE / "residuals16.bin")):
        raise ValueError("sixteen-equation query prerequisite changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_public_q_compact_filter_exact_two_pair_resolver",
        "proposal_id": "Q20261009232800", "candidate_id": None,
        "curve_id": query["curve_id"], "public_target_q": query["public_target_q"],
        "field": "GF(2)[t]/(t^41+t^3+1)", "curve": "y^2+xy=x^3+1",
        "subgroup_order": 549756390943,
        "factor_base_size": 256, "folded_columns": 26,
        "pair_rotations": [0, 10, 20, 30],
        "valid_prefix_cap": 600000,
        "seed_bins": 3969, "selected_equations_per_bin": 16,
        "allowed_reusable_data": "four 1956-state pair domains, one hash index of 1956 left-suffix pair points, right-suffix pair states grouped by seed, and the 6.6-MB exact quadratic filter table; no four-summand vector table or x-support lookup",
        "target_rule": "scan distinct-column first-two pair prefixes lexicographically; evaluate all bin equations on Q minus prefix; visit only surviving right-suffix seed buckets, hash needed left-suffix pair point, and check all eight columns and exact group equality",
        "stop_rule": "first verified ordinary eight-column relation for the frozen public Q; otherwise preserve PREFIX_CAP, TIME_CAP, MEMORY_CAP, or failure",
        "phase_boundary": "online starts at first target-minus-first-pair operation after target-independent pair and filter construction; ends after exact native group verification of first relation or cap",
        "compiler": "clang++ -O3 -std=c++17 -Wall -Wextra resolve16.cpp -o resolve16",
        "limits": {"workers": 1, "online_wall_seconds": 120,
                   "rss_bytes": 4294967296},
        "input_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "public_input.txt", "public_input_receipt.json",
            "rank16_protocol.json", "rank16_result.json", "rank16_control.json",
            "filters16.bin", "query16_protocol.json", "query16_result.json",
            "query16_control.json", "residuals16.bin")},
        "source_sha256": {name: sha(HERE / name) for name in (
            "filter16_core.hpp", "resolve16.cpp", "resolve16",
            "run_resolve16.py", "freeze_resolve16.py")},
        "helper_sha256": sha(HELPER),
        "claim_boundary": "N41 ordinary-row search stage only; final relation matrix and one-target DLP recovery are separate gates",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
