#!/usr/bin/env python3
"""Freeze exact inputs and claim boundary for the d13 prefix frontier."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
INPUTS = {
    "bound_source": HERE / "bound.py",
    "audit_source": HERE / "audit.py",
    "freeze_source": HERE / "freeze.py",
    "d13_geometry": GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static/d13_exact_geometry_v1.json",
    "d13_candidate_manifest": GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json",
    "d13_pair_inverse_result": GOAL / "n131_d13_same_rotation_pairs_20261009/result.json",
    "n41_exact_census": GOAL / "n131_two_pair_prefix_density_20261008/n41_census.json",
    "n41_public_row": GOAL / "n41_two_free_pair_compact_lookup_20261009/public_search_v2.json",
    "n41_public_row_sage_audit": GOAL / "n41_two_free_pair_compact_lookup_20261009/sage_audit.json",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError("preserve first protocol")
    record = {
        "kind": "n131_d13_six_pair_prefix_frontier_protocol",
        "status": "FROZEN_BEFORE_BOUND_RUN",
        "proposal_id": "Q20261009224800",
        "candidate_id": None,
        "run_id": None,
        "curve_id": "EC1N131Ckb1h136f03e58c98",
        "n131_subgroup_order": "680564733841876926932320129493409985129",
        "valid_seed_codes_per_unrotated_domain": 4134,
        "pair_blocks": 6,
        "leaf_rotations": [0, 0, 22, 22, 44, 44,
                           66, 66, 88, 88, 110, 110],
        "target_law": "Q uniform among the r-1 nonidentity subgroup points, independently of a predeclared prefix schedule; this is a conditional complexity screen, not the frozen public point law",
        "prefix_policy": "For k free pair blocks, fix the other 6-k pair group outputs before seeing Q. Test L predeclared prefixes; apply the union bound to exact completion support.",
        "pair_domain_upper_policy": "Choose two distinct valid seed codes, then one of two signs for each leaf: at most 4*C(4134,2) ordered-sign group outputs per pair block. Folded-column exclusions and output collisions only lower support.",
        "online_cap_seconds": 600,
        "memory_cap_bytes": 4 * 1024**3,
        "workers": 1,
        "source_paths": {name: str(path) for name, path in INPUTS.items()},
        "source_sha256": {name: digest(path) for name, path in INPUTS.items()},
        "promotion_gate": "An N131 method must generate target-relevant prefixes or jointly eliminate multi-pair families; this bound alone authorizes no public-Q run.",
    }
    output.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    print("FROZEN_D13_PREFIX_FRONTIER")


if __name__ == "__main__":
    main()
