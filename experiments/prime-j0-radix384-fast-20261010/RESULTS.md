# Two-limb radix-384 scalar recoder

The specialized recoder computes exactly the same fifteen radix-384
Eisenstein digits and secp256k1 point as mode 133, while replacing its
six 32-bit chunk divisions per coordinate with two 64-bit constant
divisions. It retains the same 24,283,336-byte point table, the same
maximum of fourteen mixed additions, and the same grouped unit gauge.

The macOS ARM64 release compiler lowered the quotient work before the
first orbit lookup as follows. Counts are instructions in that compiled
loop, not elapsed-time measurements.

| Mode | `umulh` | `umull` | `udiv` |
| --- | ---: | ---: | ---: |
| 133, generic radix 384 | 10 | 2 | 0 |
| 134, two-limb quotient | 4 | 0 | 0 |

The [proof](PROOF.md) derives the two-limb quotient and the certified
coordinate bound. The [local receipt](evidence/local/receipt.json) binds
the compiler build, binary, source, fresh inputs, assembly audit, and raw
correctness logs. The implementation and generator were frozen in commit
`5ceb68277c8de04250daf0e0732abc651fb98d34` before drawing the
panel with scalar stream SHA-256
`eb378bc70d04f513b8f6f28e622daa17c0914b8c672c099b6185bd5ac6752f73`.

| Correctness check | Result |
| --- | --- |
| Signed quotient/remainder boundaries | 10,595 cases matched generic division |
| Prior panel | 4,096 complete scalars matched mode 133 |
| New disjoint panel | 4,096 complete scalars; 122,880 per-step divisions matched |
| Independent binary multiplication | First 128 new scalar points matched |
| Fixed fixture | 129 verified points per mode; rows matched after mode labels |
| Release suite | 95 passed, zero failed |

The local host was macOS ARM64. A controlled CPU wall-time comparison
remains gated by the host-level isolation requirements in
`docs/ISOLATED_BENCHMARKS.md`. The current RunPod container can perform
a serialized Linux correctness replay.
