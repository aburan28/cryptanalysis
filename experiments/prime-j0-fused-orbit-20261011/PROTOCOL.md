# Fused orbit record experiment

This candidate retains the direct 2-adic class index, 83,051-seed
tau cover, twelve radix-1024 full windows, exact terminal atlas, and
three XYZZ tau buckets. It changes the full class code from three
packed bytes to an aligned eight-byte record containing both the
point-table choice and the canonical signed digit.

1. Freeze the record format and atlas before drawing a new scalar
   panel. Independently decode every full residue and check exact
   digit, seed, exponent, and unit equality against the direct-index
   control.
2. Draw 4,096 full-range scalars disjoint modulo subgroup order from
   all earlier panels. Pair the fused and direct-index variants on
   those same scalars; verify integer reconstruction and independent
   curve points, and retain failures and operation counts.
3. Materialize a separate native mode with both variants as controls.
   Check exact native retained bytes, the targeted panel, full test
   suite, and ten edge cases. Package inherited test assets with
   crate-relative paths for Linux.
4. Queue one source-pinned Linux correctness replay behind the serial
   runner's active job. The current pod has no host-level isolation
   receipt, so local and pod timings remain diagnostics. A runtime
   speedup needs a host-isolated paired full scalar evaluation that
   charges both decode and point operations.

The [construction](atlas-receipt.json) and
[exhaustive replay](atlas-check.json) are fixed before the new panel
is drawn. The existing direct-index panel is a design control only.
