# Fresh tau-preexpanded scalar replay

The tau-preexpanded table evaluates all **4,096** post-freeze secp256k1 scalars to independently generated points and agrees point for point with both the orbit-X and original nineteen-window native evaluators. Its 21,949-slot table retains **2,916,756 bytes**. Each digit selects a stored affine `P` or `tau(P)` and contributes to one Jacobian bucket. The online path performs no degree-three tau map or final projective addition and needs at most two bucket rotations. These are verified operation-path and storage properties; CPU wall timing awaits a host that passes the isolated benchmark preflight.

| Item | Value |
| --- | --- |
| Frozen source commit before scalar draw | `4b563c866` |
| Tau-expanded delta patch SHA-256 | `64b83a6649be78a66a4b9ab080c03ba09d97be3ad99f9123c860de714af5b631` |
| Full native release suite | 106 passed, 0 failed |
| Stored nonidentity `tau(P)` points checked | 21,930 |
| Fresh scalar seed / count | `20261010141` / 4,096 |
| Fresh scalar stream SHA-256 | `dbb5bb4a090d77b40886252b81a7e2d42c0561cc6eaedef5a1508c7d2b529c04` |
| Independent point fixture SHA-256 | `ab6d653abcf8b0491b8e1ceaf7c7f39bffdde4e5a565c647179acfe1c6e1dba2` |
| Native binary SHA-256 | `096245f9c3ffc923c80c7adbbd7d5d68fdd61690e7eb328ffe6c0a60ef3aaa5b` |
| Tau-expanded verified points | 4,096 / 4,096 |
| Orbit-X verified points | 4,096 / 4,096 |
| Original nineteen-window verified points | 4,096 / 4,096 |
| Three-way point agreement | 4,096 / 4,096 |
| Measurement class | correctness only |

`make_inputs.py` draws full-range 256-bit scalars and rejects any scalar congruent modulo the group order to the earlier panels, including the orbit-X holdout. `make_fresh_fixture.py` uses the independent binary group implementation in `prime-j0-tau-power16-20261010/verify_group.py`. The three native modes process the whole fixture in one command each. `verify_inputs.py`, `verify_receipt.py`, and `verify_fresh.py` check the input law, four-patch source reconstruction, frozen commit, output hashes, each expected point, and three-way equality.

At equal retained table bytes, this format moves the degree-three map into target-independent preparation, whereas orbit-X caches the three unit X coordinates and removes bucket rotations. A controlled paired run can now compare those choices on the same one-target scalar workload and physical CPU partition.
