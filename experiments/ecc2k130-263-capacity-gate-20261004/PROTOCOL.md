# ECC2K-130 degree-263 capacity and orbit-accounting gate

This is a preregistered **exact counting analysis**, not an IC run or a
performance comparison. It tests which factor-base sizes are even capable
of covering a declared fraction of uniformly sampled nonidentity targets
with one unordered `m`-summand group decomposition. It also separates the
source curve's available sign/Frobenius quotient from the sign-only policy
on the first degree-263 descendant. The result will decide which arities
deserve a natural-query PDP and rank experiment; it cannot decide whether
their solvers are fast enough.

The exact route is `IW1E263d1hadee4e69fa3d`, from
`EC1N131Ckb1h136f03e58c98` to `EC1N131Cbinh833014327b07`. Pin the
merged route manifest at SHA-256
`4b8ce3b607f9fd34c64a157cc904a00b8350e48570d1eaac7b4ca0646f296075`
and the paired polynomial-W screen summary at SHA-256
`0c7f5bae97672b775715a5f479de212efafcc7b657c428c945ad0a1131180c83`.
The source commit is `f602ce7426917adae7c053a5359657fa4a355872`.
Read the subgroup order from the route, assert both nodes agree, and do
not substitute a different field representation or subgroup. All exact
inputs and integer thresholds are in [CONFIG.json](CONFIG.json).

For an **actual** base of `B` distinct, nonidentity, subgroup-usable points,
allow repeated summands. The number of unordered `m`-multisets is
`C(B+m-1,m)`. Thus the fraction of uniform nonidentity target points with
an `m`-sum witness is no more than

`U(B,m) = min(1, C(B+m-1,m)/(r-1))`.

For each `m=3,...,8` and each target support threshold `1/100` and `1/2`,
find the **smallest integer** `B` with `C(B+m-1,m)/(r-1)` at least that
threshold. Check the boundary at both `B` and `B-1` with exact integers.
This is a necessary size, not a predicted hit rate: many multisets can
collide or map to the identity. A guided or nonuniform target-query law
needs its own bound and is outside this gate.

For each threshold size, report two alternative **policy** floors on the
number of unknown base logs, assuming no logs are initially known:

* Sign only: at least `ceil(B/2)` columns.
* A base closed under sign and the source's order-131 Frobenius action:
  at least `ceil(B/262)` columns. This policy is also available to a
  transported source base when orbit labels are carried through the map.

The second line is **not** an automatic property of an arbitrary
polynomial-W or descendant-native base. The degree-263 target has
endomorphism-order conductor 263, so the source's degree-2 Frobenius is
not an integral endomorphism of that curve. An induced scalar action on
the prime subgroup can still be computed or an orbit-closed descendant
base can be built, but its construction, membership test and costs remain
unmeasured. Do not use the sign-only column floor as a theorem that every
descendant implementation must have that many columns. Report the minimum
bytes for a raw vector of `ceil(log2(r)/8)`-byte residues at either column
floor, without treating it as a complete matrix-memory estimate.

For the polynomial-W policies in the merged screen, compute the exact
upper bound `B_max=2(2^d-1)` and `U(B_max,m)` for `(d,m)=(24,5),
(28,4),(35,3),(28,5),(35,4)`. The first three reproduce the existing
hard bounds; the latter two test the next higher arity. An upper bound
below 1% rules out 1% one-shot **uniform** support at that arity for
both source and native bases. An upper bound above 1% proves nothing
about the actual base size, collisions, solver cost or natural yield.

The verified isogeny is a group homomorphism and an isomorphism on the
prime-order subgroup. Therefore `source` and `transported` have exactly
paired group-sum hit vectors after mapping each target, and
`descendant_native` and `pullback` have exactly paired hit vectors after
inverse transport. The next empirical four-policy test should verify
these identities, then spend its coverage budget on the two independent
geometries and its timing budget on all four implementations. This gate
does not construct any of those bases or assign an `IC1` candidate ID.

The result must include the exact inputs, a machine-readable table,
boundary assertions, and a decision. Keep all IC online/cold times,
natural PDP yields, rank, solved logarithms and rho ratios `null`. The
only admissible decision here is whether each arity fails a hard capacity
threshold, remains open pending actual `B`/PDP/rank measurement, or
requires an explicitly orbit-closed policy for the optimistic column
floor. Do not claim a crossover from this analysis.
