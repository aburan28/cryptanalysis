# Compressed orbit gauge tree

The 96-byte compressed orbit entry removes the 1,021 runtime gauge
rotations on the previously known 512-scalar calibration panel. The
unchanged tree shapes verified all 512 independently generated secp256k1
points with zero runtime rotations and 7,679 group additions. The modeled
join interval uses 74,742 Solinas calls, compared with 75,763 for the
preceding Pareto plan. Its source-derived aggregate formula-DAG depth is
7,092, compared with 7,371. The retained table is 17,148,704 bytes,
including the plan, versus 11,552,448 bytes before materialization.

The table-preparation cost is one additional Solinas call per 174,883
entries. `calibration-check.json` and `native-receipt.json` bind the
fixture, native rows, plan, checker, overlay, and binary. These inputs
were known during design.

The source was frozen at
`7a36233a722e13d49f95642f13b2ed407b480b57` before generating a
disjoint 512-scalar holdout. Its fixture SHA-256 is
`03645e180c970c6328b0d81a86566bbe3add880b3d894dbd98c7b7d5c10bcc56`.
The native evaluator matched every independently generated point with
7,680 group additions and zero runtime rotations. On this unseen panel,
the operation model records 74,752 join calls, versus 75,773 for the
preceding Pareto plan; the formula-DAG scores are 7,079 and 7,364.
`holdout-check.json` binds the raw rows and checker. An instrumented native
build counted **74,752** actual Solinas calls in the join interval, matching
the transformed plan on every case; affine recovery made 2,048 calls and
the total was 76,800. `opcount-receipt.json` binds the counter binary,
overlay, fixture, raw rows, and checker. Complete-operation wall time,
including the larger table's cache effects, awaits an isolated host.
