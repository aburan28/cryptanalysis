#!/usr/bin/env python3
"""Exact W16 support arithmetic for target Frobenius-orbit probing."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WIDTH = ROOT / "n131_w16_w18_sixpair_width_gate_20261010" / "result.json"
RHO_IDENTITY = ROOT / "n131_rho_reference_identity_audit_v5.json"
R = 680564733841876926932320129493409985129


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    width = json.loads(WIDTH.read_text())
    item = next(row for row in width["widths"] if row["degree"] == 16)
    n = item["signed_pair_states_N"]
    m = item["same_seed_two_pair_states_M"]
    eigen = int(json.loads(RHO_IDENTITY.read_text())["frobenius_eigenvalue_mod_subgroup_order"])
    assert (eigen * eigen + eigen + 2) % R == 0
    assert pow(eigen, 131, R) == 1
    assert eigen != 1
    single = Fraction(n * m * m, R)
    assert 0 < single < 1
    minimum = (R + 2 * n * m * m - 1) // (2 * n * m * m)
    assert minimum == item["minimum_one_free_pair_prefixes_for_half_union_ceiling"]
    result = {
        "status": "PASS_EXACT_ORBIT_SUPPORT_ARITHMETIC",
        "curve_id": width["curve_id"],
        "subgroup_order": str(R),
        "frobenius_eigenvalue_mod_r": str(eigen),
        "orbit_length_for_nontrivial_prime_subgroup_point": 131,
        "w16_signed_pair_states_N": n,
        "w16_same_seed_two_pair_states_M": m,
        "single_fixed_prefix_uniform_target_union_ceiling": str(single),
        "minimum_distinct_orientations_for_half_union_ceiling": minimum,
        "all_131_orientations_union_ceiling": str(min(1, 131 * single)),
        "meaning": "Upper support bound only; no target-specific membership, independence, extraction, or N131 timing inference",
        "source_sha256": {"script": digest(__file__), "width_census": digest(WIDTH),
                          "n131_frobenius_identity": digest(RHO_IDENTITY)},
    }
    with (HERE / "transfer.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({k: result[k] for k in (
        "status", "single_fixed_prefix_uniform_target_union_ceiling",
        "minimum_distinct_orientations_for_half_union_ceiling",
        "all_131_orientations_union_ceiling")}))


if __name__ == "__main__":
    main()
