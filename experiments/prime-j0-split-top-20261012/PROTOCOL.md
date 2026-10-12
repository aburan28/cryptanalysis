# Split-top Eisenstein scalar format: frozen protocol

## Contribution and instance

Test a fixed-generator secp256k1 scalar format that uses twelve radix-671
unit-orbit digits and splits the bounded terminal Eisenstein pair into two
independently tabled coordinate pairs. The low pair has both coordinates in
`[-128,127]`; the high pair is multiplied by `256` and has coordinates in
`[-184,184] x [-106,106]`. The curve, generator, subgroup, Eisenstein
endomorphism, initial representative, and unit action are exactly those in
`experiments/prime-j0-secp256k1-native/`.

The identity to verify is

`z = sum(i=0..11, 671^i d_i) + 671^12 (ell + 256 h)`.

The nearest-residue digit must satisfy `3Q(d_i) <= 671^2`. The initial
representative must satisfy `3Q(z) <= n`. These imply the universal terminal
bound `3Q(t) <= 1668628670`. The coordinate bounds above follow from
`4Q(a,b) = a^2 + 3(a+2b)^2 = (2a+3b)^2 + 3b^2`.

The ordinary table has `12 * (671^2+5)/6 = 900492` affine entries. The
rectangular low and high tables have at most `65536` and `78597` entries,
respectively. The complete point payload bound is `1044625 * 64 = 66856000`
bytes, including the identity slots. Retained runtime memory must separately
include the residue atlas, plans, table containers, and constants.

## Frozen screen and acceptance checks

- Use the 4,096 scalar design panel at
  `experiments/prime-j0-sector-digit-20261010/fresh-inputs.json`, SHA-256
  `1dd3d17f3485c144f045cf0a81394b8d129095b74ac2de9a06e06d6f4ef2cd99`.
- Use the 680-pattern Pareto plan table at
  `experiments/prime-j0-pareto-tree-20261012/plans.bin`, SHA-256
  `7e610f2f5325c4ad9619015da3f6416273530db5f82ce739d052ac5e7e931574`.
- Verify every one of the `671^2` residue assignments, its exact digit,
  unit code, and norm bound. Replay every design scalar's exact pair
  reconstruction, terminal box, and scalar congruence. Preserve one row per
  scalar and compare modeled terms, rotations, and ordinary-path products
  with the frozen radix-929 and radix-943 controls.
- Commit the format, proof obligations, screen source, and design receipt
  before drawing a new independent 512-scalar holdout. The holdout must
  verify full secp256k1 points with an independent group law and preserve
  source, input, and result digests.
- A native evaluator must charge recoding, both terminal lookups, all point
  operations, and output verification. Any wall-time ranking requires the
  host-level isolation receipt in `docs/ISOLATED_BENCHMARKS.md`.

The split-table construction is a memory and operation tradeoff. The design
screen is a source-call model, with no wall-time claim.
