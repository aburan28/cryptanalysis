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
arithmetic. The [fresh fixture](joint-pair-qcorr-inputs/inputs.json)
places all eight challenges into its first cases, then fills the
remaining slots with scalars disjoint from eighteen earlier fixtures.

The [release panel](joint-pair-qcorr-native-panel.json) and
[warnings-as-errors UBSan panel](joint-pair-qcorr-ubsan-panel.json)
each check 144 native arms: four corrected-quotient modes, four
integer-division guard controls, four five-neighbor controls, four
original 25-neighbor controls, a packed plane, and fixed comb9.
Every arm independently replays 4,096 outputs per case. The Python
model checks 32,768 scalar identities, 184 group decompositions,
eight subgroup-base relations, both exact GLV quotients per nonzero
scalar, and the two planted corrections on `j0-56`. The C suite passes
2,314,219 checks in both builds, including boundary scalars, identity
input, forced fallback, and wave blocks of 1, 2, 7, and 128.

| Curve | Fresh scalars | Center guard accepts | Quotient corrections | Pair additions, all formats | Serial / wave output inversions |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 16,384 | 2,098 | 0 | 32,718 | 16,384 / 128 |
| `j0-56` | 16,384 | 16,356 | 2 | 65,454 | 16,384 / 384 |

All paired output digests, group additions, rotations, unit actions,
and guard-hit counts match; there are zero scalar fallbacks. The
[isolated manifest producer](make_joint_pair_qcorr_isolated_manifest.py)
validates locally for all four same-width serial or wave pairs, each
with eight cases and 244 custody artifacts. On an unsupported floating
format, the mode uses exact integer division and reports its capability
flag as disabled; the isolated producer requires an active binary64
path before admitting a performance comparison.

This is a correctness and cost-structure experiment, not a CPU
speedup claim. Controlled wall time requires a host-level isolation
receipt. The result concerns variable-time public-scalar batch
multiplication, not one-target DLP recovery.
