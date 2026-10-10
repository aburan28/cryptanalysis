# Direct XYZZ–Jacobian bucket merge

The deferred-tau evaluator forms `B0 + tau(B1)`. This variant keeps `B0` in
XYZZ coordinates and adds the Jacobian `tau(B1)` directly. It reuses the
two-bucket tables and scalar recoding from the preceding format. The direct
merge costs one fewer field multiplication and one fewer field squaring in
the ordinary nonexceptional completion path than converting both buckets to
Jacobian before addition.

Modes 149 (18 windows) and 150 (17 windows) leave modes 147 and 148 intact.
Their retained table sizes are respectively 3,994,692 and 6,615,956 bytes.
The paired point replay uses the 4,096 independently generated scalars and
ten boundary cases frozen in `prime-j0-tau-bucket-two-x-20261010`. The
`run_replay.py` output and `verify.py` receipt bind the executed native binary,
the source freeze, both fixtures, and every independently checked point.

The temporary `ops-diagnostic.patch` counts calls to the native field-operation
wrappers after table construction. All counts below cover the same 4,096
scalars, including the final bucket merge. `verify_ops.py` reapplies the patch
to the frozen source and checks the logged totals.

| Format | Add | Subtract | Multiply | Square |
| --- | ---: | ---: | ---: | ---: |
| 17 windows, old merge | 90,110 | 486,789 | 573,424 | 147,452 |
| 17 windows, direct merge | 90,110 | 486,789 | 569,328 | 143,356 |
| 18 windows, old merge | 94,207 | 516,260 | 606,200 | 155,646 |
| 18 windows, direct merge | 94,207 | 516,260 | 602,104 | 151,550 |

The difference is 4,096 fewer multiplications and 4,096 fewer squarings for
each width, or one of each per scalar. These are correctness and operation-count
diagnostics; CPU wall-time ratios require a host-level isolation receipt under
`docs/ISOLATED_BENCHMARKS.md`.
