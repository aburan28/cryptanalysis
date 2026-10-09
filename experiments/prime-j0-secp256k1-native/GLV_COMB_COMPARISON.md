# Compact tau-six and fixed-base GLV comb comparison

The compact 12-row tau-six comb uses **972 stored affine seed points** and
**42,417** source field-product units across 128 frozen holdout scalars.
The paired 10-row GLV comb uses 1,024 stored subset entries and 45,908
units. Tau reduces this source proxy by 3,491 units (7.6%) while storing
52 fewer entries; its count is lower on all 128 paired scalars. The 8-row
tau path uses 648 entries and 46,737 units, versus 53,266 units for the
512-entry, 9-row GLV source screen.

## Matched mathematical input

Both paths use the same frozen secp256k1 generator, scalar, and shortest
endomorphism-lattice representative `(a,b)` from
[`tau6-comb-result.json`](tau6-comb-result.json). The GLV components are
`k1=a+b` and `k2=-b`, since `tau=1-omega` and
`a+b*tau=k1+k2*omega`. Center rounding in the frozen lattice gives

`|k1| <= 248461680057433106740502955876103443201 < 2^128`, and
`|k2| <= 271162952692643265280958252986838904633 < 2^128`.

For `r` GLV rows, split each unsigned component into columns of width
`L=ceil(128/r)`. Precompute every nonzero subset sum of
`2^(jL)G`, then derive the second component's point with `omega` at lookup.
Global component signs use point negation. The native code stores
`2^r` table entries including identity. It prepares the shifted bases
with `(r-1)L` point doublings, forms `2^r-1-r` nontrivial subset sums,
and uses two batch inversions: one for shifted bases and one for the
subset table.

The revised tau-six comb stores one affine point per signed unit orbit,
`81r` points, and derives its two other positive unit images with the
Eisenstein `omega` coordinate map at lookup. It uses `(r-1)L` tau maps,
`80r` seed-graph addition calls, and two batch inversions during setup.
Both point tables use the same native `Jacobian` representation; this
comparison counts allocated entries, including GLV's identity slot.

## Paired holdout operation counts

GLV row 9 is an algebraically checked source-operation screen. Native
point replay covers GLV rows 8 and 10 and tau rows 4, 8, and 12.

| Method | Rows | Stored entries | Shifted-base setup | Table addition calls | Online maps | Online mixed additions | Source proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLV comb | 8 | 256 | 112 doubles | 247 | 1,920 doubles | 3,959 | 56,989 |
| Tau-six comb | 4 | 324 | 123 tau maps | 320 | 5,009 tau maps | 3,107 | 59,222 |
| GLV comb | 9 | 512 | 120 doubles | 502 | 1,792 doubles | 3,702 | 53,266 |
| Tau-six comb | 8 | 648 | 147 tau maps | 640 | 2,512 tau maps | 3,107 | 46,737 |
| GLV comb | 10 | 1,024 | 117 doubles | 1,013 | 1,536 doubles | 3,196 | 45,908 |
| Tau-six comb | 12 | 972 | 154 tau maps | 960 | 1,648 tau maps | 3,107 | 42,417 |

The source proxy charges seven field products per native Jacobian double,
five per tau map, and eleven per mixed addition. It counts the
target-dependent Horner evaluation only. Lookup, scalar recoding,
coordinate transforms, cache traffic, affine output conversion, and
setup remain separate. The native GLV baseline uses the same
Eisenstein-ring field and point formulas as the tau evaluator. It is a
specific fixed-base GLV comb, not an optimized survey of all GLV
implementations. Complete wall-time comparisons need a passing
[`isolated benchmark`](../../docs/ISOLATED_BENCHMARKS.md) receipt.

## Verification and reproduction

The saved comparison checks 214 paired scalars. Both native GLV modes
(8 and 10 rows) and all three compact tau modes (4, 8, and 12 rows) match an
independent affine secp256k1 reference on every point; the GLV component
congruence and all native operation counts match the screen. A second
seeded check verifies 521 scalars per mode, including negative values and
order boundaries. All **41** release tests pass, including native subset
table point checks.

```sh
cd experiments/prime-j0-secp256k1-native
cargo test --release --bin eisenstein_fixed
cargo build --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 glv_comb_comparison.py \
  --output /absolute/path/to/new-comparison.json
PYTHONDONTWRITEBYTECODE=1 python3 glv_comb_comparison.py \
  --random-check 512
```

The frozen comparison JSON SHA-256 is
`521baeaf3d5c2905358d9bb0d13d45c75178b0691e53fd2c6949fed29d4150f8`.
The binary SHA-256 is
`b0d1e7245baa68b1856c7799c88501f8721207ff8d2c48b8a38cfaf7c77ab4d9`;
the native source SHA-256 is
`a1aaa5aff061c650376c21f2e42d411e3153aa3e9bf404fe9a7aa5267baea663`.

The next experiment should compare the complete online operations on an
isolated host, including both recoders and on-demand `omega` work, then
test independent GLV representative selection and column-aware tau
recoding at the same table budgets.
