# Grouped-unit gauge accumulation for four-limb U14 multiplication

The candidate changes only the order and unit handling of the fourteen
selected affine points in the existing fixed-base U14 secp256k1 evaluator.
It keeps the 129-bit Eisenstein representative, window widths
`[10,10,10,9,9,9,9,9,9,9,9,9,9,9]`, residue atlas, 1,004,890
nonidentity table slots, four-limb Montgomery coordinates, and final
binary-GCD inversion of mode 126. The reference is mode 126 from commit
`012ff82dda7ec03331dadfe0d3cb5186ed6b8b4d`.

Let `omega` act on a point as `(x,y) -> (beta*x,y)`, where `beta` is the
fixed nontrivial cube root of one modulo
`p = 2^256 - 2^32 - 977`. Each selected table point has a unit code
`(-1)^s omega^e`, with `s in {0,1}` and `e in {0,1,2}`. The reference
applies `beta^e` separately to every selected affine `x` with `e != 0`.

The candidate first freezes all fourteen `(window, orbit, sign, exponent)`
choices in a stack array. It then visits the exponent classes in the fixed
order `1,2,0`. It stores a Jacobian point `B` with physical accumulated
point `A = omega^g B`, where `g` is its current gauge. On changing from
`g` to class `e`, it maps `B <- omega^(g-e) B`, multiplying only its
projective `X` by `beta^(g-e mod 3)`. It adds the raw affine seed or its
negation to `B`; no per-addend cube-root multiplication is required.
Initialization from the identity costs no gauge multiplication. After the
last class, it maps `B <- omega^g B` to gauge zero before the existing
affine finalizer. Empty classes and an identity accumulator skip the
corresponding multiplication.

Because `omega` is a group automorphism,
`omega^e(B + Q) = omega^e B + omega^e Q`. The gauge transition preserves
the physical accumulator, and each class addition contributes exactly its
original signed unit image. The group is abelian, so class reordering
preserves the scalar result. The fixed order and final normalization use
at most two nontrivial `beta` products on a nonidentity accumulator:
at most two transitions if class zero is present, or one transition plus
one final normalization if it is absent. The reference can use one such
product for each selected point with `e != 0`. Both arms use the same
number of nonidentity point selections and mixed additions.

## Frozen validation

1. Commit this protocol before generating a new disjoint 4,096-input
   unsigned 256-bit panel with seed `20261010727`. Record its scalar digest
   and prior-panel source digests. Compare both evaluators on the complete
   prior and new panels for point, representative, selected orbit/unit
   codes, and mixed-add count.
2. Independently replay at least 128 new outputs with binary scalar
   multiplication. Verify all 129 frozen expected fixture points in each
   mode. Check gauge transitions on identity, equal/inverse additions,
   all three exponent classes, and at least 512 deterministic nontrivial
   selected sums. Retain every failure and exit status.
3. Record for each checked scalar the exact count of reference per-addend
   cube-root products and candidate accumulator gauge products. Verify the
   candidate count is at most two and that all other point-operation
   counts and table bytes match. Release tests, source/input hashes, binary
   hash, and raw fixture outputs belong in a machine-readable receipt.
4. Pair full online mode-126 and candidate operations in one binary on the
   same frozen public scalars and resource envelope. Include recoding,
   choice staging, all table loads, gauge changes, mixed additions,
   inversion, formatting, and expected-point verification in each online
   timer. Record preparation separately. A controlled CPU speedup requires
   the repository's strict host isolation and noise receipt.

The candidate is opt-in and intended for public scalar research inputs.
Its choice staging, table lookups, and finalizer are input dependent.
Literature priority for this specific fixed-base schedule needs separate
review before a broader novelty claim.
