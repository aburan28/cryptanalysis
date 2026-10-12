# One-inversion positional τ table construction

## Question and fixed algorithm

This is a preparation-only variant of the positional τ format in
[POSITIONAL.md](POSITIONAL.md). For a fixed public point, does carrying all
`3^q S_j` and `3^q τS_j` layers in Jacobian coordinates and normalizing
them with one global batch inversion reduce table preparation cost? The
online table, digit stream, point addition, and output are identical to the
existing positional arm. This is an implementation experiment, not a claim
of a new mathematical algorithm.

Use `ca_ec_tau4_prepare` to construct the 18 seed points. Store all
`64 × 2 × 9` projective points in a temporary array. Layer zero is the
affine seeds embedded with `Z=1`; each later layer applies the existing
`jac_triple` directly to the preceding projective layer. Normalize all
1,152 entries in one Montgomery batch inversion, replacing `Z=0` by one in
the product and preserving identity entries. Release the temporary buffer
before returning. The returned table has the same layout and byte count as
the existing positional table. Report temporary peak memory as well as
persistent table bytes. Count every tripling and inversion, including
zero-point edge cases. A failed allocation or inversion fails preparation.

The primary measured outcome for this variant is **preparation wall time**
on an isolated host, with the old and new builder paired on the same public
point, source build, CPU, and memory policy. Preserve the online scalar
interval as a separate correctness and no-regression measurement. Report
cold total for one scalar and the measured reuse break-even count separately.
The operation gate is exactly one layer-normalization inversion for every
nonidentity point, versus 63 in the old builder. Both tables must produce
identical affine entries and every tested scalar result must independently
match `ca_group_mul`. A container affinity mask alone does not qualify a
wall-time claim; use the isolated benchmark receipt and retain failures.

## Prospective inputs and acceptance

After this protocol is committed and the stacked PR is opened, make four
new scalar files using the same curves, generator and `37P` in
[POSITIONAL.md](POSITIONAL.md). Generate 4,096 reduced little-endian `u64`
scalars per case with SplitMix64 state
`20261006 XOR (curve_index << 32) XOR point_index`, in that order. Freeze
input file hashes and the generic `ca_group_mul` output digest. Compare old
and global builders in alternating case order; on an isolated host use at
least five AB/BA repetitions. The correctness and operation result can be
reported on an ordinary host, but preparation and online speedups require
the host-level isolation gate. Promote the builder only if its paired
preparation wall time improves and no significant online regression appears.

The implementation is variable-time and intended for public research
scalars. Table preparation is charged to the cold and break-even accounting;
it is outside the existing prepared online interval.

## Frozen-panel result and limits

The protocol was committed as `71f4e265` and opened as PR #255 before the
new scalar files were generated. [make_global_inputs.py](make_global_inputs.py)
produced four 4,096-scalar files under [global-inputs/](global-inputs/),
with hashes and independent generic-output digests in
[global-inputs.json](global-inputs.json). The panel checker preserves stdout,
stderr, return codes, source hashes, and operations in
[global-panel.json](global-panel.json). All four cases passed: each builder
independently reproduced all 16,384 frozen scalar outputs, the online
operations matched exactly, and both builders used 1,134 table triplings per
build. Layer normalization changed from 63 inversions to one. The global
builder requires 36,864 bytes of temporary heap scratch in addition to the
unchanged 37,968-byte persistent table. The 256-build preparation controls
also passed, with 16,128 versus 256 inversions per case.

The C curve test passed 43,607 checks, including all 1,152 affine table
entries per tested point and 1,012 direct scalar point comparisons. The
complete CTest suite passed 14 of 15 tests. `coord` failed because this
sandbox denied localhost `bind()`; the raw failure is retained in
[global-ctest.log](global-ctest.log). The passing logs are
[global-test-curve.log](global-test-curve.log) and
[global-runner-tests.log](global-runner-tests.log).

[make_global_isolated_manifest.py](make_global_isolated_manifest.py) produces
a five-repetition AB/BA host-bound comparison for the 256-build preparation
arms. The isolated runner now accepts `metric_field: "prep_ms"` and labels
the result `table_preparation_256_repeats`; its default remains `online_ms`.
The generated manifest passed schema validation, but no qualifying host was
available for preflight or timing. The ordinary-host timing values preserved
in the panel are exploratory. Preparation speedup, cold break-even count,
and any CPU wall-time claim remain unknown.
