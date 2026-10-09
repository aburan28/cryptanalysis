# Complex-radix and fixed-slot capacity screen

## Research question

Determine how much point-table storage a thirteen-window Eisenstein radix
can save relative to the implemented radix-943 secp256k1 format, and whether
twelve independent six-unit table selections can cover the subgroup under a
140 MiB point-payload budget. This is a mathematical resource screen. No CPU
timing enters the result.

## Frozen model and inputs

Use the secp256k1 subgroup order
`FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141`
and the 72-byte affine table entry of the existing radix-943 implementation.
The implemented control has 13 tables with 148,209 entries each, or
1,926,717 point slots. Keep point slots separate from orbit maps, metadata,
allocator overhead, and table construction time.

For the radix screen, represent the initial scalar by an Eisenstein integer
`z_0` of Euclidean length at most `sqrt(n/3)`. At window `i`, use nonzero
Eisenstein radix `beta_i` with norm `N_i` and Euclidean length `r_i=sqrt(N_i)`.
Choose a nearest residue digit of length at most `r_i/sqrt(3)`, then divide
`z_i-digit_i` by `beta_i`. The certificate family requires the resulting
triangle-inequality upper bound on `|z_13|` to be strictly below one for all
admissible `z_0`. Each table stores at least one point per orbit of its
`N_i` residues under the six units. The variable-radix lower bound is only
for this specified norm-covering certificate family; correlated digits or a
different coverage proof have a different gate.

For a uniform complex radix, test the exact sufficient inequality

`sqrt(n) + sum_(k=1)^13 sqrt(N)^k < sqrt(3) * sqrt(N)^13`.

Find the first passing integral `N`. Enumerate all Eisenstein norms from that
threshold through `943^2`. Use `N(a+b*omega)=a^2-a*b+b^2`,
`c=2a-b`, and `4N=c^2+3b^2`; bound `|b|` by `sqrt(4*943^2/3)` and require
`c+b` even. Record the first representable norm and the minimum unit-orbit
count in the interval. For each beta, compute the exact orbit count by
Burnside's lemma, including nonfree action at factors 2 or 3:

`orbits=(N+g2+2*g3+2)/6`, where `g2=4` if `4|N` and `1` otherwise, and
`g3=3` if `3|N` and `1` otherwise. Check integer divisibility. Record a
small-coefficient beta witness for the minimum orbit count.

For the independent-slot screen, each of `T` fixed slots with `b_i` stored
nonidentity points offers at most `1+6*b_i` choices. Given total `B`, the
maximum choice product uses balanced `b_i`. Binary-search the least integer
`B` whose balanced product is at least `n` for `T=12` and `T=13`. Check both
the failing `B-1` and passing `B` products exactly. Compare 12-slot payload
at 72 and 32 bytes per point with 140 MiB. This capacity model permits an
implicit identity per slot and unit actions; it does not assert existence of
an efficient full-coverage recoder at its counting threshold.

## Integer certificate and validation

Use scale `S=10^30` and `isqrt(x*S^2)` to enclose every square root in an
interval of width `1/S`. Prove the uniform-radix inequality true or false at
each side of the threshold using directed integer bounds after multiplying
by `S^14`. For the variable-radix lower bound, set `K=1,925,782` and prove

`(6K)^13 * (4S-2*floor(S*sqrt(3))) < 13^13 * n * S`.

This certifies that the real lower bound on total table slots exceeds `K`.
The script must also independently verify every returned norm witness and
orbit formula, and emit a JSON receipt with all integer comparisons, source
hashes, model parameters, and a separate next-design decision. Any failed
assertion is a failed screen; preserve the source and report the failure.

Commit this protocol before implementing and running the screen. The result
remains a parameter and proof screen, not a measured speedup or an academic
priority claim. Existing complex-base digit work includes [Heuberger and
Mazzoli (2013)](https://eprint.iacr.org/2013/705.pdf); this screen concerns
the exact fixed-base memory budget and certificate family above.
