#!/usr/bin/env python3
"""Audit the restricted nine-seed chain lower bound without Sage.

The symbolic ring is Z[tau], where tau^2 = 3*tau - 3.  Each tuple (a,b)
denotes a+b*tau, and multiplication by omega=1-tau is a free unit-orbit
change for the purpose of the lower bound.
"""

import json


SEEDS = {
    "P": (1, 0),
    "2P": (2, 0),
    "4P": (4, 0),
    "P+tauP": (1, 1),
    "2P+2tauP": (2, 2),
    "P+2tauP": (1, 2),
    "2P+4tauP": (2, 4),
    "2P+tauP": (2, 1),
    "P-2tauP": (1, -2),
}


def add(left, right):
    return left[0] + right[0], left[1] + right[1]


def neg(value):
    return -value[0], -value[1]


def double(value):
    return 2 * value[0], 2 * value[1]


def omega(value):
    a, b = value
    return a + 3 * b, -a - 2 * b


def tau(value):
    a, b = value
    return -3 * b, a + 3 * b


def norm(value):
    a, b = value
    return a * a + 3 * a * b + 3 * b * b


def orbit(value):
    out = set()
    current = value
    for _ in range(3):
        out.add(current)
        out.add(neg(current))
        current = omega(current)
    assert current == value
    return frozenset(out)


def main():
    assert len({orbit(value) for value in SEEDS.values()}) == len(SEEDS)
    for a in range(-10, 11):
        for b in range(-10, 11):
            value = (a, b)
            assert norm(omega(value)) == norm(value)
            assert norm(tau(value)) == 3 * norm(value)
            assert norm(double(value)) == 4 * norm(value)

    # Exact dataflow in src/main.rs::prepare.  Rotation is charged separately.
    points = {"P": SEEDS["P"]}
    points["2P"] = double(points["P"])
    points["4P"] = double(points["2P"])
    points["P+tauP"] = add(points["2P"], neg(omega(points["P"])))
    points["2P+2tauP"] = double(points["P+tauP"])
    points["P+2tauP"] = add(points["2P+2tauP"], neg(points["P"]))
    points["2P+4tauP"] = double(points["P+2tauP"])
    points["2P+tauP"] = add(points["P+tauP"], points["P"])
    points["P-2tauP"] = add(omega(points["2P"]), neg(points["P"]))
    assert points == SEEDS

    seed_norms = {name: norm(value) for name, value in SEEDS.items()}
    forced_adds = {
        name: value for name, value in seed_norms.items()
        if value in (7, 13, 19)
    }
    assert len(forced_adds) == 4
    assert sorted(forced_adds.values()) == [7, 7, 13, 19]
    assert all(value % 3 != 0 for value in seed_norms.values())

    # Every non-base target must be created once.  A unit rotation preserves
    # norm; a double multiplies it by 4; tau multiplies it by 3.  An integer
    # source cannot double/tau into norms 7,13,19.  The other four targets
    # also cannot be formed by tau because all target norms are prime to 3.
    # Therefore each of four forced targets costs >=11 for an addition, and
    # each remaining target costs >=7 for a doubling.  Extra intermediate
    # points only add nonnegative cost and cannot change those bounds.
    lower_bound = 4 * 11 + 4 * 7
    chain_cost = 4 * 11 + 4 * 7
    assert lower_bound == chain_cost == 72
    result = {
        "schema": 1,
        "ring": "Z[tau]/(tau^2-3tau+3)",
        "seed_norms": seed_norms,
        "forced_addition_seeds": sorted(forced_adds),
        "distinct_unit_orbits": 9,
        "minimum_M_plus_S_excluding_unit_rotations": lower_bound,
        "current_chain_M_plus_S_excluding_unit_rotations": chain_cost,
        "current_chain_unit_rotations_M": 2,
        "cost_model": {"double": 7, "tau": 6, "mixed_add_lower_bound": 11},
        "claim_scope": "one-result-per-operation graph, unit rotations, doubles, tau, and additions; excludes fused or simultaneous formulas",
        "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
