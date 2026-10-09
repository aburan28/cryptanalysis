# Fixed-generator prime-field tau-six comb

A four-row and an eight-row tau-six comb share the point endomorphism across
several frozen digit streams. On 128 held-out scalars, the four-row path uses
**59,222** source field-product units and the eight-row path uses **46,737**,
versus **135,392** for the one-row tau-six evaluator. All 214 frozen output
points match an independent secp256k1 reference in both native modes.

## Construction and bound

For the width-six expansion `z = sum_i d_i tau^i`, choose `r` rows and column
width `L = ceil(164/r)`. Write `i = c + jL`. Precompute the 81 signed unit
digit orbits on each shifted base `tau^(jL) G`, for `0 <= j < r`. Horner
evaluation over columns computes

`zG = sum_c tau^c (sum_j d_(c+jL) tau^(jL) G)`.

The shifted bases use `(r-1)L` tau maps. Their projective coordinates are
batch-normalized, then each row's connected unit-edge seed graph makes 80
mixed-addition calls, with the point formula handling equal-point edges.
All `81r` seed outputs are normalized with a second batch inversion. The
native table stores one affine point per orbit; the other positive unit
images use the Eisenstein `omega` coordinate map at lookup, and signs use
point negation. The setup requires 123 or 147 shifted-base tau maps, 320 or
640 seed-graph addition calls, and two batch inversions respectively.

The 164-position span covers every scalar reduced by the frozen
`short_representative` lattice rule. Center rounding places a candidate in
the closed half-basis square. Convexity of
`N(a,b)=a^2+3ab+3b^2` bounds its norm by
`202636156165303341991249223765203838742465737488381082669559035497656782615090`.
Let `psi(N)=sqrt(N)-sqrt(217)/26`. A zero step contracts `psi` by at least
`sqrt(3)`, and a nonzero six-step block contracts it by at least 27.
Every nondivisible state of norm below 196 is already one of the atlas
digits: `tau6_comb_screen.py` checks all 462 such states in the finite box
`|a|<=27, |b|<=16`, which contains every state with norm below 196.
The exact integer inequality `B*26^2 < 349^2*3^158` excludes a nonzero
nonterminal state from step 158 onward, where `B` is the norm bound above.
Since every nonterminal state has norm at least three, the inequality
`B*78^2 < 85^2*3^162` excludes any nonterminal state from step 162 onward.
A final six-step block can finish at step 163, so its terminal digit fits
at position 163.

## Frozen operation counts

| Rows | Width | Seed orbits | Holdout tau steps | Holdout mixed additions | Holdout proxy | Saving from one row |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 164 | 81 | 20,243 | 3,107 | 135,392 | baseline |
| 2 | 82 | 162 | 10,060 | 3,107 | 84,477 | 37.6% |
| 3 | 55 | 243 | 6,699 | 3,107 | 67,672 | 50.0% |
| 4 | 41 | 324 | 5,009 | 3,107 | 59,222 | 56.3% |
| 6 | 28 | 486 | 3,390 | 3,107 | 51,127 | 62.2% |
| 8 | 21 | 648 | 2,512 | 3,107 | 46,737 | 65.5% |

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
The 41 release tests, including shifted-table and GLV subset point checks,
and both fixture entrypoints pass. The result JSON
SHA-256 is
`0d8dbd38ad11f7225bd70105ee671d5d201e69f493c4d2e231d50e1c0d679130`;
the native binary SHA-256 is
`834dc6202261916bb9817b1c92e78fe620e66e262bac23487b268e4dd3ff78b2`.

[Hanser and Wagner](https://tugraz.elsevierpure.com/files/86425778/koblitzfb.pdf)
studied a tau-comb for binary Koblitz curves. This
implementation applies the comb arrangement to the prime-field tau map
and the minimum-norm Eisenstein width-six orbit atlas. The paired
fixed-base GLV comparison is in
[`GLV_COMB_COMPARISON.md`](GLV_COMB_COMPARISON.md).
