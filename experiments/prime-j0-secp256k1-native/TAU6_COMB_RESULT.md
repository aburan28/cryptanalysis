# Fixed-generator prime-field tau-six comb

A four-row and an eight-row tau-six comb share the point endomorphism across
several frozen digit streams. On 128 held-out scalars, the four-row path uses
**60,162** source field-product units and the eight-row path uses **47,392**,
versus **135,392** for the one-row tau-six evaluator. All 214 frozen output
points match an independent secp256k1 reference in both native modes.

## Construction and bound

For the width-six expansion `z = sum_i d_i tau^i`, choose `r` rows and column
width `L = ceil(169/r)`. Write `i = c + jL`. Precompute the 81 signed unit
digit orbits on each shifted base `tau^(jL) G`, for `0 <= j < r`. Horner
evaluation over columns computes

`zG = sum_c tau^c (sum_j d_(c+jL) tau^(jL) G)`.

The shifted bases use `(r-1)L` tau maps. Their projective coordinates are
batch-normalized, then each row's connected unit-edge seed graph needs 80
mixed additions. All `81r` seed outputs are normalized with a second batch
inversion. The three positive unit images per seed are materialized; signs
use point negation. Thus the four-row table has 324 seed orbits and 972
materialized unit images, while the eight-row table has 648 seed orbits and
1,944 images. The setup requires 129 or 154 shifted-base tau maps, 320 or
640 seed-graph additions, and two batch inversions respectively.

The 169-position span covers every scalar reduced by the frozen
`short_representative` lattice rule. Center rounding places a candidate in
the closed half-basis square. Convexity of
`N(a,b)=a^2+3ab+3b^2` bounds its norm by
`202636156165303341991249223765203838742465737488381082669559035497656782615090`.
For a zero step, norm divides by three. For a nonzero six-step block, the
maximum digit norm is 217 and the quotient norm is bounded above by
`floor((isqrt(N)+16)^2/729)`. The executable monotone recurrence in
`tau6_comb_screen.py` bounds the remaining tau steps by 168. A terminal
digit can therefore occupy position 168, inside the 169-position span.

## Frozen operation counts

| Rows | Width | Seed orbits | Holdout tau steps | Holdout mixed additions | Holdout proxy | Saving from one row |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 169 | 81 | 20,243 | 3,107 | 135,392 | baseline |
| 2 | 85 | 162 | 10,387 | 3,107 | 86,112 | 36.4% |
| 3 | 57 | 243 | 6,912 | 3,107 | 68,737 | 49.2% |
| 4 | 43 | 324 | 5,197 | 3,107 | 60,162 | 55.6% |
| 6 | 29 | 486 | 3,520 | 3,107 | 51,777 | 61.8% |
| 8 | 22 | 648 | 2,643 | 3,107 | 47,392 | 65.0% |

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
```

The screen independently reconstructs each Eisenstein integer and checks
the subgroup scalar congruence. The native replay checks both modes on all
214 scalars: every representative, tau/addition count, and affine point.
The 39 release tests and both fixture entrypoints pass. The result JSON
SHA-256 is
`eaa89aab4b50c405d03f4152beb838173124f66f6d6a7d3b815367389ff69a43`;
the native binary SHA-256 is
`45db7f7a62ff7044127aac3cca5f2a9514808af5df60dba46004f4177ada54e5`.

Hanser and Wagner studied a tau-comb for binary Koblitz curves. This
implementation applies the comb arrangement to the prime-field tau map
and the minimum-norm Eisenstein width-six orbit atlas. A comparison with
fixed-base GLV/comb implementations at equal table budgets is the next
algorithmic and timing step.
