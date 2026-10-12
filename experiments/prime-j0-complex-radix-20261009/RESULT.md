# Thirteen-window complex-radix storage bound

The exact screen bounds point-table storage for the current thirteen-window
secp256k1 unit-orbit construction. Within the frozen nearest-residue
norm-covering certificate family, variable Eisenstein radices require at
least **1,925,783 point slots**, or **138,656,376 point bytes** at the
implemented 72-byte affine format. The implemented integer radix 943 uses
1,926,717 slots, leaving at most **934 slots (67,248 point bytes)** to save
by changing radices under that certificate. A uniform complex radix attains
1,926,236 slots at the first feasible orbit count, saving **481 slots
(34,632 point bytes)** in the point table before recoder and map costs.

## Proof boundary

Let `n` be the secp256k1 subgroup order, `L=13`, and `r_i=sqrt(N_i)` be the
Euclidean length of the nonzero Eisenstein radix in window `i`. The existing
equilateral scalar-kernel representative starts with
`|z_0| <= sqrt(n/3)`. A nearest-residue digit gives
`|z_(i+1)| <= |z_i|/r_i + 1/sqrt(3)`. With `P=product_i r_i`, the resulting
upper bound on `|z_13|` includes both `sqrt(n/3)/P` and the final digit term
`1/sqrt(3)`. For that upper bound to be strictly below one, necessarily

`P > sqrt(n)/(sqrt(3)-1)`.

The arithmetic-geometric mean inequality then gives

`sum_i N_i >= 13 * P^(2/13)
           > 13 * (n/(sqrt(3)-1)^2)^(1/13)`.

Each quotient has `N_i` residues, and one six-unit orbit contains at most
six residues. Consequently the sum of point-table orbit counts exceeds
`(13/6)*(n/(sqrt(3)-1)^2)^(1/13)`. The receipt proves this real lower bound
is greater than 1,925,782 by the integer comparison frozen in
[PROTOCOL.md](PROTOCOL.md). Orbit fixed points can only raise the actual
slot count. This bound applies to the stated triangle-inequality certificate
for independent nearest-residue windows. A recoder with a different global
coverage argument has to be assessed on its own terms.

For one uniform complex radix of norm `N`, the full sufficient certificate
is `sqrt(n)+sum_(k=1)^13 N^(k/2) < sqrt(3)*N^(13/2)`. The left side divided
by `N^(13/2)` decreases with `N>1`, so a certified failing `N` followed by
a passing `N` identifies the first passing norm. Directed integer radical
bounds at scale `10^30` show that **889,021 fails** and **889,022 passes**.
The exhaustive equation `4N=(2a-b)^2+3b^2` finds first representable norm
**889,023** (for example `742-319*omega`). For each representable norm,
Burnside's lemma gives `(N+g2+2*g3+2)/6` unit orbits, where `g2=4` when
`4|N`, otherwise 1, and `g3=3` when `3|N`, otherwise 1. This accounts for
the nonfree unit action. The smallest orbit count in the interval is
**148,172 per window**. Norm 889,023 attains it; the lower-shear witness
`927-31*omega`, norm **889,027**, also attains it. It remains a parameter
screen: neither complex-radix recoder nor point table was built here.

## Fixed-slot capacity at 140 MiB

An independent slot with `b_i` stored nonidentity points offers at most
`1+6*b_i` choices including an implicit identity. For a fixed total `B`, the
choice product is maximized by balanced `b_i`. Exact integer binary search
finds that **12 slots need at least 5,284,490 stored nonidentity points**
before they can even meet the subgroup-order counting requirement. The
payload is at least **380,483,280 bytes** at 72 bytes per point, or
**169,103,680 bytes** even at 32 bytes per point. Both exceed 140 MiB
(146,800,640 bytes). Twelve selected points correspond to at most eleven
mixed additions when the first point initializes the accumulator.

Thirteen slots need at least 1,835,553 stored nonidentity points by the
same count, matching the prior [capacity certificate](../prime-j0-secp256k1-native/UNIT_ORBIT_CAPACITY_BOUND.md).
The counting test is necessary for coverage, not a constructive recoder.
The twelve-slot result directs the next design toward a table shared across
selection steps with an efficient decomposition algorithm, or an online
operation outside independent table selection. Such a candidate must prove
exact coverage and include decoding, any extra point work, and retained
memory in a full-operation comparison.

## Receipt and comparison status

The deterministic [screen](complex_radix_screen.py) emits the
[JSON receipt](complex-radix-screen-result.json). It records the two radical
interval comparisons, the exhaustive norm interval, beta witnesses and
orbit counts, the variable-radix integer inequality, the failing and passing
capacity products, and source SHA-256 hashes. The separate
[verifier](verify_screen.py) used 90-digit decimal arithmetic, directly
enumerated all quotient unit orbits for both equal-slot witnesses, and
recomputed both capacity thresholds; its [receipt](complex-radix-independent-verify.json)
records `status: passed`. Neither script uses timing data. The
existing radix-943 implementation remains the implemented control;
this result supplies a proof and parameter decision for the next design.

Complex-base scalar expansions and six-unit actions have prior literature,
including [Heuberger and Mazzoli](https://eprint.iacr.org/2013/705.pdf).
The contribution here is the exact resource boundary for this fixed-base
secp256k1 construction and its 140 MiB operation target.
