# Gauge-aware reduction tree for fixed-base secp256k1 scalar multiplication

Format 171 evaluates the same U14 sector digits and 64,314,208-byte table as
format 170 with a gauge-aware XYZZ reduction tree. Specialized affine-pair
addition and later projective joins give **528,972 nominal field products**
on the frozen 4,096-scalar panel, compared with **540,634** for the serial
Karatsuba Solinas evaluator: 11,662 fewer products, or 2.157% of that model.
The sum of longest point-operation dependency chains falls from 540,634 to
201,965 products, a 62.64% reduction in modeled depth. The current Rust
evaluator executes the tree sequentially; that depth is an opportunity for
future instruction interleaving or parallel subtrees, not a wall-time result.

| Frozen panel measure | Format 170 serial | Format 171 tree |
| --- | ---: | ---: |
| Cases | 4,096 | 4,096 |
| Active affine terms | 57,343 | 57,343 |
| Gauge rotations | 8,164 | 12,886 |
| Nominal ordinary-path field products | 540,634 | 528,972 |
| Nominal 64-bit products with the same Karatsuba Solinas field kernel | 8,650,144 | 8,463,552 |
| Sum of modeled per-scalar product depth | 540,634 | 201,965 |
| Retained table and constants | 64,314,208 B | 64,314,208 B |

The release test matched all 4,096 scalar points and selector metadata to
format 170; the first 128 points also matched independent binary scalar
multiplication. Focused tests checked ordinary, doubling, and inverse
affine pairs. The release CLI matched all 129 independent fixture cases,
including scalar, generator, point, mode, and `verified=1`. `model.py`
independently reconstructed the sector choices and tree schedule and matched
the native test's exact rotation, product, and depth totals.

`GaugeTree.lean` proves that every gauge-aware tree with the same selected
leaves represents their sum, including arbitrary reordering under the stated
commutative group and order-three automorphism laws. The pinned Lean build
and axiom audit are in `lean-build.txt`; the assumptions and implementation
bridge are mapped in `PROOF.md`.

The source formula count excludes recoding, the tree selector, exceptional
branches, table access, inversion, and final conversion. The benchmark host
currently available fails the CPU isolation preflight, so no wall-time
ranking is promoted. The next measurement is a complete mode-170/mode-171
pair on a qualifying host, followed by a batched or parallel tree evaluator
if the reduced dependency depth remains useful under actual scheduling.
