#!/usr/bin/env python3
"""Freeze the N41 public-point query panel before constructing its input."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPER = HERE / "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "query_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first query protocol")
    rank = json.loads((HERE / "rank_result.json").read_text())
    control = json.loads((HERE / "rank_control.json").read_text())
    if (rank["status"] != "EXACT_QUADRATIC_BIN_FILTERS" or
            rank["training_violations"] != 0 or
            rank["selected_equations"] != 31744 or
            control["status"] != "EXIT_SUCCESS" or
            control["filters_sha256"] != sha(HERE / "filters.bin")):
        raise ValueError("quadratic filter prerequisite changed")
    previous = json.loads((HERE / "protocol.json").read_text())
    query = {
        "status": "FROZEN", "kind": "n41_public_q_seed_bin_quadratic_filter_panel",
        "proposal_id": previous["proposal_id"], "candidate_id": None,
        "curve_id": previous["curve_id"],
        "public_target_q": previous["public_target_q"],
        "factor_base_size": 256, "folded_columns": 26,
        "pair_rotations": [0, 10, 20, 30],
        "first_two_pair_states_each": 1956,
        "seed_bins": 3969, "equations_per_bin": 8,
        "valid_prefix_cap": 8192,
        "prefix_order": "lexicographic pair index in rotation 0, then lexicographic pair index in rotation 10; skip overlapping folded columns",
        "phase_boundary": "target-dependent query begins at first Q-minus-prefix operation after target-independent input and filter-transpose setup, and ends after screening 8192 distinct-column prefixes and writing residual records",
        "decision_rule": "Each bin survives only if all its independently exact quadratic x equations vanish on the target residual; this is a necessary filter for a suffix completion. Record exact-support false positives in a separate read-only audit.",
        "compiler": "clang++ -O3 -std=c++17 -Wall -Wextra query_filter.cpp -o query_filter",
        "limits": {"workers": 1, "query_wall_seconds": 120,
                   "rss_bytes": 4294967296},
        "input_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "production.json", "rank_protocol.json",
            "rank_result.json", "rank_control.json", "filters.bin")},
        "source_sha256": {name: sha(HERE / name) for name in (
            "make_input.py", "query_filter.cpp", "query_filter", "freeze_query.py")},
        "helper_sha256": sha(HELPER),
        "claim_boundary": "A public-point filter stage on N41; exact leaf completion, one-target online recovery, and N131 transfer remain separate gates",
    }
    output.write_text(json.dumps(query, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
