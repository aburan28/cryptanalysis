# E-1: 24-bit sparse root directory on the frozen N83 target stage

A 24-bit bitmap-rank directory reduces packed root-table allocation from
101,360,128 to 91,922,944 bytes against the 26-bit sparse directory. Both
arms preserve exact 83-bit key lookup and the first inserted witness for
duplicate keys. The shorter prefix raises full-key probes from 35,837 to
471,510 on the frozen target, so the 24-bit variant remains a measured memory
tradeoff rather than the preferred timing candidate.

## Frozen comparison

The curve is `EC1N83Ckb1h876c2921cb64`, workload ID `981ac530e67e`, and
proposal ID `Q2026101004`. The complete IC candidate and run IDs are null.
The parent factor base has 30,977,592 usable points and 186,612 folded
columns. Both arms index the same 2,000,000 sampled pair states and 4,000,000
exact 18-byte root records, then query one frozen public point. The comparison
changes only the sparse bitmap width. Both arms use zero-gap canonicalization,
singleton tags, and exact-key comparison. The target clock starts after index
construction and includes query preparation, batched S3 roots, partner
canonicalization, root lookup, and relation checks.

| Arm | Median target stage | Median exact lookup | Median index build | Full-key probes | Table bytes | Median peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sparse 26-bit | 30.816 s | 6.368 s | 14.169 s | 35,837 | 101,360,128 | 713,097,216 |
| Sparse 24-bit | 29.932 s | 6.693 s | 11.387 s | 471,510 | 91,922,944 | 696,057,856 |

The six-run order was sparse26, sparse24, sparse24, sparse26, sparse26,
sparse24. These CPU times are exploratory because the local host has no
isolation receipt and experienced large runtime variation. In particular,
the median target-stage difference does not establish a wall-time speedup.
The raw rows, phase measurements, statuses, and ranges are in
[`summary.json`](summary.json) and the six `run_*.json` files. Every run
recorded `state_cap_no_relation` at the declared cap. The table and RSS
figures satisfy the 1,024 MiB limit.

The 24-bit directory uses one bit per possible bucket, a rank prefix per
64-bit bitmap word, and one 32-bit offset per occupied bucket plus a sentinel.
The saved bitmap and rank bytes are partly offset by more occupied buckets.
Sorting by exact key and descriptor preserves the first-inserted witness.
Four Rust tests passed for exact hits, misses, duplicate first witnesses,
zero-gap canonicalization, and batched S3 roots. The full replay checks exact
lookup samples, state and root counts, target status, and noncanonical
arithmetic counts across both arms. The independent wrapper replay verified
both frozen fixtures and emitted the same pair certificate
`4d6ff730d8cb35b5ba851be41b047850300253857e3a877bc360a52f325da947`;
its receipt is in [`replay_check.json`](replay_check.json).

## Reproduce

From this directory, `python3 run.py` verifies the frozen crypto source
snapshot, builds with `cargo --release --locked`, and preserves all six raw
rows. Set `N83_E1_TARGET_DIR` to choose an output directory. The source
snapshot is generated from crypto commit
`904f0f844f3c1e69e8d22ae5e60ecd56e6648611` if absent; set `CRYPTO_REPO`
to the corresponding checkout. The frozen representative and bridge files
are inherited from `adaptive_all_orientations_20261004/inputs`.

For an isolated replay, build this experiment from the same source snapshot,
run `make_manifest.py` with the verified host CPU, NUMA, and cgroup values,
then pass the resulting manifest to `scripts/isolated_bench.py probe` and
`run`. The repository's [CPU isolation contract](../../../docs/ISOLATED_BENCHMARKS.md)
defines the promotion gate. The 26-bit arm remains the preferred candidate
for that controlled timing comparison. A complete single-target IC online
metric also requires target recovery and a paired rho solve under the
repository measurement contract.
