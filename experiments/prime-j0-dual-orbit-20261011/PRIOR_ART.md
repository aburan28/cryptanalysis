# Contribution and related constructions

This experiment uses a split norm-seven endomorphism as an **offline
residue-cover tag** for a fixed-base radix-1024 table. A deterministic
priority assignment then chooses a tau-only representation whenever the
same stored seed set permits one. The new assignment changes only the
atlas: native code, seed count, affine table size, and scalar workload are
held fixed in the paired operation comparison.

The underlying Eisenstein endomorphisms and their point formulas are
prior work. [Xu, Yu, Han, and Lu, ePrint 2024/1906](https://eprint.iacr.org/2024/1906)
develop `tau=1-omega`, six-unit symmetry, and a dedicated formula for
`rho=2-omega=1+tau` on `y^2=x^3+b` over prime fields with `p ≡ 1 (mod 3)`.
The supplied revision of that manuscript gives the Jacobian `rho` formula
in Proposition 3.2 and counts `6S+7M`. Its pasted text has SHA-256
`8d20aca6b52c9b6d541e858bc97fe050528f4169c7283c8e2988042b2813d28e`.

[Heuberger and Mazzoli, ePrint 2013/705](https://eprint.iacr.org/2013/705)
study symmetric Eisenstein digit sets and efficient unit-group actions
for scalar multiplication on curves including the `p ≡ 1 (mod 3)` family.
[Smith, ePrint 2013/672](https://eprint.iacr.org/2013/672) gives lattice
bases for GLV-style scalar decomposition using endomorphisms. These
results ground the endomorphism and recoding components here.

The specific finite cover with a norm-seven tag, fixed 67,338-seed set,
classwise cost priority, and bucket-aggregated evaluation is the design
under test. Its mathematical identity, exact coverage, retained bytes,
point outputs, and operation counts are recorded separately. A literature
review of fixed-base orbit-cover optimizers is still needed before
asserting an academic first-use claim. The next implementation question
is whether Proposition 3.2's direct `rho` formula in XYZZ coordinates
improves on folding its bucket into the two tau buckets.
