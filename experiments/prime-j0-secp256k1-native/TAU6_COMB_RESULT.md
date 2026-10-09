# Fixed-generator prime-field tau-six comb

The 12-row tau-six comb uses **972 stored affine seed points** and **42,417**
source field-product units on 128 held-out scalars. The 4-row and 8-row
paths use 324 and 648 points with 59,222 and 46,737 units respectively;
the one-row evaluator uses 135,392 units. All 214 frozen output points
match an independent secp256k1 reference in all three native modes.

## Construction and bound

For the width-six expansion `z = sum_i d_i tau^i`, choose `r` rows and column
width `L = ceil(162/r)`. Write `i = c + jL`. Precompute the 81 signed unit
digit orbits on each shifted base `tau^(jL) G`, for `0 <= j < r`. Horner
evaluation over columns computes

`zG = sum_c tau^c (sum_j d_(c+jL) tau^(jL) G)`.

The shifted bases use `(r-1)L` tau maps. Their projective coordinates are
batch-normalized, then each row's connected unit-edge seed graph makes 80
mixed-addition calls, with the point formula handling equal-point edges.
All `81r` seed outputs are normalized with a second batch inversion. The
native table stores one affine point per orbit; the other positive unit
images use the Eisenstein `omega` coordinate map at lookup, and signs use
point negation. The 4-, 8-, and 12-row setups require 123, 147, and 154
shifted-base tau maps; 320, 640, and 960 seed-graph addition calls; and
two batch inversions each.

The 162-position span covers every scalar reduced by the frozen
`short_representative` lattice rule. For `N(a,b)=a^2+3ab+3b^2`, the
lattice basis `U,V` has determinant equal to the subgroup order `n`.
The vectors `V` and `U-V` both have norm `n`, as does their difference
`U-2V`. They generate an equilateral triangular lattice with side
length `sqrt(n)`. Every point lies in a triangle whose closest vertex
has norm distance at most `n/3`. In `U,V` coordinates, a triangle vertex
lies within the frozen `5x5` search around the separately rounded center:
if its `V,U-V` coefficients are neighboring floor/ceiling integers `x,y`,
its `U,V` coefficients are `y,x-y`, at offsets at most one and two from
the respective rounded real coordinates.
The minimum-norm representative therefore has integer norm at most
`floor(n/3) = 38597363079105398474523661669562635950945854759691634794201721047172720498112`.
Let `psi(N)=sqrt(N)-sqrt(217)/26`. A zero step contracts `psi` by at least
`sqrt(3)`, and a nonzero six-step block contracts it by at least 27.
Every nondivisible state of norm below 196 is already one of the atlas
digits: `tau6_comb_screen.py` checks all 462 such states in the finite box
`|a|<=27, |b|<=16`, which contains every state with norm below 196.
The exact integer inequality `B*26^2 < 349^2*3^156` excludes a nonzero
nonterminal state from step 156 onward, where `B=floor(n/3)`.
Since every nonterminal state has norm at least three, the inequality
`B*78^2 < 85^2*3^161` excludes any nonterminal state from step 161 onward.
A final six-step block can finish at step 161, so its terminal digit fits
at position 161.

## Frozen operation counts

| Rows | Width | Seed orbits | Holdout tau steps | Holdout mixed additions | Holdout proxy | Saving from one row |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 162 | 81 | 20,243 | 3,107 | 135,392 | baseline |
| 2 | 81 | 162 | 10,012 | 3,107 | 84,237 | 37.8% |
| 3 | 54 | 243 | 6,645 | 3,107 | 67,402 | 50.2% |
| 4 | 41 | 324 | 5,009 | 3,107 | 59,222 | 56.3% |
| 6 | 27 | 486 | 3,264 | 3,107 | 50,497 | 62.7% |
| 8 | 21 | 648 | 2,512 | 3,107 | 46,737 | 65.5% |
| 9 | 18 | 729 | 2,117 | 3,107 | 44,762 | 66.9% |
| 10 | 17 | 810 | 2,023 | 3,107 | 44,292 | 67.3% |
| 11 | 15 | 891 | 1,764 | 3,107 | 42,997 | 68.2% |
| 12 | 14 | 972 | 1,648 | 3,107 | 42,417 | 68.7% |

Rows 9–11 are algebraic source-operation screens. Native point replay covers
rows 4, 8, and 12.

The source proxy charges five field-product units per tau map and eleven
per mixed addition. The count starts at the first nonzero precomputed point
and ends after the final column. It excludes digit recoding, table lookup,
cache traffic, and affine output conversion. Fixed-base table preparation
is target independent and is recorded separately above. Complete CPU
performance requires paired full-operation runs and a passing host
isolation receipt under
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).

## Reproduction

```sh
cd experiments/prime-j0-secp256k1-native
cargo test --release --bin eisenstein_fixed
cargo build --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 tau6_comb_screen.py --check-native
target/release/eisenstein_fixed --check-scalar-w6-comb4-fixed-case \
  eisenstein-pair-fixture.json 85
target/release/eisenstein_fixed --check-scalar-w6-comb8-fixed-case \
  eisenstein-pair-fixture.json 85
target/release/eisenstein_fixed --check-scalar-w6-comb12-fixed-case \
  eisenstein-pair-fixture.json 85
```

The screen independently reconstructs each Eisenstein integer and checks
the subgroup scalar congruence. The native replay checks all three modes on all
214 scalars: every representative, tau/addition count, and affine point.
The 41 release tests, including shifted-table and GLV subset point checks,
and all three fixture entrypoints pass. The result JSON
SHA-256 is
`1abf7a67b09e655b68886124155360886665e7a0f2a88a7e7c34bd1501d01401`;
the native binary SHA-256 is
`b0d1e7245baa68b1856c7799c88501f8721207ff8d2c48b8a38cfaf7c77ab4d9`.

[Hanser and Wagner](https://tugraz.elsevierpure.com/files/86425778/koblitzfb.pdf)
studied a tau-comb for binary Koblitz curves. This
implementation applies the comb arrangement to the prime-field tau map
and the minimum-norm Eisenstein width-six orbit atlas. The paired
fixed-base GLV comparison is in
[`GLV_COMB_COMPARISON.md`](GLV_COMB_COMPARISON.md).
