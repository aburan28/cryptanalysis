"""Exact two-product S4 evaluator: identity, exhaustive check, optimality in
the precomputed-feature model, and the relation-search claim boundary.

Setting.  S4(x1, x2, x3, x4) = Res_z(S3(x1, x2, z), S3(x3, x4, z)) up to the
leading-coefficient factor.  Write the two Semaev quadratics in z as
a2 z^2 + a1 z + a0 and b2 z^2 + b1 z + b0 with

    a2 = (x1 - x2)^2,
    a1 = -2 ((x1 + x2)(x1 x2 + A) + 2 B_curve),
    a0 = (x1 x2 - A)^2 - 4 B_curve (x1 + x2),

on y^2 = x^3 + A x + B_curve, and likewise b_i from (x3, x4).  Normalising
both to monic (one inversion per endpoint, amortised over every pair the
endpoint participates in), f = z^2 + B z + C and g = z^2 + E z + F, the
resultant is

    R = (F - C) (UL + UR) + (E - B) (VR - VL),
        UL = B^2 - C,  VL = B C   (left endpoint),
        UR = F - E^2,  VR = E F   (right endpoint).

Per pair this costs 2 multiplications and 4 additions once the four features
of each endpoint are stored.  The projective resultant is a2^2 b2^2 R, so R = 0
iff S4 = 0 whenever a2 b2 != 0; the a2 = 0 case (x1 = x2) is a separate
partition handled by the doubling formula and never enters the pair loop.

Optimality (checked).  Expanded, R = B^2 F - 2 C F + F^2 + C^2 + C E^2 - B C E
- B E F.  As a quadratic form in the eight stored features
(C, B, UL, VL, F, E, UR, VR) its Gram matrix has rank 4, and a product of two
linear forms has rank at most 2, so no evaluator in the "sum of products of
linear forms in the stored features" model uses fewer than 2 multiplications.
The cross (left x right) coefficient block has rank 4 as well, so a plain dot
product of stored features needs at least 4 multiplications; the (2,2)
flattening of the full polynomial has generic rank C(4,2) = 6, which is the
rank-six fused dot product the benchmark also times.

Claim boundary.  This is an evaluator for S4 = 0 tests on candidate pairs.  It
reduces the constant in the pair-enumeration phase of a four-summand
decomposition oracle when the pair count exceeds the endpoint count; it does
not change the number of pairs that must be enumerated, the yield of
relations, or the linear algebra, and it is not a thin-product instance
(the inner product is rank 6 and every pair is still visited).  No complete
index-calculus speedup or ECDLP speedup is claimed from it; the measured
figure is a stage diagnostic with candidate_id null.
"""

from __future__ import annotations

import json
import os
from itertools import product

import sympy as sp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "s4_two_product.json")


def two_product(B, C, E, F):
    UL, VL, UR, VR = B * B - C, B * C, F - E * E, E * F
    return (F - C) * (UL + UR) + (E - B) * (VR - VL)


def sylvester_resultant_monic(B, C, E, F):
    M = sp.Matrix([[1, B, C, 0], [0, 1, B, C], [1, E, F, 0], [0, 1, E, F]])
    return M.det()


def symbolic_identity() -> dict:
    B, C, E, F, z = sp.symbols("B C E F z")
    res = sp.expand(sp.resultant(z**2 + B * z + C, z**2 + E * z + F, z))
    tp = sp.expand(two_product(B, C, E, F))
    expanded = sp.expand(B**2 * F - 2 * C * F + F**2 + C**2 + C * E**2 - B * C * E - B * E * F)
    # Projective resultant equals a2^2 b2^2 R.
    a0, a1, a2, b0, b1, b2 = sp.symbols("a0 a1 a2 b0 b1 b2")
    proj = sp.expand(sp.resultant(a2 * z**2 + a1 * z + a0, b2 * z**2 + b1 * z + b0, z))
    scaled = sp.expand(a2**2 * b2**2 * two_product(a1 / a2, a0 / a2, b1 / b2, b0 / b2))
    return {
        "two_product_equals_resultant": sp.simplify(res - tp) == 0,
        "expanded_form_matches": sp.simplify(res - expanded) == 0,
        "projective_resultant_equals_a2^2_b2^2_R": sp.simplify(proj - scaled) == 0,
        "resultant_expanded": str(res),
    }


