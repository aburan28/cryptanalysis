#!/usr/bin/env python3
"""Freeze per-bin quadratic rank and filter extraction."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "rank16_protocol.json"
    if output.exists():
        raise FileExistsError("preserve first rank protocol")
    production = json.loads((HERE / "production.json").read_text())
    if (production["status"] != "EXACT_X_ORBITS_WRITTEN" or
            production["counts"]["accepted_orbits"] != 1583568 or
            production["x_orbits_sha256"] != sha(HERE / "x_orbits.bin")):
        raise ValueError("exact orbit production changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_seed_bin_quadratic_x_filter_rank16",
        "proposal_id": "Q20261009232800", "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "bins": 3969, "orbits": 1583568,
        "feature_order": "constant; 40 x bits 1..40; lexicographic pairwise products of those 40 bits",
        "feature_count": 821, "selected_equations_per_bin": 16,
        "selection_rule": "Full M4RI RREF of all exact x rows in each seed-sum bin; select up to sixteen independent free-column kernel equations with minimum support, breaking ties by free-feature index; validate every selected equation on every original bin x.",
        "filter_encoding": "for each seed-sum pair in lexicographic 1..63 order, little-endian rank u16, equation count u8, reserved u8, then sixteen 13-word little-endian 64-bit coefficient vectors",
        "compiler": "clang++ -O3 -std=c++17 -I/var/tmp/sage-10.9-current/local/include -L/var/tmp/sage-10.9-current/local/lib -Wl,-rpath,/var/tmp/sage-10.9-current/local/lib rank_filter16.cpp -lm4ri -o rank_filter16",
        "limits": {"workers": 1, "wall_seconds": 300,
                   "rss_bytes": 4294967296},
        "input_sha256": {name: sha(HERE / name) for name in
                         ("protocol.json", "production.json", "x_orbits.bin")},
        "source_sha256": {name: sha(HERE / name) for name in
                          ("rank_filter16.cpp", "rank_filter16", "freeze_rank16.py")},
        "decision_rule": "A selected quadratic equation can reject a seed-sum bin for a proposed residual x before either pair leaf is fixed; exact membership and distinct columns are checked separately for all surviving bins.",
        "claim_boundary": "N41 bin-filter stage; an N131 transfer requires bounded construction and evaluation costs for its much larger seed-sum space",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
