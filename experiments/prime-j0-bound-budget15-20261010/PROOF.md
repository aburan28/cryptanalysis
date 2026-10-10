# Fifteen-window recoding with a weighted digit budget

The candidate uses six radix-256 windows followed by nine radix-512 windows.
The first eight radix-512 windows may choose Eisenstein digits of norm at
most `512²`; the final window uses the existing `363²` bound. All radix-256
windows use `256²`. This allocation admits a complete two-bucket `tau`
cover with 21,847 seeds for each early radix-512 window, down from 25,869
under the tighter bound.

The six-unit residue quotient, `tau(a,b)=(-3b,a+3b)`, nearest digit rule,
and optimal cycle cover are proved in
[`prime-j0-tau-power16-20261010/PROOF.md`](../prime-j0-tau-power16-20261010/PROOF.md).
The new `atlas-w9.bin` enumerates all 262,144 residues. Its 43,692 unit
classes are all eligible for a two-class `tau` segment under `D=512`; the
cycle cover has 21,845 pairs and two singletons. The generator checks every
code's residue and norm. The largest decoded norm is 261,633, below 262,144.

For window `i`, let `R_i=2^w_i` and let `D_i` be its digit length bound.
Set `P=product_i R_i` and `S=sum_i D_i product_{j<i}R_j`. The certified
nearest-lattice representative obeys `3N(x_0) <= n`. Iterating
`x_{i+1}=(x_i-d_i)/R_i` and the norm triangle inequality gives

`sqrt(N(x_15)) <= (sqrt(n/3)+S)/P`.

For the stated schedule, `P=2^129` and
`S=483841591694663947043977754461887070464`. Exact integer arithmetic
gives

`3(P-S)^2-n = 307894731501496315773559478054171831478525439653543264814648304175009283775 > 0`.

Consequently `N(x_15)<1`, and the final Eisenstein pair is zero for every
secp256k1 scalar. `build_atlas.py` recomputes this integer margin and writes
the full atlas receipt.

The 15 fixed-base tables store `6*5463 + 8*21847 + 25869 = 233423`
affine seed points. Their 64-byte payload is 14,939,072 bytes. The three
atlases occupy 2,572,036 bytes. Native table/container overhead and the
96-byte Solinas unit constant array bring the charged retained size to
17,511,596 bytes. The sixteen-window compact candidate retains 8,336,624
bytes. Both use the same Solinas cube-root rotation and XYZZ bucket merge;
the variable under study is the window schedule and digit budget.

For each nonzero digit, the selected seed point is added to bucket zero or
one. The latter bucket receives one `tau` at the end and is merged into the
first. The 15-window schedule permits at most 14 nonidentity mixed additions
after the initial point insertion; the 16-window schedule permits 15. The
source-level group-operation counts are checked on paired scalar fixtures.
