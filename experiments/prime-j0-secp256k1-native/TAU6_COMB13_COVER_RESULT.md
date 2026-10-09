# Additive terminal cover for the sparse tau comb

Every omitted top-row digit in the 1,024-point sparse tau-six comb is the
**exact sum of two retained unit-orbit digits**. Substituting those two
precomputed points makes the 13-row evaluation complete within at most one
additional mixed addition. The comb retains 12 tau steps and the same 1,024
affine point slots even when the top digit's orbit is absent.

On the deliberately omitted-orbit scalar, the complete point-evaluation
proxy falls from **1,044 to 335 field-product units**: 156 tau steps become
12, while the mixed-addition count rises from 24 to 25. On an independent
100,000-scalar panel, two repairs occur and the complete proxy falls from
32,530,426 to **32,529,008** units. The gain concentrates in the rare
omitted-orbit tail.

## Coverage argument

The width-six atlas has 81 unit orbits and 486 digit images. The frozen top
row retains 52 orbits, leaving 29 orbits or 174 digit images. At table setup,
the native implementation enumerates exact coefficient sums of retained
unit images. It verifies that every one of those 174 images has a two-sum
expression, then stores the chosen pair as small metadata. Both summands use
the already retained row-12 affine points.

The 162-position proof places at most one nonzero digit in positions
156–161, which form row 12 of the 13-column comb. Consequently, any scalar
needs at most one such repair. If the ordinary fast evaluation has `t` tau
steps and `a` mixed additions, the cover evaluation has the same `t <= 12`
and at most `a+1` mixed additions. Its source point cost is therefore
`5*t + 11*(a + repair)`, where `repair` is zero or one. The same recoding
and short representative are used. For public scalars, the branch on the
top digit is allowed; this implementation is variable-time.

## Frozen workload and verification

The source screen reconstructs all missing digit coefficients exactly,
replays the 214 frozen scalars and a deliberately omitted top-row orbit,
and checks a disjoint uniformly generated scalar panel. Native outputs are
compared with independent secp256k1 point multiplication. Its result JSON
retains the source and binary hashes, every frozen input, panel counts, and
the deliberate repair's operation record.

| Panel | Scalars | Original sparse proxy | Two-sum cover proxy | Repairs |
| --- | ---: | ---: | ---: | ---: |
| Frozen edges | 22 | 1,838 | 1,838 | 0 |
| Frozen design random | 64 | 20,776 | 20,776 | 0 |
| Frozen holdout random | 128 | 41,722 | 41,722 | 0 |
| Disjoint random, seed `2026100932` | 100,000 | 32,530,426 | **32,529,008** | 2 |

The **44** native release tests pass. The screen independently verifies
**473** native scalar points: 214 frozen, one deliberate repair, the first
256 disjoint random scalars, and both repairs encountered in the disjoint
panel. The isolated manifest passes structural validation, and all **258**
paired fixture checks return the frozen points and input fields.

The paired isolated manifest compares the previous sparse mode with
`--benchmark-scalar-w6-comb13-cover-fixed-case` on the same 129 frozen
scalars, including the deliberate omission. The timer includes any two-sum
repair and independent expected-point assertion; table and repair-map setup
are recorded as reusable preparation outside that interval. A wall-time
comparison requires a passing host receipt under
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).

## Reproduce

```sh
cd experiments/prime-j0-secp256k1-native
export CARGO_TARGET_DIR=/private/tmp/prime-j0-comb13-target
TMPDIR=/private/tmp cargo test --offline --locked --release --bin eisenstein_fixed
TMPDIR=/private/tmp cargo build --offline --locked --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 tau6_comb13_cover_screen.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --output /private/tmp/new-comb13-cover-result.json
```

The frozen result SHA-256 is
`18300278da10eed8a2c1decf5df8dfb8b4abe59d5c8e4e01d1913f4b6589d3d4`.
The native source SHA-256 is
`be7afa95d94b3a63af2d992c0fab2e973d25033a18992de561d1615ae8823b34`;
the release binary SHA-256 is
`1c8838c8e138a2e036b3abfd9b7b5944b61f203ee64e81a2cad9c2417292952e`.
