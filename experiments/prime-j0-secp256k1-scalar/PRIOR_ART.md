# Prior-art boundary for the carried-gauge scalar prototype

The current candidate evaluates a short `a+bτ` representation on
`y²=x³+b` over a prime field, where `τ=1-ω` and `ω` is the order-three
endomorphism. The following pieces are already in the literature:

| Component | Published source | Consequence here |
| --- | --- | --- |
| `τ=1-ω`, short two-dimensional scalar reduction, Jacobian `τ` and tripling formulas | Xu, Yu, Han, Lu, [*On Efficient Computations of y²=x³+b/Fp for Primes p≡1 (mod 3)*](https://eprint.iacr.org/2024/1906), Sections 3–4 | These are baseline mathematics, not proposed new results. |
| Unit-invariant digit preparation and a loop that uses `3R` to process two `τ` positions | Xu et al., Section 4.3.1, Algorithm 3 | Fusing two `τ` positions via tripling is also prior art. |
| Symmetric endomorphism-based digit sets and τ-adic recoding on `j=0` prime-field curves | Heuberger and Mazzoli, [*Symmetric Digit Sets for Elliptic Curve Scalar Multiplication without Precomputation*](https://eprint.iacr.org/2013/705) | Unit digits and complex-base recoding are not new in themselves. Their radix is a Frobenius eigenvalue, rather than the particular `1-ω` used here. |

The **specific candidate for further examination** is to carry a
three-state unit orientation through Jacobian projective coordinates,
choose the next orientation at each stride, and exploit the resulting
Z-coordinate scale. In the present paired formula, one orientation
change makes that scale a negation, while other changes multiply by a
nontrivial constant. Digit representatives are rotated into the
current orientation. The local policy in `validate_scalar.py` chooses
among these transitions; its complete 256-bit output is checked against
Sage. Algebraically, `τ²=-3ω`, so choosing an orientation change of two
gives `ω²τ²=-3`. The resulting cheap paired stride is therefore a
signed tripling, matching the mechanism underlying Xu et al.'s
Algorithm 3. Its equation (14) absorbs powers of `-ω` into
unit-invariant digits to use tripling. The projective-state notation
may only be another implementation of that existing method. We have
not established a distinct algorithmic contribution, so **academic
novelty is unknown and currently looks unlikely**.

The 128-case stage diagnostic in `STAGE_RESULT.md` compares this
candidate with the same unit-digit evaluator using free gauge and
without fused strides. It does **not** compare against Xu et al.'s
window-four method, an optimized GLV implementation, or a full native
scalar path. Its `4M` per single `τ` is the explicit formula used by
our control, not a claim that all `τ` implementations require `4M`.
The source paper gives an alternative `3M+3S` Jacobian `τ` formula;
the relative cost depends on the field kernel. Thus the 4.446% nominal
`M` saving is a result **within that frozen formula boundary only**.
No CPU speedup or broader scalar-multiplication advantage follows.

Next gates are an independent prior-art review of the precise gauge
transition, a native implementation with complete field-operation and
setup costs, comparison with credible full scalar baselines, and
host-isolated timing before any wall-time claim.
