# Fifteen radix-256 windows with one direct terminal point

This fixed-generator secp256k1 format combines the existing six-unit
positional orbit atlas with the bounded direct-terminal construction. It
recodes the certified nearest Eisenstein representative through fifteen
radix-256 windows. Each ordinary digit selects one point from the orbit row;
the exact remaining Eisenstein pair selects one point from a terminal disk
row. Unit images use the same order-three automorphism and sign rule as the
existing axis format. All shifted digit points and terminal points are built
before the scalar call. Online evaluation uses at most sixteen selected
points and no endomorphism map.

For `N(a,b)=a²+3ab+3b²`, the initial representative satisfies `3N≤n`.
Each nearest ordinary digit satisfies `3N(d)≤256²`. Writing
`z0=d0+256d1+...+256^14 d14+256^15 t`, the norm triangle bound gives

`3N(t)≤floor((2^128+sum(256^j,j=1..15))²/256^30)=66051`.

Every nonzero terminal point has exactly one image in the sector
`(-u,b)` with `u>0` and `u≤3b<2u`. The integer disk contains 79,879
coordinate pairs: the identity and 13,313 free six-unit orbits. Within
each `u` row, admissible `b` values form a contiguous interval, so two
small row-bound arrays and a prefix offset give a direct table index.
`search.py` enumerates the disk by exact square rows and audits the rank
and all six unit images. The fifteen ordinary rows contain 10,924 point
orbits each; total point entries are `15*10924+13314=177174`.

The power-of-two radix is an intentional CPU candidate: coefficient
quotients and residues can use signed bit shifts and masks. The nearby
integer-radix census includes radix 257 at 176,979 entries, only 195 fewer
points; no CPU ordering is inferred from this point count. The native
comparison must charge the full recoder, atlas lookup, table access,
point arithmetic, affine recovery, and correctness check for the same
public scalar panel.

The design screen reuses the frozen 4,096-scalar panel and the radix-286
control representative. Commit `598f4e57d461b0deabccff30d85285ac8909f4f4`
freezes the native builder, evaluator, holdout generator, and verifier.
`holdout.py` then drew 512 distinct scalars disjoint from the earlier
panels. `replay.py` compares every complete point against the existing
radix-286 evaluator and an independent binary multiplier, retaining source,
table, and output digests. Commit
`d79b5b7b6f585e00f1e145cb74d2de978634b15f` froze a second generator
and three-panel verifier. `holdout2.py` then drew a further 512 scalars
disjoint from the 4,096-scalar design panel and all eight earlier holdouts;
`replay-two-panel.json` preserves the earlier replay receipt. A complete CPU timing ratio requires a
qualifying isolation receipt; the current record has exact operation and
storage counts and correctness replay.
