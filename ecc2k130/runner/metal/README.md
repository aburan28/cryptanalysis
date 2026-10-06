# Native macOS / Metal table access

The public pair tables are portable little-endian data. Native Metal support
now covers device discovery, table-size planning, downloading, and bounded
GPU lookup validation. The existing rho engines are CUDA/CPU implementations;
this directory does not yet implement a complete Metal rho walk.

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

## Complete rho execution still requires a port

The CUDA client cannot run directly through Metal. A native walk would need
Metal Shading Language versions of the GF(2^131) multiplication/reduction,
squaring, batched inversion and point update, followed by branch/cycle state,
distinguished-point output and replay/checkpoint integration. CUDA/PTX CLMAD
instructions cannot be carried over as Metal instructions.

For a resident table consumer, read the data into shared Metal buffers while
avoiding an unnecessary second 20 GB host copy. Check allocation results and
the working set. Devices with smaller per-buffer limits need record-aligned
segments and a shader capable of selecting the correct segment.

Using precomputed pair sums to eliminate an intermediate addition also needs
the intermediate branch-selection method discussed in the research notes.
The Metal lookup test does not supply that method. Preserve the synthetic
target identity and walk configuration when connecting a consumer.
