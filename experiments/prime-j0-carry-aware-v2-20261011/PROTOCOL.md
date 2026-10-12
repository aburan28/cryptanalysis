# Carry-aware norm-seven orbit recoding screen

## Construction

Hold the 67,338-seed, radix-1024 priority cover fixed. For each of its
174,764 unit-orbit classes, enumerate every valid representation by the
selected seed and maps `1`, `tau`, `tau^2`, and `rho=1+tau`, including maps
that land in the same class. For an exact residue, apply one of the six units
and retain every matching digit. These alternatives induce different
quotients after exact radix division; a bounded beam can choose carries that
change which maps the remaining windows need.

The screen uses twelve full windows. A path is admissible only if the final
quotient has norm below `149^2` and its weighted digits reconstruct the
original Eisenstein representative exactly. The fixed priority recoder is
replayed as a fallback for every scalar. After screening widths 1, 2, 4, 8,
and 16 on the observed design panel, freeze width 2 for the disjoint panel.
The search ranks states by (presence of rho, rho terms, nonzero terms,
quotient norm). This rank is a *screening objective*, not a calibrated point
operation cost. Record examined offers and expanded states because the online
search itself may cost more than any arithmetic it saves.

## Inputs and interpretation

Use the existing observed 4,096-scalar design panel in
`../prime-j0-adic-orbit-20261011/fresh-inputs.json` for construction
decisions. Draw the holdout with a new deterministic seed, rejecting modular
collisions with prior panels and with itself. Preserve the source cover hash,
scalar input hash, selected-digit certificate, and exact source hash in the
receipt. A favorable screen requires independent scalar and point replay,
a native implementation with
charged recoding time, and paired timing under the repository's isolation
gate. The screen reports activation and term counts, not wall-time speedup.

## Native replay

`materialize_native.py` takes the direct-XYZZ-rho materializer from the
stacked base branch, retains its original fresh panel for existing tests,
and places the disjoint carry holdout beside it. It injects mode 167, the
compressed offer index, and a test that compares every selected digit path
and point against the frozen certificates and direct-rho control. The
materialization receipt binds both generated Rust files and all input
assets. Build and test from the materialized directory with Cargo; keep
the Cargo target directory and raw test log on a filesystem with sufficient
headroom. Pass the raw log to `collect_native.py --log` after the suite
finishes. Run CLI mode 167 on the ten-case boundary fixture and pass its
stdout through `verify_native_edge.py` to bind the binary and points.

The full suite, CLI replay, and all local profiling are correctness evidence
unless a paired end-to-end run passes the isolated-host gate in
`../../docs/ISOLATED_BENCHMARKS.md`.
