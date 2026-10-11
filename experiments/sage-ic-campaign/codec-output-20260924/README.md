# Sage NTL output codec optimization

This package contains an incremental Sage patch for
`binary_hardware_codec.pyx:unpack_points`. Apply
[`codec-output.patch`](codec-output.patch) after the batch and hardware
patches from PRs #68, #72, and #73. The unchanged field map, packing code,
native CPU kernel and Metal kernel are inherited from the hardware package.

The decoder caches the standard point homset and allocator once per batch.
It initializes a standard finite-field point directly with the same
normalized coordinates and state used by the measured native batch
constructor. Custom point subclasses still use the original constructor;
infinity still goes through the curve constructor. The public API still
returns ordinary Sage points.

`source/binary_hardware_codec.pyx` is the measured candidate. `baseline/`
holds the exact preceding source. Machine-specific `.so` files are omitted;
their original SHA256 values remain in the frozen intent, install receipt,
and cell receipts.

## Evidence

The first 12-cell pilot is retained in `run-001/`: one small Metal cell
regressed and host scheduler variation was high, so that pilot was held.
`intent-v2.json` froze longer paired samples and fresh seeds before
`run-002/`. The second run passed all frozen correctness, speed and memory
gates. Each cell has 12 balanced rounds and uses full warm plan calls with
point packing, backend work, point reconstruction, exact verification and
output cleanup. Plan creation is separately timed in the cell receipt.

See [RESULT.md](RESULT.md) for the values and limits. Audit the patch and
receipts without Sage:

```sh
python3 experiments/sage-ic-campaign/codec-output-20260924/verify_archive.py
```

For a newly built patched Sage, run `test_codec_output.py` with Sage's Python
interpreter. `benchmark_v2.py` is the historical runner and requires the
recorded incumbent binary; it is not a portable benchmark launcher.
`tests-full.log` preserves the installed CPU/Metal suite. A new host should
run its own suite and timing campaign before selecting a device backend.

The result concerns this one public Frobenius point-map API. A complete
index-calculus speedup remains unknown without a frozen workload and verified
discrete-logarithm recovery.
