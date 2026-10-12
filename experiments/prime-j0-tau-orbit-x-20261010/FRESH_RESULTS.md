# Fresh orbit-X scalar replay

The orbit-X table evaluates every one of the 4,096 post-freeze scalars to the independently generated secp256k1 point and agrees with the original nineteen-window native format on every case. Its table retains **2,916,756 bytes** for 21,949 slots. This is 1,636,384 bytes less than the seventeen-window table, while the direct-unit layout eliminates the baseline's runtime bucket rotations. The cost is 1,404,736 more retained bytes than the original nineteen-window table. These are exact storage and operation-path properties; this run records correctness without a CPU timing comparison.

## Reproducibility

| Item | Value |
| --- | --- |
| Frozen source commit before scalar draw | `3326010dd` |
| Orbit-X delta patch SHA-256 | `2326cb66feb886d54e795971135a9463269fde92e3b7c81cb82cf0d1c8ac1197` |
| Full release suite | 104 passed, 0 failed |
| Cached unit images compared with native point table | 131,580 |
| Fresh scalar seed / count | `20261010140` / 4,096 |
| Fresh scalar stream SHA-256 | `9d05e25932fddbb53366b1bd3ef08b81676ffe9f8c99d1a3b5d8e81fa9dead0e` |
| Independent point fixture SHA-256 | `7bee8eec554dd0e85411444feeee9c2cf19131a9632d6beb852c7c38f2919ccd` |
| Native binary SHA-256 | `b7c7dbe001f13a0b2bc47d9c088322792b4dce528df76695e70d89d65185f4dc` |
| Orbit-X native verified cases | 4,096 / 4,096 |
| Original nineteen-window native verified cases | 4,096 / 4,096 |
| Pairwise output agreement | 4,096 / 4,096 |
| Measurement class | correctness only |

`make_inputs.py` rejects scalars congruent modulo the group order to any recorded earlier panel, including the immediately preceding nineteen-window holdout. `make_fresh_fixture.py` uses the independent binary group implementation in `prime-j0-tau-power16-20261010/verify_group.py` to produce expected affine coordinates. Both native modes then process the whole fixture in one command each. `verify_inputs.py`, `verify_receipt.py`, and `verify_fresh.py` check the input law, three-patch source reconstruction, frozen commit, output hashes, per-row point equality, and pairwise agreement.

The existing RunPod pod runs the serial benchmark service, but its strict preflight rejects controlled CPU timing because the container lacks a host-level isolated partition and related controls. The next performance step is a paired format-138/format-139 run on a physical Linux host that passes that preflight, with the same public scalar panel, matched binaries, and complete receipt.
