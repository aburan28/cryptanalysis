#!/usr/bin/env python3
"""Generate matched F4 inputs with a genuine three-component grading.

This is a deliberately small, auditable homogeneity experiment. The M2 inputs
have identical generators and monomial order; one ring records tri-grading,
the other records only ordinary total degree. Both saturate by h_0*h_1*h_2
before the F4 call. The polynomial lift specializes exactly to the Boolean
fraction equations on the affine chart h_0=h_1=h_2=1.
"""

import argparse
import json
from pathlib import Path

from block_fraction_solver import MODULI, equations, independent_oracle
from math_model import GF2n


def homog_term(mask, width, block_degree=4):
    """Canonical M2 term of multidegree (block_degree,)*3."""
    factors = []
    for block in range(3):
        count = 0
        for bit in range(width):
            index = block * width + bit
            if mask & (1 << index):
                factors.append(f"x_{index}")
                count += 1
        if count > block_degree:
            raise ValueError("input monomial exceeds the formal grading")
        remaining = block_degree - count
        if remaining:
            factors.append(f"h_{block}" + (f"^{remaining}" if remaining > 1 else ""))
    return "*".join(factors) or "1"


def input_polynomials(n, k, target):
    field = GF2n(n, MODULI[n])
    width = 2 * (k + 1)
    # Reuse the audited Boolean quotient polynomial. Its formal lift is
    # multihomogeneous and becomes the *same* polynomial after h_i=1.
    eqs = equations(field, k, target)
    descended = eqs[:n]
    coords = ["+".join(homog_term(m, width) for m in sorted(poly)) or "0"
              for poly in descended]
    field_equations = [f"x_{j}^2+x_{j}*h_{j // width}"
                       for j in range(3 * width)]
    # Equality to zero enforces at least one denominator coefficient = 1
    # after h=1; it excludes the invalid zero-denominator component.
    denominator_equations = ["*".join(
        f"(h_{block}+x_{block * width + k + 1 + j})"
        for j in range(k + 1)) for block in range(3)]
    return coords + field_equations + denominator_equations


def boolean_lift_check(n, k, target):
    """Exhaustively verify dehomogenization for the deliberately tiny panel."""
    field = GF2n(n, MODULI[n])
    width = 2 * (k + 1)
    original = equations(field, k, target)
    # The lift does not alter a Boolean monomial when all h_i = 1.
    # Check its grading explicitly and every Boolean assignment against
    # independent numerical cleared S4 and denominator evaluation.
    for poly in original[:n]:
        for mon in poly:
            degrees = tuple(((mon >> (b * width)) & ((1 << width) - 1)).bit_count()
                            for b in range(3))
            assert all(degree <= 4 for degree in degrees)
            lifted = tuple(degree + 4 - degree for degree in degrees)
            assert lifted == (4, 4, 4)
    for bits in range(1 << (3 * width)):
        pairs = []
        for block in range(3):
            word = (bits >> (block * width)) & ((1 << width) - 1)
            num = den = 0
            for j in range(k + 1):
                if word & (1 << j):
                    num ^= field.power(2, j)
                if word & (1 << (k + 1 + j)):
                    den ^= field.power(2, j)
            pairs.append((num, den))
        original_value = sum(
            (1 << j) if sum((mask & bits) == mask for mask in poly) & 1 else 0
            for j, poly in enumerate(original[:n]))
        assert original_value == field.s4_cleared(pairs, target)
        for block in range(3):
            denom_zero = pairs[block][1] == 0
            p = original[n + block]
            assert bool(sum((mask & bits) == mask for mask in p) & 1) == denom_zero
    return independent_oracle(field, k, target)


def emit(n, k, target, arm):
    width = 2 * (k + 1)
    nv = 3 * width
    vars_ = [f"x_{j}" for j in range(nv)] + [f"h_{j}" for j in range(3)]
    degrees = [[int(j // width == block) for block in range(3)]
               for j in range(nv)] + [[int(i == block) for block in range(3)]
                                      for i in range(3)]
    grade_options = ("Degrees=>" + json.dumps(degrees).replace("[", "{").replace("]", "}")
                     + ",Heft=>{1,1,1},") if arm == "multi" else ""
    ring = f"R=ZZ/2[{','.join(vars_)},{grade_options}MonomialOrder=>GRevLex];"
    generators = input_polynomials(n, k, target)
    return "\n".join([
        f"-- n={n}, k={k}, target={target}, arm={arm}; generated from the same input list",
        "stopIfError=true;",
        ring,
        f"I=ideal({','.join('(' + p + ')' for p in generators)});",
        '<< "INPUTCOUNT|" << numgens I << endl;',
        "ts=cpuTime();",
        "J=saturate(I,ideal(h_0*h_1*h_2));",
        '<< "SATCPU|" << (cpuTime()-ts) << endl;',
        '<< "SATGENS|" << numgens J << endl;',
        "gbTrace=1;",
        "tg=cpuTime();",
        'G=groebnerBasis(J,Strategy=>"F4",MGBOptions=>{"Threads"=>1,"Log"=>"F4MatrixSizes,SPairDegree"});',
        '<< "GBCPU|" << (cpuTime()-tg) << endl;',
        '<< "GBCOUNT|" << numgens source G << endl;',
        'scan(flatten entries G,p->(<< "GBPOLY|" << toString p << endl));',
        'exit 0;',
        "",
    ])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, choices=MODULI, default=5)
    ap.add_argument("--k", type=int, choices=(0, 1), default=0)
    ap.add_argument("--target", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("strict_runs"))
    args = ap.parse_args()
    if args.k == 1 and args.n > 7:
        ap.error("only bounded n=5/7, k=1 fixtures are supported")
    oracle = boolean_lift_check(args.n, args.k, args.target)
    args.out.mkdir(parents=True, exist_ok=True)
    for arm in ("multi", "total"):
        script = args.out / f"n{args.n}_k{args.k}_t{args.target}_{arm}.m2"
        script.write_text(emit(args.n, args.k, args.target, arm))
        print(json.dumps({"path": str(script), "arm": arm,
                          "expected_verified_relation": oracle,
                          "generators": len(input_polynomials(args.n, args.k, args.target))}))


if __name__ == "__main__":
    main()
