# Two-x orbit basis for fixed-base scalar multiplication

The two-x orbit basis removes **64 bytes per fused table slot** while preserving the multiplication and squaring counts of the full orbit-tau XYZZ format. On a post-freeze 4,096-scalar panel, the seventeen-window table retains **12,804,404 bytes**, saving 4,125,632 bytes; the eighteen-window table retains **7,561,860 bytes**, saving 2,378,112 bytes. The corresponding point evaluations add 46,497 and 49,217 field subtractions across the panel. Source and replay scripts were frozen at `151c37bd88d895b4242db5a8d8ea8362c580da24` before the panel draw.

## Orbit identity and representation

For a primitive cube root `beta` in the field, `beta^2 + beta + 1 = 0`. On `y^2 = x^3 + b`, the order-three automorphism sends `(x,y)` to `(beta*x,y)`. Set `m = x + beta*x = -beta^2*x`. The orbit x coordinates are then

| Unit power | Selected x coordinate |
| --- | --- |
| 0 | `x` |
| 1 | `m - x` |
| 2 | `-m` |

The table stores `(x,m,y)` for an ordinary point and for its tau image. This is six field words, or **192 bytes** per fused slot, compared with eight words and 256 bytes for the three-x representation. Sign selection negates `y` as before. The 17- and 18-window recoders, tau selection, and XYZZ accumulator are unchanged. Table addresses depend on digits, so both modes are opt-in for public scalars.

## Exact point-kernel diagnostic

| Format | Retained table bytes | Field adds | Field subs | Field muls | Field squares |
| --- | ---: | ---: | ---: | ---: | ---: |
| Nineteen-window full orbit | 5,726,228 | 73,722 | 481,208 | 589,776 | 147,444 |
| Eighteen-window full orbit | 9,939,972 | 69,630 | 454,626 | 557,040 | 139,260 |
| Eighteen-window two-x | **7,561,860** | 69,630 | 503,843 | 557,040 | 139,260 |
| Seventeen-window full orbit | 16,930,036 | 65,532 | 428,037 | 524,256 | 131,064 |
| Seventeen-window two-x | **12,804,404** | 65,532 | 474,534 | 524,256 | 131,064 |

All rows use the same 4,096 public scalars. The two-x modes selected nontrivial unit powers 49,217 times at eighteen windows and 46,497 times at seventeen windows, exactly matching their extra subtraction counts. The [counter patch](ops-diagnostic.patch), [raw log](ops-diagnostic.log), [hash receipt](ops-diagnostic.json), and [verifier](verify_ops.py) bind these counts to the frozen source. The counters cover field wrapper calls during point evaluation after tables are warmed; table construction, recoding outside these wrappers, final inversion, output conversion, and hardware time are separate boundaries. A controlled wall-time comparison requires the repository's [isolated benchmark preflight](../../docs/ISOLATED_BENCHMARKS.md).

## Correctness and replay

The release suite passed **118 tests**. It checked all 773,352 nonzero images in the compressed seventeen-window table and all 445,680 in the compressed eighteen-window table against the corresponding full tables. Those full tables were previously checked against independently constructed ordinary and tau points. The new post-freeze panel independently computed 4,096 secp256k1 points with the Python binary group implementation and replayed five native modes on every scalar. Ten scalar reduction boundaries were replayed through all five modes. The complete streams, source hashes, fixture hashes, and binary hash are checked by [verify_fresh.py](verify_fresh.py).

From a full checkout:

```sh
python3 experiments/prime-j0-two-x-orbit-20261010/verify_fresh.py
python3 experiments/prime-j0-two-x-orbit-20261010/verify_ops.py
```

The new fixture CLI modes are `--check-scalar-unit-orbit-u256-tau-frontier17-two-x-xyzz-fixed-fixture` and `--check-scalar-unit-orbit-u256-tau-frontier18-two-x-xyzz-fixed-fixture`.
