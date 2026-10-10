# Mixed-width tau atlas construction and group replay

An exact cycle cover reduces the sixteen-window fixed-base table from
207,552 affine points to **107,814**. The new point payload is 6,900,096
bytes, and the width-eight and width-nine atlases total 1,436,064 bytes.
This uses fifteen radix-256 windows and one radix-512 window; the exact
termination inequality covers every secp256k1 scalar representative.

| Validation | Result |
| --- | ---: |
| Width-eight residues decoded and norm checked | 65,536 / 65,536 |
| Width-nine residues decoded and norm checked | 262,144 / 262,144 |
| Width-eight seeds | 5,463 |
| Width-nine seeds | 25,869 |
| Frozen prior scalars recoded to zero | 8,192 / 8,192 |
| Frozen prior scalar points matched by independent affine binary multiplication | 8,192 / 8,192 |

The independent group replay uses a separate affine point implementation
and checks the generator's degree-three eigenvalue before processing the
panels. The exact atlas, scalar-panel, and result hashes are in
`screen-result.json` and `group-check.json`. The construction source and
proof are frozen at commit `3d92ceb6f`; the group replay implementation
and receipt are recorded in the following commit.

The next integration step is to build the 107,814 native affine table
entries, verify each against an independently formed group sum, and check
the new disjoint 4,096-scalar panel after source freeze. A paired online
timing comparison then needs the qualified CPU isolation receipt required
by `docs/ISOLATED_BENCHMARKS.md`.
