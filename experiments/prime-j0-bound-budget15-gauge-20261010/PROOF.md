# Grouped unit gauge inside two tau buckets

The fifteen-window candidate stores selected affine seed points in two
`tau` buckets. Its per-term unit selector ordinarily multiplies the x
coordinate of every seed with unit power one or two by a fixed cube root
of one. This variant groups the selected terms by unit power inside each
bucket and rotates the accumulated XYZZ bucket instead. It composes the
existing [U14 grouped-unit gauge](../prime-j0-u14-gauge-20261010/PROTOCOL.md)
with the [fifteen-window weighted digit budget](../prime-j0-bound-budget15-20261010/PROOF.md).

Let `omega(P)=(beta*x(P),y(P))`, and let a selected point for tau bucket
`e` have unit code `(-1)^s omega^p`, where `p` is 0, 1, or 2. For each
bucket independently, maintain an XYZZ point `B_e` and gauge `g_e` so the
physical accumulated point is `A_e=omega^g_e(B_e)`. On changing from gauge
`g` to unit-power class `p`, set `B_e <- omega^(g-p)(B_e)`. This preserves
`A_e` because `omega^p omega^(g-p)=omega^g`. Adding the raw seed or its
negation to `B_e` then contributes the required `(-1)^s omega^p(seed)` to
`A_e`. After the classes in order `1,2,0`, normalize with
`B_e <- omega^g_e(B_e)` if needed.

The group is abelian, so reordering within a bucket changes no result.
The maps `omega` and `tau` commute, so the final
`B_0 + tau(B_1)` equals the original fifteen-window scalar multiple.
Each bucket has at most two nontrivial gauge transitions or final
normalizations in the fixed class order. Thus two buckets use at most
four cube-root x rotations, compared with one per selected term whose
unit power is nonzero. Rotating a nonidentity XYZZ bucket changes only
its Montgomery x coordinate; the fixed Solinas reduction computes that
rotation in 23 source-loop limb products.

The digit atlases, selected seed points, recoding, mixed-add count, bucket
tau map, merge, and affine finalizer are shared with mode 156. The charged
retained size remains 17,511,596 bytes. A preliminary 4,096-scalar panel
gave 40,981 per-term rotations and 15,323 gauge rotations, with exact
agreement on every point and 128 independent binary point checks. The
new disjoint panel and complete field-operation record are separate gates.
