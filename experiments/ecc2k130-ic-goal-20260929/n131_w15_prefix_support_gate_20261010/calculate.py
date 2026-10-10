#!/usr/bin/env python3
"""Exact support ceilings for target-independent W15 prefix probes."""

from fractions import Fraction
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
W15 = BASE / "n131_w15_coupled_sixpair_20261010/seed_sum_count.json"
W14 = BASE / "n41_upper_xor_projection_20261010/seed_sum_count.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gates(n, m, r, seconds):
    partitions = {
        "one_free_pair_fixed": (n, n * m * m),
        "one_constrained_four_atom_block_fixed": (m, n * n * m),
        "both_free_pairs_fixed": (n * n, m * m),
    }
    output = {}
    for name, (prefix_states, suffix_states) in partitions.items():
        occupancy = Fraction(min(suffix_states, r), r)
        q50 = max(1, (r + 2 * suffix_states - 1) // (2 * suffix_states))
        output[name] = {
            "prefix_state_count": str(prefix_states),
            "suffix_tuple_count_upper": str(suffix_states),
            "uniform_target_occupancy_upper": {
                "numerator": str(occupancy.numerator),
                "denominator": str(occupancy.denominator),
            },
            "distinct_prefixes_needed_before_union_upper_reaches_half": str(q50),
            "necessary_probe_rate_per_second": {
                "numerator": str(q50), "denominator": seconds,
            },
            "necessary_budget_per_probe_ms": {
                "numerator": seconds * 1000, "denominator": str(q50),
            },
        }
    return output


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    sources = {"freeze": HERE / "freeze.py", "calculator": Path(__file__),
               "independent_audit": HERE / "audit.py",
               "w15_exact_count": W15, "w14_exact_count": W14}
    assert protocol["status"] == "FROZEN_BEFORE_W15_PREFIX_SUPPORT_CALCULATION"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources.items()}
    w15 = json.loads(W15.read_text())
    w14 = json.loads(W14.read_text())["n131"]
    r = int(protocol["subgroup_order"])
    assert int(w15["group_order"]) == int(w14["group_order"]) == r
    assert w15["curve_id"] == protocol["curve_id"]
    seconds = protocol["wall_budget_seconds"]
    records = {}
    for name, record in (("w15", w15), ("w14", w14)):
        n = int(record["accepted_signed_pair_states_per_rotation"]
                if name == "w15" else record["signed_pair_states_per_rotation"])
        m = int(record["same_seed_two_pair_states"])
        total = int(record["six_pair_tuple_count"])
        assert n * n * m * m == total
        records[name] = {
            "signed_pair_states_per_rotation": str(n),
            "same_seed_two_pair_states": str(m),
            "six_pair_tuple_count": str(total),
            "group_wide_tuple_mean": {
                "numerator": str(Fraction(total, r).numerator),
                "denominator": str(Fraction(total, r).denominator),
            },
            "partitions": gates(n, m, r, seconds),
        }
    result = {
        "status": "PASS_EXACT_W15_PREFIX_SUPPORT_GATES",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "group_order": str(r),
        "records": records,
        "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                          **{name: sha(path) for name, path in sources.items()}},
        "interpretation": "necessary uniform-target union-bound probe counts for target-independent prefixes; not measured success rates or a statement about the fixed public point",
    }
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "w15_q50_one_free_pair":
                      records["w15"]["partitions"]["one_free_pair_fixed"][
                          "distinct_prefixes_needed_before_union_upper_reaches_half"]}))


if __name__ == "__main__":
    main()
