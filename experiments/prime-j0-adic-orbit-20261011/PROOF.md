# Direct 2-adic index of Eisenstein unit orbits

Let `R=2^n`, here `n=10`, and let the six units act on pairs modulo
`R` by `omega(a,b)=(a+3b,-a-2b)` and negation. The map has order three.
Its reduction modulo two cycles the three nonzero parity pairs:
`(1,0) -> (1,1) -> (0,1) -> (1,0)`. Negation fixes parity.

For a nonzero residue pair, set `t=min(v2(a),v2(b))`, `m=n-t`, and
divide both coordinates by `2^t` modulo `2^m`. Exactly one power
`omega^k`, `k in {0,1,2}`, changes the resulting parity to `(1,0)`.
For `m>=2`, exactly one sign makes its odd first coordinate lie in
`[1,2^(m-1))`. The result `(A,B)` has odd `A` and even `B` and is
unique in the six-unit orbit. For `m=1`, sign acts trivially, and the
unique representative is `(1,0)`. The zero pair forms its own orbit.

At level `m>=2`, there are `2^(m-2)` possible first coordinates and
`2^(m-1)` possible second coordinates. Hence there are
`2^(2m-3)` orbits. Level one contributes one orbit, and zero contributes
one. For `n=10`, the total is

`2 + sum_(m=2)^10 2^(2m-3) = (2^20+8)/6 = 174,764`.

More generally, for every `n>=1` the same construction has exactly
`(2^(2n)+8)/6` unit orbits. The two exceptional classes are zero and
the nonzero orbit modulo two; all other classes have six residues.

With `offset[1]=1` and `offset[m]=2+sum_(j=2)^(m-1) 2^(2j-3)` for
`m>=2`, the direct dense index is

`offset[m] + ((A-1)/2)*2^(m-1) + B/2`.

The zero index is zero. This formula contains no minimum over six
images, bitset test, prefix rank, or population count. Since the
canonicalizing unit is also known, a code storing a seed, tau exponent,
and unit for the canonical residue decodes any member by composing
with the inverse canonicalizing unit. This is the same six-unit
composition law as the existing quotient atlas. It preserves the exact
digit congruence, norm bound, and scalar reconstruction.

The lookup performs one 2-adic valuation, at most one linear unit
transform, one sign normalization, and one direct code access per
full digit. In particular, it has no rank-table memory access. These
are structural operation counts, not a wall-time comparison.

The independent verifier must enumerate all `2^20` residue pairs,
check the index and unit action against a separate implementation,
and show that every index has exactly one orbit. Atlas decoding and
point multiplication are separate gates after this combinatorial proof.
