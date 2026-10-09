# E-1: counting buckets for the N83 packed root index

A 22-bit hashed bucket directory reduced exact-key comparisons in the frozen
N83 target probe from 23,387,956 to 9,324,648, a 2.51× reduction. Counting
scatter followed by a short sort inside each bucket built the exact packed
root index without the previous global hash-prefix comparator sort. The
retained 22-bit table used 84.7 MiB, while the measured build peak was
418.6 MiB of process RSS because scatter holds both record vectors briefly.

## Method

The three modes use the same 18-byte record: an exact 83-bit canonical root
and a 7-byte witness descriptor. `packed_hashprefix` globally sorts records
by a 20-bit mixed-key prefix, then by the exact record, and stores 64-bit
directory offsets. `packed_bucket20` and `packed_bucket22` count records by
20- and 22-bit mixed-key prefixes, scatter once, sort each bucket by the
exact record, and store 32-bit offsets. The runner checks that the complete
record count fits the 32-bit directory. Each lookup compares the full key
and returns the first inserted witness for that key.

The [protocol](protocol.json) freezes curve `EC1N83Ckb1h876c2921cb64`,
30,977,592 usable base points before orbit folding, 186,612 folded columns,
one public target point, 2,000,000 sampled pair states, one target
orientation per state, a 1,024 MiB RSS cap, and workload `981ac530e67e`.
The nine-run order rotates the modes in three blocks: `A B C | B C A | C A B`,
where A is the global sort, B is the 20-bit bucket sort, and C is the 22-bit
bucket sort. Target-independent setup and index construction are outside the
reported target probe interval. The [runner](run.py) archives dependency
commit `904f0f844f3c1e69e8d22ae5e60ecd56e6648611`, verifies its source
tree hash, and records source, binary, input, and raw-result hashes.

## Result

| Metric, median of three runs per mode | A: global 20-bit | B: bucket 20-bit | C: bucket 22-bit |
| --- | ---: | ---: | ---: |
| Exact-key comparisons in target probe | 23,387,956 | 23,387,956 | 9,324,648 |
| Retained root-table allocation | 76.7 MiB | 72.7 MiB | 84.7 MiB |
| Peak process RSS | 330.7 MiB | 393.6 MiB | 418.6 MiB |
| Index build | 21.315 s | 19.444 s | 14.792 s |
| Target probe | 58.965 s | 54.286 s | 38.925 s |

The target-probe ranges were 56.325–82.554 s (A), 20.894–83.694 s (B),
and 36.786–46.523 s (C). The index-build ranges were 16.851–36.751 s
(A), 10.771–22.387 s (B), and 11.071–14.953 s (C). Within the three
rotated blocks, A/C target-probe time ratios were 2.121, 1.531, and 1.267;
B/C ratios were 2.150, 0.568, and 1.167. These CPU measurements are
exploratory because the host had no isolation receipt; the exact comparison
count and allocation are deterministic for the frozen input.

All nine runs had status `state_cap_no_relation` after the frozen state cap,
with zero table hits. They agreed on 4,000,000 distinct root keys, target
states, S3 operation counts, first-witness samples, and generator-target
correctness controls. The [summary](summary.json) retains every paired row
and range; each raw JSON file has a companion run receipt with its SHA-256.
The three Rust unit tests passed, including 50,000 generated keys per hashed
directory mode with hits, misses, and duplicate witnesses. Proposal
`Q2026100802` keeps `candidate_id` and `run_id` null for this stage study.

To replay, copy this directory beside the prior E-1 directories and frozen
parent inputs, then run `python3 run.py` in the copy. Set `CRYPTO_REPO` to a
local checkout containing the frozen dependency commit if needed. Running in
this directory would replace the published fixed-name receipts. The next
construction test is an in-place bucket permutation that avoids the second
record vector during scatter, with peak RSS and build time measured at a
larger index cap.
