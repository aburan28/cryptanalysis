# E-1: dense 26-bit directory with 16-byte root records

The direct 26-bit directory preserves exact lookup and first-witness behavior
on the frozen N83 target stage. It builds the index faster in this local panel,
but uses substantially more memory and does not give a convincing online
lookup improvement. The sparse 26-bit directory remains the physical-host
replay priority.

The curve is `EC1N83Ckb1h876c2921cb64`, workload `981ac530e67e`, and
proposal `Q2026101006`. The parent factor base has 30,977,592 usable points
and 186,612 folded columns. Both arms index 2,000,000 sampled pair states
and 4,000,000 exact root records, then query the same single public point.
The 1,024 MiB RSS cap and all input, query, and target parameters are shared.
The candidate and run IDs remain null because this is a bounded decomposition
stage, not a complete IC pipeline.

The sparse arm uses a bitmap, per-word rank, and one offset per occupied
bucket. The dense arm stores one direct 32-bit offset per 26-bit bucket. It
sorts records in place during construction, whereas the sparse arm uses a
keyed temporary array. Both use 16-byte key/descriptor records, exact-key
binary search, zero-gap canonicalization, and singleton tags.

| Directory | Median target stage | Median exact lookup | Median index build | Table bytes | Median peak RSS | Full-key probes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sparse26 | 67.028 s | 13.901 s | 35.664 s | 93,360,128 | 608,485,376 | 35,837 |
| Dense26 | 65.326 s | 15.959 s | 21.479 s | 332,435,460 | 770,310,144 | 35,837 |

The six-run order was sparse/dense, dense/sparse, sparse/dense. The dense
target-stage range was 46.867–73.799 s; the sparse range was 63.905–69.909 s.
This local host lacked the repository's physical CPU isolation receipt, so
these timings are exploratory. Index construction is target independent and
is outside the target-stage interval. The table bytes are allocator capacity
for records and directory structures; peak RSS includes the whole process.
All six runs recorded `state_cap_no_relation` within the RSS limit. The
`summary.json` file retains every phase median, range, and raw row.

Four Rust tests passed, including exact hits, misses, duplicate first
witnesses, maximum descriptor values, canonicalization, and batched S3
roots. All six runs agreed on the frozen lookup sample, stage result,
operation counts, 3,767,807 tagged singleton buckets, 445,046 tag
rejections, and 35,837 full-key probes. The native output now reports the
actual record width for each packed variant.

Run `python3 run.py` in this directory to rebuild and replay the panel.
It verifies the frozen crypto snapshot and parent inputs, then preserves
every raw run and host receipt. Set `N83_E1_TARGET_DIR` for the Cargo output
directory. The repository's [CPU isolation contract](../../../docs/ISOLATED_BENCHMARKS.md)
governs any promoted wall-time comparison.
