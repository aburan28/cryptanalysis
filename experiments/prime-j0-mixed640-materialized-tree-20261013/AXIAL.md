# Axial factorization of the mixed-radix scalar table

The mixed-radix digit atlas can be evaluated from one-dimensional point
tables. For each window base `B_i` and atlas digit `(a_i,b_i)`, the evaluator
looks up `[|a_i|]B_i` and `[|b_i|]B_i`, negates the ordinate when a coordinate
is negative, and accumulates the two coordinates in separate XYZZ buckets.
It applies the order-three endomorphism once to the second bucket:

`sum_i ([a_i]B_i + [b_i]tau(B_i)) = (sum_i [a_i]B_i) + tau(sum_i [b_i]B_i)`.

`AxialFactorization.lean` proves this fold identity for an associative,
commutative point operation, an additive `tau`, and integer scalar action
commuting with `tau`. The proof map is `tau_fold` for moving `tau` through a
fold, `axial_fold` for splitting digit pairs, and `axial_scalar_fold` for the
integer-coordinate identity. The pinned Lean 4.34.1 build and `#print axioms`
output are in `axial-lean-receipt.json`: the first two declarations depend
on `propext`; the scalar declaration depends on `propext` and `Quot.sound`.
The native bridge consists of the pinned atlas decoding and signed affine
lookup, checked on the 128 frozen scalar fixtures against an independent
binary multiplier.

The exhaustive atlas scan in `axial_model.py` checks 262,144 radix-512
residues and 409,600 residues each for the full and final radix-640 atlases.
The maximum absolute coordinates are 1023, 1278, and 780 respectively.
Fourteen window rows therefore require 15,878 affine entries including
their zero slots, or 1,016,192 point bytes. With the unchanged 4,729,980
atlas bytes, the point and atlas payload is 5,746,172 bytes. The native
table reports 5,746,628 retained bytes including its fixed metadata. In the
128-scalar fixture, 126 scalars have 28 nonzero axis components and two
have 27; each coordinate bucket receives 1,791 terms in total.

`native_axial_bench.py` generates the source-pinned native front door. The
local release test `axial_holdout_matches_independent_binary` passed all
128 fixture scalars and reported `retained_bytes=5746628`. The evaluator
trades a much smaller point table for about fourteen additional mixed
additions per scalar. Its online timing must include both bucket walks,
the final `tau`, addition, inversion, and affine recovery. The RunPod
comparison uses the serial benchmark service and preserves its preflight,
source hashes, raw invocations, and pair rows; its instance-scoped receipt
will determine whether the smaller table pays for those additions.