def exhaustive_small_fields() -> list[dict]:
    out = []
    for p in (2, 3, 5, 7, 11):
        mism = 0
        total = 0
        for B, C, E, F in product(range(p), repeat=4):
            total += 1
            lhs = int(sylvester_resultant_monic(B, C, E, F)) % p
            rhs = int(two_product(B, C, E, F)) % p
            if lhs != rhs:
                mism += 1
        out.append({"p": p, "tuples": total, "mismatches": mism})
    return out


def optimality() -> dict:
    B, C, E, F = sp.symbols("B C E F")
    C_, B_, UL, VL, F_, E_, UR, VR = feats = sp.symbols("C_ B_ UL VL F_ E_ UR VR")
    # R written in the stored features only (no products of raw variables).
    R_feat = sp.expand((F_ - C_) * (UL + UR) + (E_ - B_) * (VR - VL))
    gram = sp.hessian(R_feat, feats) / 2
    cross = sp.Matrix(4, 4, lambda i, j: gram[i, j + 4])
    # Full-polynomial (2,2) flattening rank in (B,C)|(E,F) monomials.
    R = sp.Poly(sp.expand(two_product(B, C, E, F)), B, C, E, F)
    rows, cols, ent = {}, {}, {}
    for (eb, ec, ee, ef), coeff in R.terms():
        rows.setdefault((eb, ec), len(rows))
        cols.setdefault((ee, ef), len(cols))
        ent[(rows[(eb, ec)], cols[(ee, ef)])] = int(coeff)
    M = sp.zeros(len(rows), len(cols))
    for (i, j), v in ent.items():
        M[i, j] = v
    return {
        "gram_rank_in_8_features": int(gram.rank()),
        "lower_bound_products_of_linear_forms": -(-int(gram.rank()) // 2),
        "two_product_uses": 2,
        "cross_block_rank_left_x_right_features": int(cross.rank()),
        "dot_product_lower_bound_multiplications": int(cross.rank()),
        "full_polynomial_(B,C)|(E,F)_flattening_rank": int(M.rank()),
        "generic_C(4,2)": 6,
    }


def cost_model() -> dict:
    """Operation counts per pair and per endpoint; crossover condition in multiplications."""
    return {
        "raw_fused_projective": {"per_pair": "7M + 1S", "per_endpoint": "0", "note": "(a2 b0 - a0 b2)^2 - (a2 b1 - a1 b2)(a1 b0 - a0 b1)"},
        "monic_fused": {"per_pair": "3M + 1S", "per_endpoint": "1I + 2M", "note": "(C - F)^2 + (B - E)(B F - C E) after monic normalisation"},
        "rank_six_dot": {"per_pair": "6M", "per_endpoint": "1I + 2M + ~4M (six monomials)", "note": "generic flattening rank C(4,2) = 6"},
        "two_product": {"per_pair": "2M", "per_endpoint": "1I + 3M + 1S", "note": "features (B, C, UL, VL) / (E, F, UR, VR)"},
        "crossover_vs_monic_fused": "2|W| + c(|L|+|R|) < 4|W| iff |W| > (c/2)(|L|+|R|); with c ~ 4M + 1I, roughly |W| > 2(|L|+|R|) counting I ~ 0; endpoint-reuse >= 2 pairs per endpoint on each side",
        "crossover_vs_raw_fused": "two-product wins once each endpoint is reused in more than about one pair (8 vs 2 per pair, endpoint cost ~5 + I)",
    }


def main() -> None:
    res = {
        "identity": symbolic_identity(),
        "exhaustive_small_fields": exhaustive_small_fields(),
        "optimality": optimality(),
        "cost_model_derived": cost_model(),
        "a2_zero_partition": "x1 = x2 gives a2 = 0; those pairs use the doubling branch and never enter the monic pair loop",
        "claim_boundary": "evaluator constant for S4 = 0 tests only; pair count, relation yield, linear algebra and total IC cost unchanged; not a thin-product instance; candidate_id null",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
