# Vectorized Sage binary Frobenius table construction

This directory contains an incremental patch for
`src/sage/schemes/elliptic_curves/binary_hardware.py`. Its exact parent is the
hardware source in `experiments/sage-binary-hardware/source/binary_hardware.py`
on PR #75. It does not depend on the draft automatic CPU-routing change in
PR #76. The patch changes only `FrobeniusPlan._make_table`.

The old code fills 256 Python integers per input byte, then splits each integer
into machine words. The new code writes each basis image into a NumPy `uint32`
row and constructs the 256 entries with eight slice/XOR operations. Unused
high basis bits remain zero. The resulting table is contiguous and read-only,
with the same byte/digit/word layout as the original CPU and Metal kernels.

To audit the patch and archived measurements without Sage, run:

```sh
python3 experiments/sage-ic-campaign/table-build-20260924/verify_archive.py
```

For an already built local Sage checkout at the PR #75 source, apply
`vector-table.patch` from the Sage checkout root. Build or install that Python
source through the checkout's normal development workflow. The local run used
the installed source hash recorded in `install-independent-001/install.json`.

`run-004` is the held first independent paired run. Its alternate-modulus cold
cell missed the frozen per-cell gate. `run-005` repeats the unchanged source
with new seeds and 48 balanced plan pairs per cell. `run-006` is a separate
complete-call Metal diagnostic. Full data, scripts, intents, and exactness
logs are included. See [RESULT.md](RESULT.md) for measurements and limits.
