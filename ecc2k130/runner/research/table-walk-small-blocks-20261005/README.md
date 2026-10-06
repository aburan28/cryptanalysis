# Experimental smaller-block table-walk kernels

This change prepares variants for the single RTX 5090 / CUDA 13.3 objective
of 22 billion completed point updates per second. **It does not establish
22B/s, a GPU speedup, or a recovered discrete logarithm.** Complete point-update
correctness and throughput remain null for the new variants.

## Implementation

The runner's `collective_inverse.cuh` now uses a portable root-placement policy.
`ECC_COLLECTIVE_CTA_WAVE` defaults to zero, preserving the existing permutation.
Its opt-in mode rotates inversion roots using a declared block-wave model.
`ECC_COLLECTIVE_WAVE_SMS` defaults to 170 and must be recorded for each hardware
experiment. This is a scheduling hypothesis, not a guarantee of block placement.
Group membership, zero substitution, tree arithmetic, publication barriers,
and final reader barriers are unchanged.

The optional `ECC_STATIC_GROUP_BARRIERS` path specializes named barrier IDs.
It also defaults to zero, preserving the existing dynamic-ID barrier path.
The experiment enables it consistently across the control and candidates.

The hybrid configurations use the existing `ECC_TABLE_ADDEND_GLOBAL` option:
selector tables remain in shared memory while larger addends use global memory.

## Evidence and scope

The archived experiment compiled with CUDA **13.3.73**, without spills:

| Profile | Threads/block | Registers/thread | Barriers | Static shared bytes | Dynamic table bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| control512 | 512 | 126 | 5 | 10,240 | 48,732 |
| hybrid256 | 256 | 126 | 3 | 5,120 | 14,148 |
| hybrid256wave | 256 | 126 | 3 | 5,120 | 14,148 |
| hybrid128wave | 128 | 126 | 2 | 2,560 | 14,148 |

These compiler receipts apply to the hash-pinned `source-snapshot.tar.gz`,
which contains 64 source files and no executable binaries, credentials, or
macOS metadata files. This snapshot has newer table-walk implementation
details than the current tracked runner. The opt-in policy is ported to the
runner, but its resource/performance behavior there is not inferred from the
archived builds. `snapshot-manifest.json` preserves every source hash and
exact compile command; `compilation-receipt.json` keeps GPU results null.

The portable test compiles the runner's policy header and checks **9,216
GF(2^131) coordinate inverses** against polynomial long division and extended
Euclid. Cases include zero inputs, all-zero groups, dense values, high
coefficients and block-wave positions. This establishes policy/model
correctness, not CUDA synchronization or complete point-update correctness.
It is not a CPU performance measurement.

## Inverse-only physical GPU check

All four configurations subsequently passed 87,057 inverse comparisons each
on the existing physical RTX 5090 with CUDA 13.3.73: **348,228 independent
Euclidean-reference matches and 348,228 inverse round trips**. The fixture
exercises all declared root-wave positions for the small blocks, zero inputs,
the final partial block, output sentinels and consecutive shared-scratch reuse.
Production stayed running. The check used private buffers and made no cache,
power, device-reset or production-signalling calls. `gpu-inverse-validation.json`
records the exact source/binary hashes and pass outputs.

This was a shared-device correctness diagnostic, with no timing/speedup claim.
It does not validate the table-walk's complete point-update kernel, global-table
read path, checkpoint behavior or performance. Those gates remain pending.

The earlier cache experiment reported a three-sample median of
19.853562B/s (20.432885, 19.853562, 19.819769). Its complete raw evidence was
lost after premature pod cleanup. Those logs are diagnostic context, not a
verified 22B acceptance result or evidence of these variants' performance.

## Reproduction

From the repository root, run the portable functional check:

```sh
python3 ecc2k130/runner/research/table-walk-small-blocks-20261005/check_root_model.py
```

On an existing Linux x86-64 CUDA 13.3.73 build host, rebuild the pinned
experiment into a new output directory. This command executes no GPU kernels:

```sh
python3 ecc2k130/runner/research/table-walk-small-blocks-20261005/build_profiles.py \
  --output /tmp/table-walk-small-blocks-build
```

Compilation must not substitute for the pending physical GPU gates. Do not
enable these variants automatically or call them faster based on occupancy
or shared-memory predictions.

To rebuild the inverse-only fixture, add `--inverse-only` to the build command.
The helper only compiles it. Running the resulting `inverse-*` executables is
a separate GPU operation and must be scoped to authorized hardware.

## Required physical measurement

Keep all profiles at **87,040 workers × 16 slots = 1,392,640 walks**: 170
512-thread blocks, 340 256-thread blocks, or 680 128-thread blocks. Using a
constant 170-block count would change the workload population.

Require an auditable idle GPU; matched full logical states and sorted report
corpora; 300 fresh selected-profile CPU report checks; exact split/resumed
versus uninterrupted checkpoints and corpora; and zero dropped reports.
The 22B gate needs five fresh 512-launch DP32 samples, each counting
730,144,440,320 updates with three reference checks, and a median rounding
lower bound at least 22B/s. Short screens cannot satisfy that gate.

Retrieve primary metadata first and then the complete raw archive. Confirm
the transfer is terminal, check the archive's expected size and SHA-256, and
record verified local custody before manual cleanup. Rentals and production
pauses need their own authorization; these scripts provision no resources.
