# Minimum three-image cover and scalar reconstruction

The certified scalar representative `z0` satisfies `3N(z0) <= n`. For
each of twelve radix-1024 windows, the selected digit `d_i` is congruent
to `z_i` coordinatewise modulo 1024 and satisfies `N(d_i) <= 1024^2`.
Consequently `z_(i+1)=(z_i-d_i)/1024` is integral. The exact bound
`3(149*1024^12 - sum_(i=0)^11 1024^(i+1))^2 > n` proves that the
terminal pair lies in `N(z12)<149^2`. This is the same termination
invariant as the two-image radix-1024 format; the new atlas changes only
which bounded representative is selected for each residue.

The six-unit orbit quotient of the full residue space has 174,764
classes. Tau is invertible modulo 1024 because its determinant is three,
so its action is a permutation. Consider one cycle. A seed in class `v`
can cover at most three consecutive classes: `v`, `tau(v)`, and
`tau^2(v)`. The first two images are admissible when
`3N(d_v)<=1024^2`; the third is admissible when
`9N(d_v)<=1024^2`. The minimum-norm representative `d_v` makes these
tests necessary and sufficient for this seed policy.

Every cover can be trimmed to a partition of the cycle into consecutive
segments of length at most three without increasing the number of seeds.
The segment covering a fixed origin starts at the origin or one of its
two predecessors. For each of those three starts, a linear dynamic
program tries every admissible segment length and minimizes segment
count. The least of those three results is therefore the exact minimum
for the cyclic cover. Reconstruction of the dynamic-program path gives
one seed and exponent assignment for each class.

In the exact terminal disk, tau multiplies the norm by three. It sends
each nonzero unit class to at most one successor inside the disk and
cannot form a nonzero cycle. Its finite components are chains. A seed
can cover at most three consecutive chain classes, giving the lower
bound `ceil(L/3)` for a chain of length `L`. Starting at the root and
grouping successive triples attains that bound. The identity requires
one explicit zero seed.

Let `G_i=[1024^i]G`. Store one affine point
`[u+v*lambda_tau]G_i` per selected seed pair `(u,v)` in row `i`.
The code's unit and tau exponent recover the selected digit point.
With three buckets, `B0 + tau(B1 + tau(B2))` equals the sum of all
thirteen decoded terms, hence the original scalar multiple. This
group identity will be checked independently on the frozen scalar panel.
