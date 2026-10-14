# Native atlas for the 6,194-class scalar cover

The 67,338-seed redundant-slot cover has been reindexed into a
**1,667,480-byte DR20 atlas** with SHA-256
`61e1e7a588e7a5588d5a5e99e02a8eaa13a08e681301907e985810f7a7dbdd49`.
The [independent atlas check](native-atlas-check.json) validated all
174,764 class records and the inverse unit action on all 1,048,576 radix
residues. Its retained affine-entry count is 817,344, matching the parent
cover at the same seed budget.

The [native materializer](materialize_native.py) binds this atlas and the
fresh 4,096-scalar panel to the direct-XYZZ evaluator. Its focused release
Rust test passed locally: every point matched the adic path and certified
digit path, and the first 128 points matched independent binary multiplication.
The [receipt](local-targeted-check.json) binds the terminal test log, generated
Rust source, atlas, panel, and binary hashes. A verified parent crate was used
as the local materialization base because this sparse checkout lacked inherited
source assets; the [Linux workflow](../../.github/workflows/prime-j0-cycle-redundant-native.yml)
materializes from a full checkout and runs the complete native suite and ten
boundary fixtures. Its terminal result is pending. The local test's elapsed
time is a correctness observation. CPU wall-time comparisons must pass the
host-level isolation gate in `docs/ISOLATED_BENCHMARKS.md`.
