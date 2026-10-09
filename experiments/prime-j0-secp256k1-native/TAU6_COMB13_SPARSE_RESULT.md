# Sparse 13-row prime-field tau-six comb

A complete 13-row fixed-generator tau-six comb stores **1,024 affine seed
points** and uses **41,722 source field-product units** on 128 frozen holdout
scalars. The paired native 10-row GLV comb stores 1,024 points and uses
45,908 units; the 12-row tau comb stores 972 points and uses 42,417 units.
All 214 frozen points and a deliberate sparse-table miss match an independent
secp256k1 reference in the native executable.

## Construction

The [162-position bound](TAU6_COMB_RESULT.md) gives 13 columns and 13 rows.
Rows 0–11 store all 81 signed-unit orbits each. Row 12 stores 52 selected
orbits, for `12*81+52=1024` point entries. The selected set is frozen in
[`tau6_comb13_sparse_screen.py`](tau6_comb13_sparse_screen.py) and in the
native source. It ranks top-row orbit frequency on **10,000** independent
uniform subgroup scalars from Python seed `2026100922`; ties use seed norm
and orbit ID. No scalar from the 128-case frozen holdout or the separate
100,000-case holdout selects the table.

The 162-position proof excludes a nonterminal nonzero state from step 156.
Consequently, the top row contains at most one terminal digit. If its orbit
is absent, the evaluator uses the already-stored row-0 seed table for the
one-row tau-six evaluation of the same digit stream. The fallback always
reconstructs the same scalar and requires no additional point table.
The table builder computes the full 13th row during setup and discards 29
entries after selection; **1,024 is the retained point count**, and setup
allocations are separate from the online source proxy. Setup performs 156
shifted-base tau maps, 1,040 seed-graph addition calls, and two batch
inversions.
The table lookup and fallback branch depend on scalar digits, so this
implementation is for public scalars or variable-time use.

## Paired source-operation record

The proxy charges five field products per tau map, seven per GLV double,
and eleven per mixed addition. It covers the target-dependent point
evaluation, with lookup, scalar recoding, setup, cache traffic, and affine
output conversion recorded separately.

| Frozen panel | Scalars | Sparse tau13 | Tau12 | GLV10 | Sparse fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Edge | 22 | 1,838 | 1,873 | 1,996 | 0 |
| Design random | 64 | 20,776 | 21,106 | 22,976 | 0 |
| Holdout random | 128 | **41,722** | 42,417 | 45,908 | 0 |

The disjoint 100,000-scalar screen with Python seed `2026100923` encounters
53 distinct top-row orbits and takes the complete fallback four times. Its
charged source totals are **32,524,076** for sparse tau13, **33,091,126**
for tau12, and **35,864,687** for GLV10. That panel is an algebraic source
screen; the native point replay covers the 214 frozen scalars plus one
deliberate fallback scalar. Complete CPU wall-time comparison requires a
passing [isolated-host receipt](../../docs/ISOLATED_BENCHMARKS.md).

## Verification and reproduction

The **42** release tests pass, including a native point comparison for an
omitted top-row orbit. The saved screen checks the exact representative,
top-row selection, tau/addition counts, fallback flag, and independent
secp256k1 point for each of its 215 native inputs.
An additional seeded check verifies 522 edge and random scalars, including
negative values, order boundaries, and the deliberate fallback scalar.

```sh
cd experiments/prime-j0-secp256k1-native
export CARGO_TARGET_DIR=/private/tmp/prime-j0-comb13-target
TMPDIR=/private/tmp cargo test --release --bin eisenstein_fixed
TMPDIR=/private/tmp cargo build --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 tau6_comb13_sparse_screen.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --output /private/tmp/new-comb13-result.json
```

The frozen JSON SHA-256 is
`89c330fd5c8f9a9ac0a1e9d884b03a5d09fb7e749e6948af597c263472f2a8a2`.
The native source SHA-256 is
`6f47906f100ebfd58955839ac340e12d0a7cafb0b99dec164cb172983129b628`;
the release binary SHA-256 is
`ff74c3437a3cd0a189c6a4fbc04d32e85e0f859dfa4d87e76f8747dd5fddc360`.
