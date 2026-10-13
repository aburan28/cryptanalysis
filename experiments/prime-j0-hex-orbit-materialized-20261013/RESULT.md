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
were known during design. A new disjoint holdout and an instrumented
native call count will test the frozen variant next. Complete-operation
wall time, including the larger table's cache effects, awaits an isolated
host.
