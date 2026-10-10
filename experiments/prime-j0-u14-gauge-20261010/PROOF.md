# Correctness and unit-product bound for grouped U14 accumulation

Let `E/Fp` be secp256k1, `p = 2^256 - 2^32 - 977`, and let `beta` be the
nontrivial cube root of one checked by `check_algebra.py`. Its order-three
automorphism is `phi(x,y) = (beta*x,y)`. The fourteen frozen U14 digit
choices select affine seed points `Q_i`, signs `s_i in {0,1}`, and exponents
`e_i in {0,1,2}`. The reference sums

`A = sum_i (-1)^s_i phi^e_i(Q_i)`.

The candidate keeps one projective accumulator `B` and a gauge `g` such
that the physical accumulated point is `A_partial = phi^g(B)`. It visits
the nonempty exponent classes in the fixed order `1,2,0`. For the first
class `e`, it sets `g=e` and adds each signed raw seed to `B`, starting at
the identity. Suppose the invariant holds before another class `e`. Map

`B <- phi^(g-e)(B)`, then set `g=e`.

The physical point is unchanged because
`phi^e(phi^(g-e)(B)) = phi^g(B)`. Adding signed seeds for this class gives

`phi^e(B + sum_i (-1)^s_i Q_i)
 = A_partial + sum_i (-1)^s_i phi^e(Q_i)`.

This establishes the invariant by induction. The group law is
commutative, so visiting the classes in a new order preserves the total
sum. Finally mapping `B <- phi^g(B)` yields `A` in gauge zero for the
unchanged binary-GCD affine finalizer. Identity, cancellation, and doubling
are handled by the existing complete mixed-add branches.

For Jacobian `(X:Y:Z)`, the affine point is `(X/Z²,Y/Z³)` and
`phi^d(X:Y:Z) = (beta^d X:Y:Z)`. Thus a nonzero gauge transition needs
one four-limb Montgomery product on `X`; `Y` and `Z` are unchanged. The
constants are already stored in Montgomery form, and the old point backend
uses the same field multiplication. Multiplying by the nontrivial beta
constant is skipped when the accumulator is the identity.

Let `m` be the number of nonempty exponent classes. If class zero is
present, the fixed order ends at zero and has at most `m-1 <= 2`
transitions. If zero is absent, at most two classes are present, so there
is at most one transition and one final normalization. The candidate
therefore performs at most two nontrivial beta products per scalar. The
reference performs one for every selected digit with exponent one or two.
Both use the identical table and one `add_mixed` call per nonidentity
selected digit; their reported addition count is the same
`nonidentity.saturating_sub(1)` convention.

The same construction applies to any abelian group with a cheap
automorphism `phi` of finite order `d`. Partition selected summands
`phi^e(Q)` by exponent, visit nonzero classes first and class zero last,
and keep the invariant `A_partial = phi^g(B)`. There are at most `d`
nonempty classes. If zero is present, at most `d-1` gauge transitions are
needed and final normalization is free. If zero is absent, at most `d-1`
classes are visited: at most `d-2` transitions plus one final
normalization. Thus at most `d-1` automorphism evaluations replace an
arbitrary number of per-summand evaluations, while the group-addition
count stays fixed. The concrete implementation uses `d=3` and evaluates
each transition as one Montgomery multiplication of Jacobian `X`.
