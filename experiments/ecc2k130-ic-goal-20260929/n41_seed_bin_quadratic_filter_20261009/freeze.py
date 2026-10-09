#!/usr/bin/env python3
"""Freeze exact sign-orbit x collection before quadratic filtering."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SIGN = GOAL / "n41_two_pair_sign_orbit_x_support_20261009"
CENSUS = GOAL / "n41_two_free_pair_occupancy_20261009"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError("preserve first frozen protocol")
    files = {
        "sign_source": SIGN / "run.py",
        "sign_protocol": SIGN / "protocol.json",
        "sign_result": SIGN / "result.json",
        "sign_audit": SIGN / "audit.json",
        "geometry": CENSUS / "geometry_snapshot.json",
        "arithmetic": CENSUS / "arithmetic_snapshot.py",
        "census_result": CENSUS / "result.json",
        "census_audit": CENSUS / "audit.json",
    }
    protocol = {
        "status": "FROZEN", "kind": "n41_exact_seed_bin_two_pair_x_orbits",
        "proposal_id": "Q20261009232800", "candidate_id": None, "run_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "field": "GF(2)[t]/(t^41+t^3+1)",
        "curve": "y^2+xy=x^3+1", "subgroup_order": 549756390943,
        "public_target_q": [1458168294740, 1672312028033],
        "factor_base_size": 256, "folded_columns": 26,
        "suffix_pair_rotations": [20, 30], "pair_domain_sizes": [1956, 1956],
        "expected_orbits": 1583568, "expected_bin_min": 128,
        "expected_bin_max": 832,
        "row_encoding": "12 bytes per exact sign orbit: seed sums s,t (one byte each), six little-endian x bytes, two little-endian pair indices for each suffix domain",
        "orbit_rule": "For valid distinct-column pair indices (i,j), retain precisely the lexicographically smaller of (i,j) and their simultaneous negative pair indices; the retained x identifies one sign orbit.",
        "limits": {"workers": 1, "producer_wall_seconds": 300,
                   "rss_bytes": 4294967296},
        "inputs": {key: str(path) for key, path in files.items()},
        "input_sha256": {key: sha(path) for key, path in files.items()},
        "source_sha256": {name: sha(HERE / name) for name in
                          ("produce.py", "freeze.py")},
        "decision_rule": "Collect every exact sign-orbit x and seed-sum bin with the audited column and sign rules; stop on any count or resource mismatch.",
        "claim_boundary": "exact N41 target-independent source table for a candidate compact quadratic bin filter; online results and N131 transfer require separate frozen gates",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
