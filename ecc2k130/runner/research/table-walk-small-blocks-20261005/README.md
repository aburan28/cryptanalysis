# Experimental smaller-block table-walk kernels

This change prepares variants for the single RTX 5090 / CUDA 13.3 objective
of 22 billion completed point updates per second. **It does not establish
22B/s, a GPU speedup, or a recovered discrete logarithm.** The cache-disabled
point/checkpoint diagnostic passed; cache-enabled host-path validation and
sustained throughput remain pending.

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

## Shared-device point-validation attempts

All four validation copies compiled with both `ECC_PACKED_L2_PERSIST=0` and
`ECC_PACKED_L2_POLICY=0`. For each profile, the encoded GPU `walk` instructions
matched its cache-enabled benchmark binary exactly. This permits testing the
same walk instructions without reserving cache on the shared device; it does
not validate the cache-enabled host path.

The point/checkpoint diagnostic did **not** pass. `gpu-point-validation.json`
retains four failed attempts: an incompatible cache-flag combination, a run ID
outside the 16-bit range, overflow of the default 65,536-report buffer, and a
90-second timeout after correcting those inputs and increasing report capacity
to 2,097,152. The last run stopped before a completed checkpoint, report-replay
summary or matched-state comparison. Point/checkpoint correctness and
throughput remain null. No rate from these attempts is promoted.

The original production process was verified live with the same executable
hash after the bounded job finished. No production pause or new rental was
created. The raw final metadata checksum and exact executed controller hash
are retained. `shared-point-validation-archival.py` is an archival copy of that
controller, bound to this experiment's paths and production identity; it is
not a general-purpose launcher. The dense report workload may be unsuitable
for the shared host, but the timeout alone does not identify its cause.

The earlier cache experiment reported a three-sample median of
19.853562B/s (20.432885, 19.853562, 19.819769). Its complete raw evidence was
lost after premature pod cleanup. Those logs are diagnostic context, not a
verified 22B acceptance result or evidence of these variants' performance.

## Sparse-report full-population diagnostic

A subsequent DP44 diagnostic kept **87,040 workers × 16 slots = 1,392,640
walks**, with 17 steps in each of two launches. All four profiles passed 300
CPU reference replays apiece and produced byte-identical complete checkpoints
and identical sorted report corpora. Each profile reported 6,940 points with
zero drops. The `hybrid128wave` split/resumed execution matched its uninterrupted
execution at this same population, with another 48 successful reference replays.
The total is **1,248 verified replays**. This checks the complete point-update
and report/checkpoint paths under the declared cache-disabled configuration;
it is not an end-to-end DLP solve or a throughput result.

`gpu-point-validation-success.json` retains the exact final metadata;
`shared-point-validation-sparse-archival.py` is the exact executed fixture.
The 130,505,046-byte raw archive was fully downloaded, checked against SHA-256
`abd31ab3b649f090af1e8fd5c664b37bb34b1940aa09ddf9529ad1482abfef6e`,
and unpacked locally. All 128 members, 107 source hashes, checkpoint headers,
checkpoint bytes, sorted corpora and report counts were independently checked
from the transferred artifacts. `point-evidence-custody.json` records this
receipt. The large archive and executable binaries are retained locally rather
than committed to GitHub. Earlier failed rows remain available unchanged.

The next dedicated runner, `benchmark-runner-r2.py`, repeats these full-population
gates with DP44 and explicit report capacity, including 300 replays per profile
and a full-population checkpoint-resume comparison. Its five sustained DP32
samples and 22B/s acceptance boundary are unchanged. This is a saved component
of the frozen package, requiring its maintenance guard, input/build manifests
and an approved hardware receipt; it is not a standalone provisioning command.

## Shared-device screening

Twelve subsequent throughput-only cells used the cache-disabled binaries and
the same 1,392,640 walks, with 32 launches of 1,024 steps. Each candidate had
two samples bracketed by control samples. Production continued and the whole
device power cap was 400 W. These rows are **exploratory**, with no controlled
speedup or 22B/s acceptance claim.

| Candidate | Candidate median B updates/s | Paired control median B updates/s | Exploratory ratio |
| --- | ---: | ---: | ---: |
| hybrid256 | 3.941353 | 4.086521 | 0.9645 |
| hybrid256wave | 3.938169 | 4.089040 | 0.9631 |
| hybrid128wave | 2.585648 | 4.085745 | 0.6328 |

`shared-screen-results.json` keeps every raw cell and command. These results
provide no measured reason to select the smaller blocks in this shared,
cache-disabled setup. They do not establish the ranking on an idle GPU with
cache reservation enabled. The next investigation checks the host's fixed
shared-memory carveout hint and its occupancy query, which currently omits
the table's dynamic shared bytes. No inference from these screens substitutes
for the dedicated five-sample measurement.

## Host-policy correction and diagnostic

`apply_carveout_policy.py` patches only the frozen snapshot's host launch policy.
It verifies the exact input header hash, exposes the optional integer
`ECC_PACKED_SHARED_CARVEOUT` setting, preserves the original default of 16%,
and includes the table's dynamic bytes in the occupancy calculation. CUDA's
occupancy API defines this argument as the intended per-block dynamic shared
memory size; the earlier call passed zero. The reported value is now explicitly
a prediction, not a measurement of the scheduler's actual residency.
[NVIDIA occupancy API documentation](https://docs.nvidia.com/cuda/cuda-runtime-api/cuda_runtime_api/group__CUDART__OCCUPANCY.html).

Both patched variants compiled with CUDA 13.3.73. Their encoded GPU walk
instructions matched their original variants exactly. Each passed 300 fresh
CPU report replays, zero drops, and a complete 1,392,640-walk checkpoint/corpus
comparison against the verified original. These are another 600 replays,
bringing the point-diagnostic total to 1,848.

The shared-device paired screens remained exploratory:

| Variant | Original 16% hint median B/s | Patched policy median B/s | Exploratory ratio |
| --- | ---: | ---: | ---: |
| hybrid256, 64% hint | 3.940709 | 3.734168 | 0.9476 |
| hybrid128wave, 100% hint | 2.588521 | 3.378344 | 1.3051 |

The 128-thread variant improved relative to its own slow original, while
remaining below the earlier 512-thread control at approximately 4.09B/s in
this setup. This is not a measured improvement over the best control, not a
controlled speedup, and not evidence of sustained 22B/s. No default is changed
to 64% or 100% on the basis of these shared-device cells.

`carveout-screen-results.json` retains all eight raw paired cells and both
point checks. `carveout-evidence-custody.json` records the fully transferred
65,338,399-byte archive, SHA-256
`b0f98a6e462e0375af9599edf13916e22c35ab5da29cb30443a3d71ff609206f`.
All 128 archive members and 107 source hashes were checked locally, including
the exact new checkpoints and sorted corpora. The archival build and check
controllers preserve the executed procedures and experiment-specific paths.

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
