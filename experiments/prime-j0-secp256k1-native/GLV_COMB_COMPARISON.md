# Compact tau-six and fixed-base GLV comb comparison

The compact eight-row tau-six comb uses **648 stored affine seed points** and
47,392 source field-product units across 128 frozen holdout scalars. A paired
GLV comb uses 512 stored subset entries and 53,266 units at nine rows, or
1,024 entries and 45,908 units at ten rows. This identifies a concrete
table-budget frontier: the tau path has the lower formula count within a
648-entry budget, while the 1,024-entry GLV path has the lower formula count
with a larger table. The four-row tau path uses 324 entries and 60,162 units;
the 256-entry, eight-row GLV path uses 56,989 units.

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
point replay covers GLV rows 8 and 10 and tau rows 4 and 8.

| Method | Rows | Stored entries | Shifted-base setup | Table addition calls | Online maps | Online mixed additions | Source proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GLV comb | 8 | 256 | 112 doubles | 247 | 1,920 doubles | 3,959 | 56,989 |
| Tau-six comb | 4 | 324 | 129 tau maps | 320 | 5,197 tau maps | 3,107 | 60,162 |
| GLV comb | 9 | 512 | 120 doubles | 502 | 1,792 doubles | 3,702 | 53,266 |
| Tau-six comb | 8 | 648 | 154 tau maps | 640 | 2,643 tau maps | 3,107 | 47,392 |
| GLV comb | 10 | 1,024 | 117 doubles | 1,013 | 1,536 doubles | 3,196 | 45,908 |

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
(8 and 10 rows) and both compact tau modes (4 and 8 rows) match an
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
`3ab2c1ab1ce1af152c63dcb6387fbec295a06255475737cf7e67b059345a3fa5`.
The binary SHA-256 is
`58727e2395a308756aac7ddc89e4692e5656b7da698a725fdf3aadc4d014842c`;
the native source SHA-256 is
`6f22cfea36e535ce3551792b06578a05ed81b9744612984cb550af1afa8ace03`.

The next experiment should compare the complete online operations on an
isolated host, including both recoders and on-demand `omega` work, then
test independent GLV representative selection and column-aware tau
recoding at the same table budgets.
