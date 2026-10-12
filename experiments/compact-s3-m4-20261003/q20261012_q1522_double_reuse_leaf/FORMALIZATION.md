# Q1522 projection-circuit proof map

The inverse-reuse and direct-output circuits implement the same cofactor-four
x coordinate as the archived Q1513 circuit when the raw x has a rational
curve lift and both doublings are nonidentity. Let `u = x⁻¹` and
`d = x² + u²`. For `E: y² + xy = x³ + 1` over a field of characteristic
two, the doubling formula gives `d = x([2]P)`. If `d ≠ 0`, doubling again
gives `z = x([4]P) = d² + d⁻²`, equivalently `z d² = d⁴ + 1`.

The original circuit uses `z (x¹² + x⁴) = x¹⁶ + x⁸ + 1`. The equality
`x²d = x⁴ + 1` yields `x⁸d² = x¹² + x⁴` and
`x⁸d⁴ = x¹⁶ + 1`. Therefore

`z (x¹² + x⁴) = (d² + d⁻²) x⁸d² = x⁸d⁴ + x⁸ = x¹⁶ + x⁸ + 1`.

Conversely, if `d ≠ 0`, the denominator `x¹² + x⁴ = x⁸d²` is nonzero,
so the original equation determines that same `z`. The `x u = 1` product
and the trace rational-lift condition are retained in both new circuits;
the inverse-two-product variant adds `d v = 1` and `z = d² + v²`, while the
direct-two-product variant uses `z d² = d⁴ + 1`. A subgroup projection
discards identity, so both required nonzero conditions match the base policy.

**Lean status: partial.** The faithful target theorem is the equivalence of
these polynomial constraints over a characteristic-two field, with explicit
`x ≠ 0` and `d ≠ 0` hypotheses; a separate structural lemma must connect
them to doubling on the named Weierstrass curve and the subgroup filter.
The repository's pinned Lean stack is `leanprover/lean4:v4.35.0-rc4` with
Mathlib revision `021c46bdd042f67b538b9f9871d556a93713a9a9`.
The formalization attempt used
`lake env lean ScanWork.lean` from Q1506's pinned project and failed before
elaboration while fetching Mathlib: `Could not resolve host: github.com`.
Direct `lean RationalLift.lean` in Q1495's pinned project reported
`unknown module prefix 'Mathlib'`. No Q1522 Lean theorem is reported as
checked. The missing dependency is the pinned Mathlib checkout and its
compiled `.olean` files; after it is available, the polynomial bridge and
curve-doubling lemma require a build and `#print axioms` audit.

The [validator](validate.py) independently checked the doubling and both
projection equations on rational weight-one through weight-three raw x
samples at degree 83. Those finite checks are implementation controls,
not substitutes for the open Lean theorem.
