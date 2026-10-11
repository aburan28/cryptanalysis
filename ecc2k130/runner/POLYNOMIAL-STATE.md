# Polynomial coordinate storage for the packed CUDA backend

`PACKED_POLY_STATE=1` stores the packed backend's persistent X/Y coordinates in
polynomial basis. General builds default to `PACKED_POLY_STATE=0`; the RTX PRO 6000 preset
enables the measured polynomial-state configuration. Both modes execute the same scalar
walk, with the same seeds, jump rule, report contents, restart behavior, and
iteration count.

The polynomial mode converts X to normal basis for Hamming weight and jump
selection, and uses normal-basis Frobenius operations to construct the X/Y
differences. It then performs the coordinate update in polynomial basis,
including polynomial squaring. This removes one principal basis conversion
per step and retains one polynomial denominator cache instead of separate
normal and polynomial caches. The allocation and automatic thread memory
estimate use the corresponding cache count. The result table below measures the complete walk; the source-level traffic
reduction is not a DRAM-bandwidth measurement.

The option requires `PACKED_CACHE_DENOM=1` and `PACKED_POLY_CHAIN=1`; invalid
combinations fail at compilation. It is independent of the existing packed
multiplication, Frobenius-network, inversion, and paired-product settings.
Runtime output identifies the selection as `packed polynomial state: 0` or
`packed polynomial state: 1`.

Packed checkpoints remain version 2, lanes 1, with normal-basis X/Y payloads.
The polynomial backend converts host staging buffers when saving and
restoring, so matching thread, batch, curve, and run-ID configurations can
resume in either direction between the two storage modes. Header and complete
payload-size validation still precede restore writes. Checkpoint export does
not change the live device coordinate representation.

The final `finished:` rate now waits for pending CUDA work in both modes.
The walk fetch already waits for the walk kernel, but a final report-triggered
reseed can still be pending afterward. Waiting before reading the completion
time includes that reseed in collection throughput. The CPU synchronization
hook is a no-op.

For a CUDA 13.0.0 environment with an RTX PRO 6000 Blackwell GPU, run these
commands from the `ecc2k130` directory to build and validate both modes:

```sh
set -eu
mkdir -p build
for state in 0 1; do
  make -B gpu test-packed-cuda \
    ARCH='-gencode arch=compute_120,code=sm_120' \
    BATCH=32 THREADS=128 MINBLOCKS=4 \
    PACKED_SINGLE_PRODUCT=1 PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 \
    PACKED_PERM_SIGMA=3 PACKED_POLY_CHAIN=1 PACKED_UNROLL_INV=1 \
    PACKED_PAIR_PRODUCTS=1 PACKED_POLY_STATE="$state"
  cp ecc2k130 "build/ecc2k130-state-$state"
  python3 codegen/testpackedclient.py "build/ecc2k130-state-$state"
done
python3 codegen/testpolystate.py build/ecc2k130-state-0 build/ecc2k130-state-1
make test-timing
```

The arithmetic gate checks polynomial squaring against independent field
arithmetic. The cross-mode gate checks byte-identical external checkpoints,
resume in both directions, reference replay of reports, restarted seeds,
matching report multisets, scalar counters, guard behavior, and preservation
of rejected checkpoints. The host timing regression uses a fake asynchronous
backend with deterministic time; it establishes the final synchronization
contract, not GPU performance.

## Reproduce the comparison

With Modal installed and authenticated, run:

```sh
modal run polystate_audit.py --output build/polystate-comparison.json
```

This builds both representations with CUDA 13.0.0 for sm120, validates them,
then compares them on one RTX PRO 6000 allocation at an identical worker count.
A faster screen triggers three alternating confirmation and collection pairs.
The artifact retains source and binary hashes, compiler and GPU identity, raw
output, exact scalar counts and complete corpus comparisons. Failed validation,
incomplete runs or inconsistent counts invalidate the result.

The usual commands select the polynomial configuration:

```sh
make bench-rtx-pro6000
make audit-rtx-pro6000
```

## Measured results

The [complete comparison artifact](benchmarks/polystate/comparison.json) uses
one RTX PRO 6000 Blackwell Server Edition, CUDA 13.0.0 / nvcc 13.0.48 and native
sm120 code. Both binaries use batch 32, 128 threads per block, minimum four
blocks, 96,256 worker threads, 1,024 steps and 32 launches. Both include the
final reseed synchronization described above.

| Workload | Normal storage, median B/s | Polynomial storage, median B/s | Change |
|---|---:|---:|---:|
| Complete scalar walk benchmark | 6.301859 | **6.547850** | +3.90% |
| DP cutoff 34 collection | 6.210069 | **6.452088** | +3.90% |

Benchmark ranges across three repetitions were 6.296461–6.305901 B/s
for normal storage and 6.546105–6.547947 B/s for polynomial storage.

Collection ranges across three repetitions were 6.208729–6.210967 B/s
for normal storage and 6.451287–6.456004 B/s for polynomial storage.

Every timed run completed **100,931,731,456 scalar coordinate updates**.
Each collection run wrote **2,633 records / 84,256 bytes**, with **zero drops**;
complete record multisets matched across both modes and all repetitions.
CPU trail replay is disabled during timing after the separate reference replay
gates pass. Setup and checkpoint restoration are outside this steady-run timer.
Reported updates include discarded work after a distinguished point until the
launch ends; at this cutoff the maximum such tail is 0.002672% of the total.

Both GPU binaries passed 3,120 Frobenius vectors, 1,261 reductions, 18,185
individual products, 18,185 paired-product cases and 1,157 polynomial squares
against independent arithmetic. Both complete integration suites passed.
Cross-mode tests passed checkpoint equality, both resume directions, complete
report replay and matching corpora, restarted seeds, scalar counts, guard
behavior and preservation of incompatible/truncated/trailing checkpoints.
The deterministic final-timing regression also passed on the build host.

The artifact includes hashes of every measured source file and both binaries.
All measured C++/CUDA files match this change. The public harness additionally
has volume-creation and checkout-path portability fixes with a local regression;
those setup changes postdate the measurement manifest. Compiler flags and
measured arithmetic are unchanged. GPU clock metadata is a snapshot, not a
continuous clock trace. These results do not establish 60 B iterations/s.
