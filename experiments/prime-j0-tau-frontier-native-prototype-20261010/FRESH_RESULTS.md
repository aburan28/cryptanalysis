# Seventeen-window native scalar holdout

The seventeen-window native mode recovered the expected secp256k1
generator multiple for **all 4,096 fresh scalars** drawn after source
freeze `a913a83a5`. A separate affine binary multiplier generated the
expected points. The existing radix-384 mode verified the same fixture,
and both native output streams agree point for point.

| Check | Result |
| --- | ---: |
| Fresh scalars unique modulo subgroup order and disjoint from earlier panels | 4,096 / 4,096 |
| Independent binary expected points generated | 4,096 / 4,096 |
| Seventeen-window native points verified | 4,096 / 4,096 |
| Paired radix-384 native points verified | 4,096 / 4,096 |
| Stored nonidentity native points checked against separate group sums | 64,446 / 64,446 |
| Fixed fixture cases verified | 129 / 129 |
| Complete release tests | 100 passed, 0 failed |

The native table has 64,463 slots and retains 4,553,140 bytes,
including its three atlases and table metadata. The input scalar stream
has SHA-256 `08a033bba5f198c5f0da9236433f898a12d2fdd9fb7062c6a3e01b62abb46f16`.
`fresh-result.json` records the input, fixture, patch, binary, and raw
output hashes. `verify_fresh.py` checks all 8,192 output rows from the
two modes against the independently generated fixture and each other.

Online wall time remains a paired isolated-host experiment. The current
RunPod container fails the repository's host isolation preflight, so
these runs are correctness evidence and a native retained-byte result.
