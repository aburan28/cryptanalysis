# Exact coefficient factoring selects the affine shear instead

The archived factorization of the 13 `P,Q` coefficients of `A` and eight of
`B` reconstructs their original 60 and 16 GF(2) monomials exactly. A shared
factored-coefficient compiler, searched over all **12** coefficient/product
Horner orders, emits at least **57 field multiplications and 48,770 AND
gates** per N41 quartic block. The prior shared-Horner compiler emits 54
and 43,584 on the same dense input wires. This direct coefficient factoring
therefore did not enter another public-target solver run; its repeated
`S+Z` factors motivated the exact affine substitution tested in the
[successor experiment](../n41_single_branch_shear_20261011/RESULT.md).

The [coefficient verifier](verify_coefficients.py) multiplies every archived
factor and multiplicity over a sparse GF(2) polynomial ring, lifts it by
its `P,Q` exponents, and compares the complete `A,B` supports to the
[single-branch norm](../n41_quartic_joint_public_20261010/norm_result.json).
The [reconstruction receipt](coefficient_audit.json) passes for all 76
monomials. The [order search](factor_order_result.json) constructs the
actual Karatsuba Boolean circuit for all six orders of `(a,S,Z)` and both
orders of `(P,Q)`; its best order is `(Z,a,S)` then `(P,Q)`. The
[field replay](audit_result.json) evaluates that emitted circuit on zero,
unit, and fourteen seeded uniform five-tuples against direct monomial
arithmetic, with exact outputs in every case.

This is a point-decomposition arithmetic diagnostic on
`GF(2)[t]/(t^41+t³+1)`. It does not alter a public relation row or the
primary one-target timing record; `candidate_id` is `null`. Reproduce with
`python3.12 -B verify_coefficients.py`, `python3.12 -B search_orders.py`,
and `python3.12 -B audit_horner.py` from this directory.
