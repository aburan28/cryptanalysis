# E-1: canonical roots from cyclic zero gaps

An exact cyclic zero-gap scan reduced full 83-bit rotations from 656,000,000
to 38,261,354 in the frozen N83 target probe, while preserving every
canonical key and Frobenius shift checked. All three adjacent runs had lower
target-stage wall time with the new method; their ratios were 1.074, 1.156,
and 1.118 on this unisolated host. These timings are stage diagnostics; a
CPU wall-time speedup requires a qualifying host-isolation receipt.

For a nonconstant cyclic binary word, its least numeric rotation must begin
at a longest cyclic run of zero bits. The implementation scans set-bit
positions to find those runs, rotates only their starts, and resolves equal
words by the smallest shift. Zero and all-one words return shift zero. The
baseline evaluates all 83 orientations and keeps the first minimum. The
shortcut returns the same `(key, shift)` pair, so the 22-bit hashed bucket
directory and its 18-byte exact records remain unchanged.

## Frozen measurement

The curve is `EC1N83Ckb1h876c2921cb64`; the one-target workload ID is
`981ac530e67e`. The factor base has 30,977,592 actual usable points and
186,612 folded columns. Both arms index 2,000,000 sampled pair states,
retain 4,000,000 root records, use binary search in the same 22-bit bucket
directory, and obey a 1,024 MiB RSS cap. The six-run order was baseline,
zero-gap, zero-gap, baseline, baseline, zero-gap.

| Measure | Full scan | Zero-gap scan |
| --- | ---: | ---: |
| Index full rotations | 328,000,000 | 19,127,078 |
| Target full rotations | 656,000,000 | 38,261,354 |
| Median index build | 2.130 s | 1.980 s |
| Median target stage | 7.204 s | 6.511 s |
| Median target conversion and canonicalization | 2.216 s | 1.557 s |
| Exact target key comparisons | 9,324,648 | 9,324,648 |
| Allocated root table | 88,777,220 B | 88,777,220 B |

All six runs ended `state_cap_no_relation` at the declared cap. The bounded
target interval includes query preparation, batched S3 evaluation, root
conversion and canonicalization, exact lookup, and native relation checks.
The raw phase and RSS rows are in [`summary.json`](summary.json) and the six
`run_*.json` files. The host had no isolation receipt, so the aggregate CPU
speedup remains unknown under the repository measurement rule.

The canonicalization unit test compared every word at lengths 3, 5, 7, and
11, plus 100,000 fixed-seed 83-bit words, against the full scan. The other
three root-index and S3 tests passed. Across the six full runs, source and
input identifiers, indexed states, distinct keys, first-witness lookup
samples, target outcomes, exact lookup counts, and all noncanonical
field/group operation counts agreed.

## Replay

Run `python3 run.py` from this directory. The runner archives frozen crypto
commit `904f0f844f3c1e69e8d22ae5e60ecd56e6648611` from the local
`/Volumes/SSD990/crypto` checkout, verifies source and input digests,
builds with `cargo --release --locked`, and writes each raw row before the
comparison. [`protocol.json`](protocol.json),
[`stage_manifest.json`](stage_manifest.json), [`workload.json`](workload.json),
and [`build_receipt.json`](build_receipt.json) bind the exact experiment.
