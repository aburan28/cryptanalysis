# Nineteen-window native scalar holdout

The nineteen-window native evaluator matched **all 4,096 newly drawn
secp256k1 generator multiples** against points from an independent affine
binary multiplier. The frozen seventeen-window native evaluator matched
the same fixture, and both output streams agree point for point.

| Check | Result |
| --- | ---: |
| Scalar residues unique and disjoint from all earlier listed panels | 4,096 / 4,096 |
| Independent binary expected points generated | 4,096 / 4,096 |
| Nineteen-window native points verified | 4,096 / 4,096 |
| Seventeen-window native control points verified | 4,096 / 4,096 |
| Nineteen-window stored nonidentity points independently checked | 21,930 / 21,930 |
| Complete native release suite | 102 passed, 0 failed |

Source, atlas, and input-generation code was frozen and pushed at commit
`6f04f10efb8990ddd0800abf7bb9d0ea2ba2debb` before the new scalar
panel was drawn. The input stream has SHA-256
`80cfd45399d9ede4bcf8a13901a82ab052a3d372abf85c995987f2be4195ee1f`.
The independent point fixture has SHA-256
`42ac5d9572ddc6c236d895195acf1b9a61586813c557d92088ca02fba2ffb4f3`.

The native table has 21,949 slots and retains **1,512,020 bytes**,
including its three atlases and metadata. The earlier seventeen-window
native table retains 4,553,140 bytes, so the new table uses 3,041,120
fewer bytes (66.79%). The [operation-frontier diagnostic](../prime-j0-tau-frontier-cost-20261010/README.md)
counts 77,814 mixed-add calls for the nineteen-window layout versus
69,631 for seventeen windows across the earlier frozen panel. This
distinguishes the storage saving from its extra arithmetic work.

`fresh-result.json` records hashes of the input, fixture, frozen patch,
binary, and both raw and compressed native output streams.
`verify_inputs.py` checks disjointness and input integrity;
`verify_receipt.py` reconstructs the exact native source from both
patches in a temporary Git index; `verify_fresh.py` checks every one of
the 8,192 native output rows against the independent fixture and each
other. The whole-fixture CLI mode kept the table warm within each native
correctness pass.

These are correctness and retained-allocation results. An online wall
comparison still requires a paired host that passes the isolated CPU
preflight. The evaluator uses scalar-dependent table addresses, so
secret-scalar routing needs a separate constant-time design and check.
