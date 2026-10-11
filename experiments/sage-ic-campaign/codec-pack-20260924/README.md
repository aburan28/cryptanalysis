# Sage NTL point-packing optimization

This package contains [`codec-pack.patch`](codec-pack.patch), an incremental
Sage 10.10.rc0 patch for `binary_hardware_codec.pyx:pack_points`. Apply it
after the batch, native Frobenius, hardware, and output codec patches in
PRs #68, #72, #73, and #74. It does not change the table map, Metal kernel,
output decoder, or backend selection.

For the exact standard finite-field point class, the packer reads the
point's existing curve and coordinate state directly. It keeps the old
`xy()` path when coordinates are not normalized. Custom point subclasses
retain the public `curve()` and `xy()` calls, including their hooks.
Invalid inputs and infinity flags retain the same behavior. The public
`FrobeniusPlan.apply` API is unchanged.

`run-001/` profiles exclusive packing, table, output, verification, and
cleanup costs before any packing edit. Packing used 19–40% of complete
CPU/Metal calls in six local cells. The first edited candidate in
`run-002/` passed correctness but failed the frozen no-regression timing
gate in two cells. Its source and receipts are preserved. The revised
candidate in `source/` passed the separate frozen `run-003/` gate on new
seeds and longer samples. See [RESULT.md](RESULT.md).

The archive includes exact baseline and candidate source, build receipts,
paired timing receipts, and focused plus installed-suite test logs.
Machine-specific binary files are omitted; their original hashes remain
in the intent, install and timing receipts. Audit the patch and records
without Sage:

```sh
python3 experiments/sage-ic-campaign/codec-pack-20260924/verify_archive.py
```

For a newly built patched Sage, run `test_pack.py` with Sage's Python
interpreter and the installed CPU/Metal hardware tests described in the
hardware package. The historical timing runner requires its saved prior
binary and is not a portable launcher.

These are warm complete point-map calls, not a complete index-calculus
pipeline. A discrete-logarithm speedup remains unknown until a frozen
workload is recovered and verified with full phase accounting.
