# Exact mixed-width two-bucket tau atlas

The construction replaces each direct window digit by a six-unit image of a
stored seed or of its degree-three endomorphism image. The resulting fixed-base
table has **107,814 affine points** across fifteen radix-256 windows and one
radix-512 window, compared with 207,552 points in the direct sixteen-window
table. Every residue has an explicit atlas code, and the digit recurrence
terminates for every secp256k1 scalar.

## Algebra and residue classes

Use Eisenstein pairs with norm `N(a,b)=a²+3ab+3b²`. The six units preserve
this norm. The endomorphism `tau(a,b)=(-3b,a+3b)` multiplies it by three.
For radix `R=2^w`, its matrix has determinant three, hence is invertible
modulo `R`. It commutes with the units, so it permutes the finite set of
six-unit residue classes. The nearest direct digit of a class is selected
by the four-corner minimization in `screen.py`; its class is unchanged.

For each class `c`, the successor is the class of `tau(d_c)`, where `d_c`
is that nearest digit. A stored seed for `c` covers its successor as well
when `3N(d_c) <= D_w²`. A singleton covers only `c`. Since successors form
disjoint directed cycles, the minimum seed set is the sum of minimum
length-one/length-two segment covers of the cycles. Any segment crossing
the chosen cycle origin must start at its predecessor; testing cuts at the
origin and predecessor therefore enumerates both boundary cases. The
backward dynamic program considers every legal one- or two-class segment,
so its recurrence `F(i)=1+min(F(i+1),F(i+2))`, with the two-class option
present exactly when eligible, is optimal by induction. Ties choose the
two-class segment; cycle and cut order fix deterministic seed IDs.

The exhaustive construction found 10,924 unit classes at width eight and
43,692 at width nine. The optimal cycle covers use respectively 5,463 and
25,869 seeds. Each width-eight seed is stored once per one of fifteen
windows. Thus `15*5463+25869=107814` points, with a 64-byte affine payload
of 6,900,096 bytes. The two immutable atlases occupy 1,436,064 bytes.
These are construction counts; native container and alignment overhead are
measured separately.

## Complete residue and scalar coverage

Each atlas code contains a seed index, an exponent in `{0,1}`, and a unit
code in `{0,...,5}`. Decode the seed, apply `tau` when the exponent is one,
then apply the unit. `screen.py` checks all `2^16` or `2^18` ordered residue
pairs, respectively, for exact congruence, digit norm, and one valid code.
The maximum decoded norms are 65,028 at width eight and 131,727 at width
nine, below `D8²=65,536` and `D9²=131,769`.

Let `R_i` be the successive radices, `P=product(R_i)`, and
`S=sum_i D_i*product_{j<i}R_j`. The certified nearest-lattice scalar
representative `x_0` satisfies `3N(x_0) <= n`, where `n` is the secp256k1
group order. Each recurrence `x_{i+1}=(x_i-d_i)/R_i` obeys the norm triangle
inequality, giving

`sqrt(N(x_16)) <= (sqrt(n/3)+S)/P`.

Here `P=256^15*512` and
`S=256*(256^15-1)/255 + 363*256^15`. Exact integer arithmetic gives
`3(P-S)^2-n = 304812379843791135856135898213403037719911754649047417101132803740237872831 > 0`.
Therefore `N(x_16)<1`; because the norm is a nonnegative integer,
`x_16=(0,0)`. With `D9=364` and `D8=256`, this sufficient inequality
reverses, so 363 is the largest final bound certified by this calculation.

At window `i`, the selected point is `R_0...R_{i-1}` times the seed point,
after its unit. Sum exponent-zero choices into `B0` and exponent-one choices
into `B1`. Since `tau` is a group endomorphism and commutes with the six
units, `B0+tau(B1)` equals the original scalar multiple. This identity
charges the extra endomorphism and projective merge during evaluation.

The exact binary atlas hashes and the two prior 4,096-scalar recoding
checks are in `screen-result.json`. Group-point construction and the fresh
panel are separate validation gates in `PROTOCOL.md`.
