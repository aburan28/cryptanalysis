# Exact-corrected quotient recoding

The center-guard pair recoder computes two nearest-integer GLV lattice
quotients with signed 128-bit division for every nonzero public scalar.
This candidate estimates those quotients with binary64 arithmetic and
corrects each estimate using an exact signed 128-bit remainder. It
keeps the center guard, five-neighbor fallback, point tables, and
wavefront evaluator unchanged.

For positive numerator `N=k·a` and denominator `r`, start from
`q=trunc(float(k)·float(a)/float(r)+0.5)`. Compute the exact remainder
`e=N−qr`. Increment `q` while `2e≥r` and decrement it while `2e<−r`,
updating `e` each time. The final condition
`−r≤2e<r` is exactly the positive nearest-integer quotient used by
the original recoder, including its half-integer tie rule. Thus the
floating estimate affects the number of corrections, not the answer.
The exact study bounds are `k<r<2^56` and `a<2^28`, so `N<2^84` fits
signed 128 bits. A platform without binary floating radix and at
least 53 double significand bits uses the original integer division.

The [frozen design](joint-pair-qcorr-design.json) binds the predecessor
and its training panel. Random training scalars required no quotient
corrections. The design also fixes four near-half quotient challenges
per curve using modular inverses of `2a`. Two large-curve challenges
require an exact correction under the development host's binary64
arithmetic. The new fixture will place all eight challenges into its
first cases, then fill the remaining slots with scalars disjoint from
eighteen earlier fixtures.

This is a correctness and cost-structure experiment, not a CPU
speedup claim. Controlled wall time requires a host-level isolation
receipt. The result concerns variable-time public-scalar batch
multiplication, not one-target DLP recovery.
