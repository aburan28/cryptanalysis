# Block-normalized positional τ scalar batches

## Frozen question

For many public scalars on one fixed point, the positional τ evaluator already
shares its table, but it converts each result from Jacobian to affine form
with a separate field inversion. This experiment retains Jacobian outputs
for a block and applies Montgomery's simultaneous inversion to their `Z`
coordinates. Simultaneous inversion is established prior art; the question is
whether its combination with the positional τ stream, including allocation,
recoding, point output, and memory traffic, wins end-to-end batch wall time.
No mathematical novelty or CPU speedup is asserted by this protocol.

Use the same `ca_ec_tau4_pos_global_prepare` table for reference and
candidate. The reference calls the existing positional multiplier separately
for each scalar and obtains every affine result inside the timed interval.
The candidate computes each scalar with the identical digit stream and mixed
additions, retaining its final Jacobian point. For each consecutive block of
`B` outputs, replace zero `Z` by one in the inversion product, perform one
inversion when the block contains a nonidentity result, and recover all
nonzero inverse `Z` values with prefix/backward products. Convert every
point to affine form in original input order. The chosen block sizes are
`B ∈ {32, 128, 512, 4096}` for 4,096 outputs. Allocate scratch inside the
timed interval and report its exact byte count. Include scalar reduction,
recoding, additions, rotations, allocation, and normalization in `online_ms`.
Keep table preparation, input loading, and independent generic point replay
outside that interval; record their times separately. Record actual output
inversions, additions, rotations, failures, and output digest. A zero-length
batch succeeds without allocation; identity outputs must remain canonical.

This is a **batch throughput** question. It does not replace the primary
single-target IC/rho metric or demonstrate a single-scalar speedup. The API
is variable-time and only for public scalars. The point table is reusable;
its preparation cost and memory remain separately charged for cold and
break-even accounting.

## Prospective panel and decision

After this protocol is committed and its stacked PR is opened, make four
new 4,096-scalar files on the two curves and two public points specified in
[POSITIONAL.md](POSITIONAL.md). Use SplitMix64 state
`20261007 XOR (curve_index << 32) XOR point_index`, store reduced little-endian
`u64` values, and freeze file SHA-256 plus the independent `ca_group_mul`
output digest. Compare the reference with all four block sizes on each file.
Every output of every arm must independently match `ca_group_mul`, including
the frozen digest. Preserve raw stdout, stderr, exit status, operation
counts, source hashes, and zero/identity controls. Do not promote a failed
or incomplete arm.

The empirical decision requires a host-level isolated benchmark receipt
for at least five AB/BA pairs per curve/point/block-size combination. The
same source, input, public point, CPU partition, NUMA node, and noise gates
apply to each pair. Report all four block sizes, memory, inversion count,
paired online wall ratio, and uncertainty. Select a deployment block size
only from qualifying isolated measurements, with its preparation and scratch
memory costs visible. Ordinary-host times are exploratory diagnostics.

Reference for simultaneous inversion and projective-to-affine conversion:
[ePrint 2008/100](https://eprint.iacr.org/2008/100.pdf), Chapter 3.

## Frozen-panel correctness and operation result

This protocol was committed as `6f7e4b48` and opened as PR #258 before the
new inputs were generated. [make_batch_inputs.py](make_batch_inputs.py)
materialized the four frozen files under [batch-inputs/](batch-inputs/);
[batch-inputs.json](batch-inputs.json) records their SHA-256 hashes and the
independent generic-output digests. [check_batch_panel.py](check_batch_panel.py)
ran the reference and four block sizes on every case. All 20 arm/case runs
passed independent generic point replay, for **81,920 verified outputs**.
The raw commands, stdout, stderr, return codes, input/source hashes, and
counts are preserved in [batch-panel.json](batch-panel.json).

| Block size | Output inversions per 4,096-result case | Online scratch |
| ---: | ---: | ---: |
| Per-result reference | 4,096 | 0 bytes |
| 32 | 128 | 1,024 bytes |
| 128 | 32 | 4,096 bytes |
| 512 | 8 | 16,384 bytes |
| 4,096 | 1 | 131,072 bytes |

Every arm used exactly the same positional additions and unit rotations on
each case. The curve test passed 43,880 checks, including zero-length,
identity-only, small-order, and partial-block controls; its raw output is
[batch-test-curve.log](batch-test-curve.log). The online scratch allocation is
included in the candidate's timed interval. The table's persistent 37,968
bytes and construction remain separate preparation costs. The ordinary-host
`online_ms` values in the raw panel are exploratory and establish no CPU
speedup.

The full local CTest run passed 14 of 15 tests. `coord` again failed because
this sandbox denied localhost `bind()`; the raw failure is in
[batch-ctest.log](batch-ctest.log). The changed-line C formatting check passed.
[batch-check.json](batch-check.json) binds the compiler, exact checks, inputs,
source, panel, and raw test logs by SHA-256.

[make_isolated_manifest.py](make_isolated_manifest.py) now generates one
five-repetition AB/BA manifest for each block size with `pos-global` as the
reference. All four generated manifests passed the isolated runner's schema
and paired-arm checks. Host preflight and isolated wall timing remain pending.
