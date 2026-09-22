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

## Run continuously and upload distinguished points

`continuous_walk.py` runs the same synthetic recurrence in bounded chunks and
continues until it receives `SIGINT` or `SIGTERM`. After every chunk it uploads
the complete 80-byte DP records, a state checkpoint, and a manifest. DP and
state objects have content-addressed names; `latest.json` advances only after
all three immutable objects are present. Restarting the same command downloads
that state before launching more GPU work.

Build once, configure the AWS CLI through its normal environment, profile, or
instance role, and give the process a unique run ID:

```sh
make -C /Volumes/SSD990/cryptanalysis/ecc2k130/metal
export ECC_BUCKET=ecc2k130-status-590183823895
export AWS_DEFAULT_REGION=us-west-2

caffeinate -dimsu -- python3 \
  /Volumes/SSD990/cryptanalysis/ecc2k130/metal/continuous_walk.py \
  --work /Volumes/SSD990/ecc2k130-metal/m4pro-01 \
  --artifact-dir /Volumes/SSD990/cryptanalysis/ecc2k130/research/step_table/pair128-24gb-20260921 \
  --run-id m4pro-01 \
  --branches 128 --lanes 128 --cycles 64 --chunk-launches 256 \
  --dp-weight 32 --progress-every 16
```

The default prefix for that command is
`campaigns/ecc2k130-synthetic-metal-h128-v1/m4pro-01`. Supply `--prefix` to
place the isolated run elsewhere. The AWS identity needs `s3:ListBucket`,
`s3:GetObject`, and `s3:PutObject` for that prefix. Credentials are read by the
AWS CLI and are not written into the campaign, checkpoint, logs, or source tree.

Use the same command after a terminal closes, a Mac reboots, or the process is
stopped. A single Ctrl-C lets the active bounded GPU chunk finish and publishes
it before exiting. If S3 is unavailable, the supervisor pauses GPU work and
retries with backoff; Ctrl-C leaves the complete unacknowledged chunk under
`WORK/pending/`, and the next invocation uploads it before doing more work.
A conditional S3 lease rejects a second writer using the same prefix.

The prefix contains:

```text
campaign.json                         immutable run and walk identity
dp/chunk-...-SHA256-BYTES.bin         immutable 80-byte DP-record delta
checkpoints/state-...-SHA256.bin      immutable lane checkpoint
manifests/chunk-...-SHA256.json       immutable DP/state binding
latest.json                           recovery pointer, written last
slots/slot-00000.json                 expiring single-writer lease
```

Inspect the current recovery boundary without downloading the corpus:

```sh
aws s3 cp \
  s3://ecc2k130-status-590183823895/campaigns/ecc2k130-synthetic-metal-h128-v1/m4pro-01/latest.json -
```

Before using S3, a two-chunk directory-backed rehearsal exercises the same
publication and resume code without credentials:

```sh
python3 /Volumes/SSD990/cryptanalysis/ecc2k130/metal/continuous_walk.py \
  --work /private/tmp/ecc2k-metal-rehearsal \
  --local-store /private/tmp/ecc2k-metal-object-store \
  --artifact-dir /Volumes/SSD990/cryptanalysis/ecc2k130/research/step_table/pair128-24gb-20260921 \
  --run-id rehearsal --lanes 8 --cycles 8 --chunk-launches 2 \
  --dp-weight 64 --verify-lanes 2 --progress-every 1 --max-chunks 2
```

Weight 64 deliberately produces frequent records for the rehearsal. Its
objects are a different walk identity and cannot be mixed with weight-32
records. `--verify-lanes N` independently replays selected resumed lanes in
every chunk and is optional during a long run. Per-launch and per-chunk output
continues to report GPU iterations per second.

For multiple Macs, choose one fixed shard count and assign each process a
different zero-based shard index as well as a different run ID and work path.
For example, four processes use `--shard-count 4` with `--shard-index 0`, `1`,
`2`, and `3`. Initial lane seeds are `base + shard-index + lane * shard-count`,
then advance by `lanes * shard-count`. Each job owns one residue class modulo
the shard count, so the streams remain disjoint even when the Macs use different
lane counts. Shard geometry is bound into each checkpoint identity and cannot
change on resume.
[The two-shard M4 Pro receipt](evidence/continuous-shard-control.json) records
65 DP reports with zero seed overlap; two lanes in each bounded shard matched
independent replay. It uses the directory-backed store and does not claim an
S3 transport check.

This is a **synthetic unknown-scalar control** using Q=[65537]P. It does not
join the production Certicom campaign and its checkpoints are a new format.
The current implementation is a correctness path, not an optimized throughput
claim.

## Exact intermediate-selector pair benchmark

The exact two-step oracle now computes the first ordinary update, evaluates the
second selector and cycle history on that intermediate point, then checks that
`R + pair[first,second]` equals the two ordinary updates byte-for-byte. An
intermediate distinguished point is not fusible: the oracle falls back so that
the report cannot be skipped. This establishes the algorithmic boundary—the
exact selector still requires the first complete point addition.

`metal-fused-benchmark` maps the full 20,244,542,976-byte h128 payload into one
shared Metal buffer and compares matched paths:

* baseline: two selectors and two small-direction point additions;
* pair candidate: the same selectors, the first direction addition, one random
  pair lookup, and a second addition from the original point.

Both paths therefore charge two runtime additions for two logical updates. The
benchmark uses 4,096 independently replayed inputs per case seed and repeats
each workload 64 times inside a command buffer so timed samples are about 15 ms
instead of sub-millisecond events.

| Case seed | Exact cases | Paired samples | Fused / baseline median time |
| --- | ---: | ---: | ---: |
| 20260921 | 4,096 | 9 | 1.035139 |
| 20261021 | 4,096 | 9 | 1.035391 |
| Combined | 8,192 | 18 | **1.035749** |

All 18 fused samples were slower; the observed range was 1.031817–1.038018.
The pair path is rejected for collection: it does not reduce group operations
and is about 3.5% slower in this matched warm microbenchmark. This is not a
complete-walk timing or an asymptotic result. The benchmark-only S3 namespace
sets `collectionEnabled: false`, and no fused DP campaign is launched.

Reproduce with:

```sh
python3 metal/prepare_fused_benchmark.py \
  --out /private/tmp/fused-input --artifact-dir research/step_table/pair128-24gb-20260921 \
  --cases 4096 --seed 20260921 --repeats 9 --warmups 2 --inner-iterations 64
make -C metal
python3 metal/run_fused_benchmark.py \
  --input /private/tmp/fused-input \
  --pairs research/step_table/pair128-24gb-20260921/pairs.bin \
  --out metal/evidence/fused-selector-reproduction.json
```

The checked-in receipts are
[seed 20260921](evidence/fused-selector-seed1.json),
[seed 20261021](evidence/fused-selector-seed2.json), and the
[combined decision](evidence/fused-selector-summary.json).
The immutable [public S3 manifest](https://ecc2k130-status-590183823895.s3.us-west-2.amazonaws.com/public/ecc2k130/synthetic-fused-selector/v1/840ec3787f2e0d06c82fcee32b3b2ec574752213d44499044a5223b07b6f26c4/manifest.json)
publishes those receipts, the exact sources, and the arm64 benchmark binary in
a separate benchmark-only namespace.

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
