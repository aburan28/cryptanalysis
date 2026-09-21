# Native macOS / Metal table access

The public pair tables are portable little-endian data. Native Metal support
covers device discovery, table-size planning, downloading, bounded pair-table
lookup validation, and a complete synthetic point-dependent walk over the
compact signed-direction table.

## This Mac

Live device queries on 2026-09-21 reported:

| Property | Measured value |
| --- | --- |
| GPU | Apple M4 Pro |
| Unified system memory | 51,539,607,552 bytes (48 GiB) |
| Recommended Metal working set | 40,200,896,512 bytes (40.20 GB) |
| Maximum single Metal buffer | 30,150,672,384 bytes (30.15 GB) |
| Selected artifact | h128, 20,244,542,976 coordinate bytes |

The smaller table lies within both reported Metal limits. The 80.98 GB table
does not fit this machine's physical memory. It can still be inspected through
bounded file windows; that does not make it a resident GPU table.

Apple describes `recommendedMaxWorkingSetSize` as a performance-oriented
working-set approximation, not a query for globally free GPU memory. The
planner therefore labels it a planning budget, reserves 2 GiB by default,
and reports whether `maxBufferLength` would require segmentation. Existing
applications and memory pressure still matter when allocating resources.
See Apple's [working-set property](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize)
and [maximum buffer length](https://developer.apple.com/documentation/metal/mtldevice/maxbufferlength).

## Build and query

Run natively from a normal macOS terminal. Xcode Command Line Tools provide
the C++ compiler, Foundation and Metal frameworks. The lookup shader compiles
through Metal at runtime; the offline `xcrun metal` utility is not required.

```sh
make -C /Volumes/SSD990/cryptanalysis/ecc2k130/metal
/Volumes/SSD990/cryptanalysis/ecc2k130/build/metal-pair-table info
python3 /Volumes/SSD990/cryptanalysis/ecc2k130/table_store.py select --backend metal
```

On macOS, `--backend auto` (the default) chooses Metal. On Linux it chooses
CUDA. Metal device selection accepts an enumeration index or registry ID.
`CUDA_VISIBLE_DEVICES` applies only to the CUDA backend.

The Codex execution sandbox exposed no Metal devices on this host. The same
helper queried the GPU and executed the validation successfully outside that
sandbox. If a restricted runner reports no Metal GPU, use a native macOS
process with GPU access; do not interpret an explicit memory override as proof
that Metal is available.

## Validate existing table files on the GPU

```sh
/Volumes/SSD990/cryptanalysis/ecc2k130/build/metal-pair-table smoke \
  /Volumes/SSD990/cryptanalysis/ecc2k130/research/step_table/pair128-24gb-20260921/pairs.bin

/Volumes/SSD990/cryptanalysis/ecc2k130/build/metal-pair-table smoke \
  /Volumes/SSD990/cryptanalysis/ecc2k130/research/step_table/pair256-88gb-20260921/pairs.bin
```

Both commands passed on the M4 Pro: 8,192 GPU queries per file, **16,384 total**.
The shader computes the unordered-pair index using 64-bit arithmetic, reads
all nine coordinate words, and returns the global index. CPU checks compare
every word and index, including infinity records and indices above 2^31 in
the large table's suffix. Each command stages only the first and last
4,194,288-byte windows, one at a time, in shared Metal buffers.

These checks validate GPU indexing and record access. They neither allocate
the full table nor measure a complete walk's throughput. The JSON results
explicitly report `fullTableResident: false` and `rhoKernelExecuted: false`.

## Download on another Mac

After building the helper, `table_store.py fetch --backend metal` selects the
artifact from the live Metal planning budget, downloads it from the public S3
catalog, and verifies its checksum. Add `--cache` to choose a persistent volume
and `--reserve-gib` for the consumer's workspace. The files already generated
on this host can be used directly with the lookup test above.

The [table-store guide](../tables/README.md) documents resumable downloads and
the CPU point/coefficient API. No AWS credentials are needed for downloads.

## Run the synthetic walk

The walk uses the public artifact's field, selector, signed Frobenius
directions, 32-bit three-tag cycle history, distinguished-point reports, and
deterministic reseeding. Every lane carries its seed, trail count, total update
count, report digest, and endpoint. The command prepares independent Python
field vectors and then replays selected GPU lanes and every report:

```sh
python3 /Volumes/SSD990/cryptanalysis/ecc2k130/metal/run_walk.py \
  --artifact-dir /Volumes/SSD990/cryptanalysis/ecc2k130/research/step_table/pair128-24gb-20260921 \
  --out /private/tmp/ecc2k-metal-walk \
  --branches 128 --lanes 128 --cycles 64 --launches 4 --verify-lanes 32
```

While the kernel runs, the wrapper streams one line per launch, for example:

```text
progress launch 2/4: 8192 walk iterations, 0.244 M iterations/s, 0 seed additions, 0.244 M charged group ops/s, 0.033571 GPU s
```

`iterationsPerSecond` counts completed point-dependent walk updates divided by
Metal GPU command time. Reseed additions are reported separately and included
in `chargedGroupOperationsPerSecond`. `wallIterationsPerSecond` also includes
host dispatch and report-copy overhead. Use `--progress-every N` to print less
frequently during long runs.

The bounded 128-lane control measured 0.231 million iterations/s overall;
steady launches measured 0.247--0.250 million iterations/s. Its
[throughput receipt](evidence/walk128-throughput.json) binds the final state,
binary, source inputs, GPU time, wall time, and rate arithmetic. This is the
synthetic correctness kernel's finite rate, not the optimized production
client's throughput.

Omit `--artifact-dir` to download only `directions.bin` and
`coefficients.json` from the public catalog. The 20 or 81 GB pair payload is
not needed by this recurrence. Output paths must be new.

Two bounded controls passed on the M4 Pro:

* 128 branches, relaxed DP weight: all 17 final lane states and 271 reports
  matched the independent Python recurrence.
* 256 branches, no DP reseeding: all 33 final lane states matched after 2,079
  point-dependent updates. This exercises direction IDs beyond 16 bits.
* Before either walk, 198 independent products, squares, inverses, additions,
  doublings, infinity and inverse-pair cases matched Python arithmetic.

The checked-in receipts are
[the 128-lane DP32 control](evidence/walk128-control.json),
[the dense-DP report control](evidence/walk128-dp-control.json), and
[the 256-branch control](evidence/walk256-control.json). A fourth
[control](evidence/walk128-public-download.json) fetched its directions and
coefficients anonymously from the public catalog before replaying all lanes.
[The macOS Python 3.9 control](evidence/walk128-python39.json) runs the full
documented 128-lane command with the compatibility popcount path. They bind source and
binary hashes, complete state/report digests, counts, and raw Metal timings.

The runner splits launches into bounded Metal command buffers, measures each
GPU command, fails closed on report overflow, and writes `state.bin`,
`reports.bin`, `native.log`, and `result.json`. The results charge reseed point
additions separately from walk updates.

This is a **synthetic unknown-scalar control** using Q=[65537]P. It does not
join the production Certicom campaign and its checkpoints are a new format.
The current implementation is a correctness path, not an optimized throughput
claim.

## Pair acceleration remains disabled

The artifact walk includes Metal Shading Language GF(2^131) multiplication,
reduction, squaring, batched inversion and complete affine point updates. It
uses generated masked carryless multiplication because Apple GPUs expose no
CUDA/PTX CLMAD instruction.

For a resident table consumer, read the data into shared Metal buffers while
avoiding an unnecessary second 20 GB host copy. Check allocation results and
the working set. Devices with smaller per-buffer limits need record-aligned
segments and a shader capable of selecting the correct segment.

Using precomputed pair sums to eliminate an intermediate addition still needs
an exact, profitable intermediate branch-selection method. The full walk
therefore loads compact signed directions and reports `pairTableLoaded: false`.
The separate pair lookup test validates storage/indexing only. Preserve the
synthetic target identity and walk configuration when connecting a consumer.
