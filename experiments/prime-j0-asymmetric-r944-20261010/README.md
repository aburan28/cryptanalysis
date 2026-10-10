# Thirteen-window asymmetric radix-944 scalar format

The radix-944 format represents a secp256k1 scalar with thirteen Eisenstein
digits and evaluates their six-unit/tau images in two buckets. Twelve rows
use the full norm bound `944²`; the final row uses `550²`. The exact
[termination and cover proof](PROOF.md) gives 74,263 seeds per full row and
102,797 in the final row: **993,953 affine point slots**. The native table
retains **71,450,736 bytes**, including 63,612,992 point bytes and 7,837,344
binary atlas bytes.

The construction was frozen at `18f3659e6765729669a2e7cd866ae209215e6607`
before drawing the disjoint 4,096-scalar panel at
`185b202b1e357a6a10ae80b5d46408eab65b6d09`. Its scalar digest is
`31608943154c1c888ccb22281e2d24748c790b900b9b0ec5ef3b2acc70a699bd`.
The independent binary-atlas verifier checked every one of the 891,136
residues in each atlas, recomputed the minimum cycle-cover seed counts, and
checked the exact integer termination margin. A separate affine evaluator
reconstructed and evaluated all 4,096 panel scalars, comparing per-term
bucket sums, grouped-gauge bucket sums, and binary scalar multiplication.

| Same 4,096 scalars | Radix 944 | Mixed radix 512/640 |
| --- | ---: | ---: |
| Mixed additions | **49,152** | 53,248 |
| Grouped Solinas rotations | **14,838** | 15,105 |
| Native retained bytes | 71,450,736 | 31,302,596 |

The native mode-159 prototype checked all 4,096 outputs against mode 158,
checked the first 128 against an independent binary evaluator, and matched
the affine replay's operation counts. The two radix-944 native tests passed;
the quotient test covered 10,595 signed boundary cases. The
[constant-division proof](FAST_DIVISION.md) and Python checker independently
passed 100,000 deterministic 129-bit inputs.
The final-source release suite passed all **135 tests**. The public CLI also
verified the prior 4,096-point fixture and the 10-point edge fixture with
empty stderr. `native-receipt.json` records the tested binary, generated
source, raw logs, fixtures, and output hashes; `verify.py` checks their
binding to the frozen construction and input commits.

`materialize_native.py OUTPUT_DIRECTORY` applies the mode-158 base patch and
the [mode-159 delta](native-delta.patch) in a separate Cargo crate. Its
source receipt records both patch hashes and the generated source hashes.
The shared native evaluator is reserved by Conductor task T-546. Complete
source-level operation accounting must include the radix-944 quotient work,
table lookup, bucket merge, and final inversion. The current RunPod Pod fails
the host-level isolation preflight, so CPU wall-time ratios remain unmeasured
until a qualifying host executes a paired full-operation panel.
