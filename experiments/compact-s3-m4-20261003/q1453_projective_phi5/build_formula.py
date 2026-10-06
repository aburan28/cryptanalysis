"""Division-free, target-specialized phi5 circuit in sparse x coordinates.

For d_i=x_i+1 and u_i=d_i^-1, define D=prod(d_i), E=D sum(u_i), and
S_j=D^2 elementary_j(u_i^2+u_i). Because u_i^2+u_i=x_i/d_i^2,
S_j are coefficients of prod(d_i^2+x_i z). Multiplying the published
phi5 invariant by D^8 gives the equation below with no inverse gates.
The sparse factor bases exclude x=1, so D is nonzero on every legal input.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import (  # noqa: E402
    Formula, field, multiplication_table, product, square_destinations)
from q1448_torsion_phi5.build_formula import (  # noqa: E402
    BASE, ORDINARY, const_bits, square_power, square_vector,
    transformed_targets, xor_vectors)


def projective_terms(formula: Formula, xs: list[list[int]], table,
                     destinations: list[int], one: list[int]) -> list[list[int]]:
    n = len(one)
    zero = [-1] * n
    d = one[:]
    e = zero[:]
    s = [one[:]] + [zero[:] for _ in range(5)]
    for processed, x in enumerate(xs):
        dx = xor_vectors(formula, x, one)
        dx2 = square_vector(dx, destinations)
        new_s = [zero[:] for _ in range(6)]
        for j in range(1, min(processed + 1, 5) + 1):
            new_s[j] = xor_vectors(
                formula, product(formula, s[j], dx2, table),
                product(formula, s[j - 1], x, table))
        new_d = product(formula, d, dx, table)
        new_s[0] = square_vector(new_d, destinations)
        e = xor_vectors(formula, product(formula, e, dx, table), d)
        d, s = new_d, new_s
    e2 = square_power(e, 1, destinations)
    e4 = square_power(e, 2, destinations)
    e8 = square_power(e, 3, destinations)
    e6 = product(formula, e2, e4, table)
    s2_2 = square_power(s[2], 1, destinations)
    s3_2 = square_power(s[3], 1, destinations)
    s3_4 = square_power(s[3], 2, destinations)
    s4_2 = square_power(s[4], 1, destinations)
    s5_2 = square_power(s[5], 1, destinations)
    s5_3 = product(formula, s[5], s5_2, table)
    s5_4 = square_power(s[5], 2, destinations)
    d2 = square_vector(d, destinations)
    return [
        e8,
        product(formula, e6, s[5], table),
        product(formula, e4, s4_2, table),
        product(formula, product(formula, e2, s3_2, table), s[5], table),
        s3_4,
        product(formula, e2, s5_3, table),
        product(formula, s2_2, s5_2, table),
        s5_4,
        product(formula, d2, s5_3, table),
    ]


def build(n: int, target_index: int = 0,
          raw_target_override: int | None = None,
          public_target_override=None):
    assert n in (53, 83)
    onb = field.Onb(n)
    base = json.loads(BASE[n].read_text())
    ordinary = json.loads(ORDINARY[n].read_text())
    assert base["curve_id"] == ordinary["curve_id"]
    raw_targets = [int(value) for value in ordinary[
        "raw_preimage_x_coordinates"]]
    if raw_target_override is None:
        assert 0 <= target_index < len(raw_targets)
        raw_target = raw_targets[target_index]
        public_target = ordinary["public_target"]
        full_preimage_count = len(raw_targets)
    else:
        assert target_index == 0
        assert public_target_override is not None
        raw_target = int(raw_target_override)
        public_target = public_target_override
        full_preimage_count = 1
    weight = int(base["normal_basis_weight_bound"])
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    for x in leaves:
        formula.at_most(x, weight)
        formula.clauses.append(x[:])
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    one = const_bits(onb.toCoords(onb.one()), n)
    target = const_bits(raw_target, n)
    terms = projective_terms(formula, [*leaves, target], table,
                             destinations, one)
    for position in range(n):
        formula.xor_relation([term[position] for term in terms])
    selector = formula.new()
    formula.clauses.append([-selector])
    meta = {
        "proposal_id": "Q1453", "candidate_id": None,
        "isogeny": "none",
        "curve_id": base["curve_id"],
        "field_degree_n": n,
        "normal_basis_weight_bound": weight,
        "factor_base_actual_B": base[
            "actual_usable_points_B_before_folding"],
        "folded_columns_K": base["signed_frobenius_columns_K"],
        "factor_base_enumerated_set_sha256": base[
            "enumerated_set_sha256"],
        "public_target": public_target,
        "raw_target_x_values": [raw_target],
        "transformed_target_u_values": transformed_targets(onb, [
            raw_target]),
        "target_preimage_index": target_index,
        "target_preimage_x_count": 1,
        "full_target_preimage_x_count": full_preimage_count,
        "leaf_x_variables": leaves,
        "target_selector_variables": [selector],
    }
    return formula, meta
