# Composite-radix tau matching construction

Let `E=Z[tau]`, with coordinates `a+b*tau`,
`tau²-3*tau+3=0`, and norm `N(a,b)=a²+3ab+3b²`. On the
secp256k1 subgroup, `tau` is the degree-three endomorphism used by the
existing native implementation. The six units preserve the norm and act
on coordinate pairs by `omega(a,b)=(a+3b,-a-2b)` and sign.

## Digit coverage

Modulo `R=384`, the six-unit action has exactly 24,578 classes. The
four-corner nearest-digit rule supplies each class with a representative
of norm at most `R²/3`. For a class `s` with direct digit `d_s`, the
candidate directed edge `s -> class(tau*d_s)` is admissible exactly when
`s` differs from its target and `3*N(d_s) <= 253²`. Its source seed
covers `s` directly and its target through one tau map. Since
`N(tau*d_s)=3*N(d_s)`, both digit choices have norm at most `253²`.

The reproducible screen enumerates all 147,456 residues. Its underlying
admissible graph has 24,578 vertices, 12,900 edges, and no cycles. It
computes a maximum matching by the following tree recurrence. For each
vertex `v`, let `free(v)` be the maximum number of matched edges below
`v` when its parent edge is unused, and `used(v)` the same number when
the parent edge occupies `v`. For the children `c` of `v`,

`used(v) = sum_c free(c)`,

`free(v) = used(v) + max(0, max_c(1 + used(c) - free(c)))`.

This recurrence considers all ways to leave `v` unmatched or match it
to exactly one child; induction on subtree height proves optimality.
The screen checks acyclicity, reconstructs the selected edges, checks
that endpoints are disjoint, and obtains a matching of 6,504 edges.
Any two-class seed cover of this graph needs at least `|V|-nu(G)` seeds
by the edge-cover/matching identity, allowing singleton seeds for
isolated vertices. The construction attains that bound with
`24,578-6,504=18,074` seeds per window. It stores the zero seed first.
For each of the 147,456 residues, it checks the encoded seed, exponent,
and unit code reconstruct that exact residue and obey the digit bound.

## Fifteen-window termination

The existing certified scalar representative `z_0` obeys
`N(z_0) <= n/3`, where `n` is the secp256k1 subgroup order. Write
`L_i=sqrt(N(z_i))`. Dividing by `R` after subtracting a digit of norm
at most `D²` gives `L_{i+1} <= (L_i+D)/R`. Thus after `W=15` windows,

`L_W <= (sqrt(n/3) + D*(R^W-1)/(R-1))/R^W`.

For `R=384` and `D=253`, the exact integer check
`n < 3*(R^W-D*(R^W-1)/(R-1))²` holds, so `L_W<1` and the integral
final quotient is zero. The same sufficient inequality fails for
`D=254`. The screen additionally reconstructs 8,192 previously frozen
full-range scalars, checking every division and the final quotient.

For each window `i`, let `P_i` be the stored affine point for seed
`d_i` at base `R^i G`. The encoded unit and tau exponent choose the
point `unit*tau^e(P_i)`. Summing exponent-zero terms into `B0` and
exponent-one terms into `B1` gives the exact result `B0+tau(B1)`,
because the endomorphism commutes with scalar multiplication and the
Eisenstein units. The two bucket sums need at most fourteen mixed
additions in total; with both buckets occupied, one projective merge
and one tau map are also charged.

The 15 by 18,074 affine points occupy 17,351,040 bytes. The native
retained allocation, including the 662,128-byte atlas and table metadata,
is 18,013,472 bytes. Mode 134 retains 24,283,336 bytes, so this format
uses 6,269,864 fewer retained bytes (25.82%). This is a storage result;
the online cost of the extra tau map and projective merge requires a
controlled paired measurement.
