# Fourteen-window radix-512/640 tau format

The format represents the certified nearest Eisenstein pair for a secp256k1
scalar with six radix-512 digits followed by eight radix-640 digits. The first
six digits use the existing complete width-nine two-bucket atlas; seven
radix-640 digits use the new full-bound atlas; the last uses bound 391.
It stores 415,190 affine seed points. Evaluation groups six-unit powers
inside each of the two tau buckets, then computes `B0 + tau(B1)`.

For an Eisenstein pair `z=(a,b)`, set `N(z)=a²+3ab+3b²`. The unit action
preserves `N`, while `tau(a,b)=(-3b,a+3b)` has norm multiplier three and
determinant three. Since `gcd(640,3)=1`, tau permutes the six-unit residue
classes modulo 640. Burnside's lemma gives `(640²+8)/6=68,268` classes.
The deterministic nearest digit of each class and its tau successor form
disjoint cycles. The same exact one- or two-class segment dynamic program
as the [earlier proof](../prime-j0-tau-power16-20261010/PROOF.md) gives
the minimum seed count for each bound. The full-bound atlas has 34,135
seeds, of which 34,133 cover two classes. The final-bound atlas has 45,163
seeds: 23,105 two-class segments and 22,058 singletons. All 409,600
residues were decoded and checked for their exact congruence and norm.
The largest decoded norms are 408,324 and 152,868, respectively, below
`640²` and `391²`.

Let `R_i` be the radices, `D_i` the digit norm bounds, `P=product R_i`, and
`S=sum_i D_i product_{j<i}R_j`. The initial nearest-lattice pair satisfies
`3N(z_0)<=n`, where `n` is the secp256k1 group order. Since each step is
`z_(i+1)=(z_i-d_i)/R_i`, the norm triangle inequality gives

`sqrt(N(z_14)) <= (sqrt(n/3)+S)/P`.

Here `P=507060240091291760598681282150400000000`,
`S=310575636933263844436138200734829380096`, and
`3(P-S)²-n=26508597186945872034846785349754346156954426674993113148162584666361413311>0`.
Thus `N(z_14)<1`, so the final integer pair is exactly zero. The generator
also checks that raising the last bound from 391 to 392 reverses this
particular sufficient inequality. The full atlas receipt records every
cycle length, segment count, binary hash, and bound check.

For each selected seed point, the atlas records one of two tau exponents
and one of six units. The unit and tau maps commute, so accumulating seed
points in buckets by tau exponent and applying tau once to the second
bucket yields the original scalar multiple. The grouped-unit gauge proof
in [mode 157](../prime-j0-bound-budget15-gauge-20261010/PROOF.md) applies
unchanged within each bucket. The independent affine group replay computes
both per-term and grouped-gauge bucket sums and compares each with binary
scalar multiplication.

The 14 tables contain `6*21,847+7*34,135+45,163=415,190` points, with
26,572,160 bytes of 64-byte affine payload. The three binary atlases
occupy `1,135,972+1,774,948+1,819,060=4,729,980` bytes. Native
container overhead and online radix-640 division must be charged by the
eventual implementation; these exact payload counts are construction data.
