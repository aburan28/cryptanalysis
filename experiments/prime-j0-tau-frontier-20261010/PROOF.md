# Variable-width two-bucket construction

The construction finds exact storage costs for a family of fixed-base
secp256k1 scalar multipliers. It retains one affine point per seed in
each window, and chooses every digit as a six-unit image of either that
seed or its degree-three endomorphism image. All selected layouts retain
the same two-bucket evaluation identity `B0+tau(B1)`.

For a radix `2^w`, the endomorphism `tau(a,b)=(-3b,a+3b)` has determinant
three. It therefore permutes residues modulo `2^w` and commutes with the
six units. On six-unit classes, let `d_c` be the minimum-norm four-corner
digit for class `c`. A stored seed for `c` covers its successor class
through one tau application exactly when `3N(d_c) <= D²`, where `D` is
the row's digit-length limit. The successor permutation consists of
disjoint cycles. A minimum seed set is a minimum cover by eligible
two-class segments and singleton segments. Testing the two possible
origin cuts and applying the backward length-one/length-two recurrence
gives an exact minimum for each cycle. The atlas builder exhaustively
checks each encoded residue and digit norm.

For widths `w_i` and limits `D_i`, set `P=product(2^w_i)` and
`S=sum_i D_i*product_{j<i}(2^w_j)`. The certified Eisenstein scalar
representative has `N(z_0)<=n/3`, where `n` is the secp256k1 order.
The norm triangle inequality after each radix division gives

`sqrt(N(z_W)) <= (sqrt(n/3)+S)/P`.

The exact integer condition `P>S` and `n<3(P-S)²` makes the final
integral quotient zero. `screen.py` chooses the largest final-row `D`
meeting this strict inequality and rejects a final row if its nearest
direct digit exceeds `D²`. For nonfinal rows this screen fixes `D=2^w`.
The full-bound atlases have exactly two singleton classes and pair all
other classes; their seed counts for widths 6–9 are respectively
343, 1,367, 5,463, and 21,847.

For a fixed multiset of nonfinal widths, sort them ascending. If
`A<=B` are adjacent radices at prefix `Q`, swapping `B,A` for `A,B`
changes the weighted digit sum from `Q*B+Q*A*B` to
`Q*A+Q*A*B`, which cannot increase it. The product and all later
prefixes are unchanged. This ordering therefore maximizes the
admissible final-row bound within the screened family. The script
enumerates every multiset of widths 6–9 for 16–19 windows, every final
width 6–9, and all valid final limits by exact binary search.

For each layout, point payload is `64*sum_i seeds(w_i,D_i)` bytes.
Atlas storage is charged once per distinct `(w,D)` as
`8+4*2^(2w)+4*seeds(w,D)` bytes. The saved point and atlas counts are
the complete construction storage terms before native container
metadata. A future compressed atlas encoding or different nonfinal
digit bounds is a separate design search.

`build_atlases.py` produced the five distinct atlases needed by the
best 17–19-window layouts. It exhaustively decoded every residue in
each atlas and replayed both prior 4,096-scalar panels for each layout,
checking every digit congruence and the final zero quotient. The
selected 17-window layout also has an independent affine group replay
in `verify_group17.py` and `group17-check.json`.
