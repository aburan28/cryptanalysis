"""Compact torsion-symmetrized five-input relation over the exact sparse base.

For y^2+xy=x^3+1, use phi(P)=1/(x(P)+1). The invariant polynomial
P_phi,5 is from Faugere-Huot-Joux-Renault-Vitse, Eurocrypt 2014,
Section 5.1, with gamma=1 and lambda=0. It is evaluated as a circuit in
e1=sum(u_i) and s_j=elementary_j(u_i^2+u_i), without expanding S5.
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
from chain_s3_multitarget import choose_target_x  # noqa: E402

ORDINARY = {
    53: PARENT / "runs/n53_q1410_ordinary.json",
    83: PARENT / "runs/n83_q1408_ordinary.json",
}
BASE = {
    53: PARENT / "q1438_dense_base/n53_w4_base.json",
    83: PARENT / "q1438_dense_base/n83_w6_base.json",
}


def const_bits(value: int, n: int) -> list[int]:
    return [1 if value >> i & 1 else -1 for i in range(n)]


def xor_lit(formula: Formula, a: int, b: int) -> int:
    if a == -1:
        return b
    if b == -1:
        return a
    if a == 1:
        return -b
    if b == 1:
        return -a
    if a == b:
        return -1
    if a == -b:
        return 1
    out = formula.new()
    formula.xor_relation((out, a, b))
    return out


def xor_vectors(formula: Formula, a: list[int], b: list[int]) -> list[int]:
    assert len(a) == len(b)
    return [xor_lit(formula, x, y) for x, y in zip(a, b)]


def square_vector(a: list[int], destinations: list[int]) -> list[int]:
    result = [-1] * len(a)
    for source, dest in enumerate(destinations):
        result[dest] = a[source]
    return result


def square_power(a: list[int], k: int,
                 destinations: list[int]) -> list[int]:
    for _ in range(k):
        a = square_vector(a, destinations)
    return a


def phi5_terms(formula: Formula, us: list[list[int]], table,
               destinations: list[int]) -> list[list[int]]:
    """Return the nine summands of P_phi,5 in the published invariant form."""
    n = len(us[0])
    assert len(us) == 5 and all(len(u) == n for u in us)
    e1 = [-1] * n
    s = [[-1] * n for _ in range(6)]
    for processed, u in enumerate(us):
        e1 = xor_vectors(formula, e1, u)
        y = xor_vectors(formula, square_vector(u, destinations), u)
        for j in range(min(processed + 1, 5), 1, -1):
            s[j] = xor_vectors(formula, s[j],
                               product(formula, s[j - 1], y, table))
        s[1] = xor_vectors(formula, s[1], y)
    e2 = square_power(e1, 1, destinations)
    e4 = square_power(e1, 2, destinations)
    e8 = square_power(e1, 3, destinations)
    e6 = product(formula, e2, e4, table)
    s2_2 = square_power(s[2], 1, destinations)
    s3_2 = square_power(s[3], 1, destinations)
    s3_4 = square_power(s[3], 2, destinations)
    s4_2 = square_power(s[4], 1, destinations)
    s5_2 = square_power(s[5], 1, destinations)
    s5_3 = product(formula, s[5], s5_2, table)
    s5_4 = square_power(s[5], 2, destinations)
    return [
        e8,
        product(formula, e6, s[5], table),
        product(formula, e4, s4_2, table),
        product(formula, product(formula, e2, s3_2, table), s[5], table),
        s3_4,
        product(formula, e2, s5_3, table),
        product(formula, s2_2, s5_2, table),
        s5_4,
        s5_3,
    ]


def transformed_targets(onb, raw_x_values: list[int]) -> list[int]:
    one = onb.one()
    answer = []
    for value in raw_x_values:
        x = onb.fromCoords(int(value))
        if x == one:
            raise ValueError("phi is undefined at target x=1")
        u = onb.pow(x ^ one, (1 << onb.m) - 2)
        assert onb.mul(u, x ^ one) == one
        answer.append(onb.toCoords(u))
    assert len(answer) == len(set(answer))
    return answer


def build(n: int, raw_targets_override: list[int] | None = None,
          public_target_override=None):
    assert n in (53, 83)
    onb = field.Onb(n)
    base = json.loads(BASE[n].read_text())
    parent = json.loads(ORDINARY[n].read_text())
    weight = int(base["normal_basis_weight_bound"])
    assert base["curve_id"] == parent["curve_id"]
    raw_targets = ([int(x) for x in parent["raw_preimage_x_coordinates"]]
                   if raw_targets_override is None else
                   [int(x) for x in raw_targets_override])
    u_targets = transformed_targets(onb, raw_targets)
    formula = Formula()
    xs = [[formula.new() for _ in range(n)] for _ in range(4)]
    us = [[formula.new() for _ in range(n)] for _ in range(4)]
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    one = const_bits(onb.toCoords(onb.one()), n)
    for x, u in zip(xs, us):
        formula.at_most(x, weight)
        formula.clauses.append(x[:])  # excludes 2-torsion x=0
        x_plus_one = xor_vectors(formula, x, one)
        inverse_check = product(formula, u, x_plus_one, table)
        for bit, expected in zip(inverse_check, one):
            formula.clauses.append([bit if expected == 1 else -bit])
    u_target, selector = choose_target_x(formula, n, u_targets)
    terms = phi5_terms(formula, [*us, u_target], table, destinations)
    for position in range(n):
        formula.xor_relation([term[position] for term in terms])
    meta = {
        "proposal_id": "Q1448",
        "candidate_id": None,
        "isogeny": "none",
        "curve_id": base["curve_id"],
        "field_degree_n": n,
        "normal_basis_weight_bound": weight,
        "factor_base_actual_B": base["actual_usable_points_B_before_folding"],
        "folded_columns_K": base["signed_frobenius_columns_K"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "public_target": (parent["public_target"] if
                          public_target_override is None else
                          public_target_override),
        "raw_target_x_values": raw_targets,
        "transformed_target_u_values": u_targets,
        "leaf_x_variables": xs,
        "leaf_phi_variables": us,
        "target_phi_variables": u_target,
        "target_selector_variables": selector,
        "target_preimage_x_count": len(raw_targets),
    }
    return formula, meta
