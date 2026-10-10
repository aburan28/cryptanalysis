# Deferred-tau two-bucket scalar format

The deferred-tau format stores one two-x orbit point per fixed-base slot and applies tau **once per scalar multiplication**. This cuts the eighteen-window table from 7,561,860 to **3,994,692 retained bytes** and the seventeen-window table from 12,804,404 to **6,615,956 bytes**. On a new post-freeze 4,096-scalar panel, the final transform and merge add exactly 12 field multiplications, 4 squarings, 6 additions, and 3 subtractions per scalar relative to the matching fused two-x mode. Source and replay scripts were frozen at `0250c22def804a9cc0d28811514d0f24a1e1ee7a` before drawing the panel.

The recoder already represents a scalar point as a sum of terms `P_j` and `tau(P_j)`. Because tau is a group endomorphism, collect ordinary terms into `B_0` and tau terms, **before tau**, into `B_1`:

`sum_j P_j + sum_i tau(P_i) = B_0 + tau(B_1)`.

Each bucket uses the existing XYZZ mixed-addition formula and the stored `(x,m,y)` orbit basis, where `m=x+beta*x`. The table therefore stores only the ordinary point. At the end, both buckets are converted to Jacobian coordinates, tau is applied to `B_1`, and the points are merged by a projective addition. For XYZZ `(X,Y,ZZ,ZZZ)` with `ZZ^3=ZZZ^2`, the conversion `(X*ZZ, Y*ZZZ, ZZ)` represents the same affine point in Jacobian coordinates. The mode is opt-in for public scalars because table addresses depend on digits.

## Exact point-kernel diagnostic

| Format | Retained table bytes | Field adds | Field subs | Field muls | Field squares |
| --- | ---: | ---: | ---: | ---: | ---: |
| Nineteen-window full orbit | 5,726,228 | 73,716 | 481,058 | 589,728 | 147,432 |
| Eighteen-window fused two-x | 7,561,860 | 69,631 | 503,972 | 557,048 | 139,262 |
| **Eighteen-window deferred tau** | **3,994,692** | 94,207 | 516,260 | 606,200 | 155,646 |
| Seventeen-window fused two-x | 12,804,404 | 65,534 | 474,501 | 524,272 | 131,068 |
| **Seventeen-window deferred tau** | **6,615,956** | 90,110 | 486,789 | 573,424 | 147,452 |

All rows use the same 4,096 public scalars and warmed tables. The [counter patch](ops-diagnostic.patch), [raw log](ops-diagnostic.log), [hash receipt](ops-diagnostic.json), and [verifier](verify_ops.py) bind the point-kernel counts to the frozen source. The counters cover calls to the field add, subtract, multiply, and square wrappers during point evaluation, including bucket conversion, tau, and the final projective merge. Table construction, scalar recoding outside those wrappers, final inversion, output conversion, and hardware time are separate boundaries. Controlled wall-time measurement requires the [isolated benchmark preflight](../../docs/ISOLATED_BENCHMARKS.md).

## Correctness and replay

The release suite passed **122 tests**. It checked all 386,676 and 222,840 nonzero ordinary unit images in the seventeen- and eighteen-window bucket tables against the corresponding full orbit tables. On a prior 4,096-scalar panel, each bucket mode matched its fused two-x reference, with the first 128 points independently checked by binary multiplication. After source freeze, the separate Python group implementation computed a disjoint 4,096-scalar fixture and ten reduction-boundary points. Both bucket modes and three references matched every point. [verify_fresh.py](verify_fresh.py) checks the source, inputs, fixtures, binary, and complete output streams.

From a full checkout:

```sh
python3 experiments/prime-j0-tau-bucket-two-x-20261010/verify_fresh.py
python3 experiments/prime-j0-tau-bucket-two-x-20261010/verify_ops.py
```

The new fixture CLI modes are `--check-scalar-unit-orbit-u256-tau-frontier17-bucket-two-x-fixed-fixture` and `--check-scalar-unit-orbit-u256-tau-frontier18-bucket-two-x-fixed-fixture`.
