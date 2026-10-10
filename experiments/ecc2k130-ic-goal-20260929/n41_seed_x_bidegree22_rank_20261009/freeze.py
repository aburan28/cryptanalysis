#!/usr/bin/env python3
"""Freeze an exact N41 seed-x bidegree (2,2) rank experiment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "../n41_seed_bin_quadratic_filter_20261009"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError("preserve first bidegree-rank protocol")
    prior = json.loads((SOURCE / "saturation_audit.json").read_text())
    if (prior["status"] != "PASS_INDEPENDENT_ALL_BIN_GF2_RANK" or
            prior["processed_x_orbits"] != 1583568):
        raise ValueError("exact suffix support prerequisite changed")
    protocol = {
        "status": "FROZEN", "kind": "n41_two_pair_seed_x_bidegree_2_2_rank",
        "proposal_id": "Q20261010000000", "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "public_target_q": [1458168294740, 1672312028033],
        "field": "GF(2)[t]/(t^41+t^3+1)",
        "suffix_pair_rotations": [20, 30],
        "exact_x_orbits": 1583568, "sample_rows": 80000,
        "sample_random_seed": 20261010000000,
        "seed_feature_order": "constant; twelve seed bits s0..s5,t0..t5; lexicographic unordered products of two distinct seed bits",
        "seed_feature_count": 79,
        "x_feature_order": "constant; x bits 1..40; lexicographic unordered products of two distinct x bits",
        "x_feature_count": 821,
        "tensor_feature_index": "seed_feature_index * 821 + x_feature_index",
        "feature_count": 64859,
        "sample_rule": "Python random.sample without replacement of 80000 record indices from range(1583568), with frozen seed; sort indices before reading exact 12-byte orbit records; retain (s,t,x) in eight bytes per sample row",
        "decision_rule": "Full rank 64859 on exact sampled rows is an exact certificate of no universal bidegree-(2,2) seed-x Boolean equation on the complete suffix support. A nonfull rank requires basis extraction, fresh exact-row and public-residual checks before any pruning claim.",
        "limits": {"workers": 1, "rank_wall_seconds": 300,
                   "rss_bytes": 4294967296},
        "source_sha256": {name: sha(HERE / name) for name in
                          ("freeze.py", "sample.py")},
        "input_sha256": {name: sha(SOURCE / name) for name in
                         ("x_orbits.bin", "saturation_audit.json",
                          "resolve16_result.json", "resolve16_audit.json")},
        "claim_boundary": "N41 exact finite-sample rank gate for one compact symbolic family; N131 transfer and full one-target costs require separate evidence",
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "sha256": sha(output)}))


if __name__ == "__main__":
    main()
