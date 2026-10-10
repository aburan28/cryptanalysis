# Eighteen-window orbit-tau XYZZ scalar format

The eighteen-window format reduces the 4,096-scalar point kernel by **32,720 field multiplications and 8,180 squarings** compared with the nineteen-window XYZZ format, while retaining **9,939,972 bytes** of table data. It gives a middle point between the nineteen-window table at 5,726,228 bytes and the seventeen-window table at 16,930,036 bytes. Source and replay scripts were frozen at `f3c421d7ebdf5f6325797cacb9de44cb75bb60d4` before drawing the panel.

The width schedule is fourteen 7-bit windows, three 8-bit windows, and a final 7-bit window. The final window begins at bit offset 122, as in the seventeen-window schedule, so it uses the same certified final-width atlas. Each nonzero table slot stores the ordinary and tau images for one seed together with their three cube-root x images. The selector applies the unit sign and the XYZZ accumulator adds the selected affine points. The exact recoding identity is

`a + b*tau = sum_j 2^h_j * u_j * tau^e_j * d_j`.

The final point is `[a + b*lambda_tau]G = [k]G`. The mode is opt-in for public scalars because table addresses depend on the digits.

| Format | Table slots | Retained bytes | Field adds | Field subs | Field muls | Field squares |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nineteen-window XYZZ | 21,949 | 5,726,228 | 73,718 | 481,395 | 589,744 | 147,436 |
| Eighteen-window XYZZ | 37,158 | 9,939,972 | 69,628 | 454,738 | 557,024 | 139,256 |
| Seventeen-window XYZZ | 64,463 | 16,930,036 | 65,533 | 428,151 | 524,264 | 131,066 |

All rows use the same newly drawn 4,096-scalar panel. The point-kernel counters cover calls to the field add, subtract, multiply, and square wrappers during point evaluation after the tables are warmed. They exclude table construction, scalar recoding outside those wrappers, final inversion, output conversion, and hardware time. The [counter patch](ops-diagnostic.patch), [raw log](ops-diagnostic.log), [hash receipt](ops-diagnostic.json), and [verifier](verify_ops.py) bind the counts to the frozen source.

The release suite passed 114 tests. It checked all **445,680** nonzero `(window, seed, tau exponent, unit)` table images against independently built points, compared 4,096 prior scalars with the nineteen-window mode, and checked the first 128 of those by independent binary multiplication. After source freeze, an independent Python binary multiplication fixture and complete native output streams verified a disjoint 4,096-scalar panel plus ten scalar reduction boundaries. [verify_fresh.py](verify_fresh.py) checks the source commit, input law, fixtures, hashes, and complete output streams.

From a full checkout, verify the frozen receipts with:

```sh
python3 experiments/prime-j0-frontier18-orbit-xyzz-20261010/verify_fresh.py
python3 experiments/prime-j0-frontier18-orbit-xyzz-20261010/verify_ops.py
```

The CLI mode is `--check-scalar-unit-orbit-u256-tau-frontier18-orbit-xyzz-fixed-fixture`. CPU wall-time comparison requires a host that passes [the isolated benchmark preflight](../../docs/ISOLATED_BENCHMARKS.md).
