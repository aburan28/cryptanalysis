# E-1: compact 15- and 16-byte root records on the frozen N83 target stage

The 16-byte record reduces the sparse 26-bit packed table from 101,360,128
to 93,360,128 bytes while preserving exact 83-bit keys, duplicate
first-witness behavior, and every frozen target result. The 15-byte record
reduces table allocation to 89,360,128 bytes. This comparison identifies the
16-byte arm for an isolated timing replay; the local CPU timing is exploratory.

## Frozen comparison

The curve is `EC1N83Ckb1h876c2921cb64`, workload ID `981ac530e67e`, and
proposal ID `Q2026101005`. Complete IC candidate and run IDs are null. The
parent factor base has 30,977,592 usable points and 186,612 folded columns.
All arms index the same 2,000,000 sampled pair states and 4,000,000 root
records, then query one frozen public point. They share a 26-bit bitmap-rank
directory, zero-gap canonicalization, singleton tags, binary search, and
full-key comparison. Only the exact record width changes. The 15-byte
record stores an 11-byte root key and a 4-byte descriptor, enough for a
24-bit state offset, one selector bit, and a 7-bit Frobenius shift. The
16-byte record uses a 5-byte descriptor and a power-of-two record stride.

| Record | Median target stage | Median exact lookup | Median index build | Full-key probes | Table bytes | Median peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 18 bytes | 32.756 s | 7.411 s | 10.090 s | 35,837 | 101,360,128 | 726,532,096 |
| 15 bytes | 34.568 s | 7.434 s | 10.112 s | 35,837 | 89,360,128 | 626,458,624 |
| 16 bytes | 29.515 s | 6.317 s | 11.351 s | 35,837 | 93,360,128 | 630,456,320 |

The nine-run order was 18/15/16, 16/18/15, 15/16/18. The clock starts after
index construction and includes target query preparation, batched S3 roots,
partner canonicalization, exact lookup, and relation checks. Local timing
varied strongly with host load. The 16-byte median is a diagnostic, not a
controlled wall-time speedup; the repository CPU isolation gate must be met
before promotion. The peak-RSS reduction exceeds the table allocation
change, so it is reported as an observed total rather than attributed solely
to the record width. The raw phase costs and ranges are in
[`summary.json`](summary.json) and the nine `run_*.json` files. Every run
recorded `state_cap_no_relation` at the declared cap and remained below the
1,024 MiB RSS limit.

Four Rust tests passed for exact hits, misses, duplicate first witnesses,
maximum descriptor encodings, zero-gap canonicalization, and batched S3
roots. All nine full runs matched frozen lookup samples, state and root
counts, target status, arithmetic counts, and full-key probe counts. Fresh
wrapper replays of all three arms verified their frozen fixtures and emitted
the same pair certificate
`4d6ff730d8cb35b5ba851be41b047850300253857e3a877bc360a52f325da947`.
The wrapper receipt is [`replay_check.json`](replay_check.json).

## Reproduce and promote

From this directory, `python3 run.py` verifies the frozen crypto source
snapshot, builds with `cargo --release --locked`, and preserves all nine raw
rows. Set `N83_E1_TARGET_DIR` to choose an output directory. If the snapshot
is absent, set `CRYPTO_REPO` to a checkout containing commit
`904f0f844f3c1e69e8d22ae5e60ecd56e6648611`. The representative and
bridge inputs come from `adaptive_all_orientations_20261004/inputs`.

On a qualifying host, use `make_manifest.py` with the verified CPU, NUMA,
and cgroup values; it pairs the 18-byte reference with the 16-byte arm.
Then run `scripts/isolated_bench.py probe` and `run` using that manifest.
The repository's [CPU isolation contract](../../../docs/ISOLATED_BENCHMARKS.md)
defines the gate. A complete single-target IC online comparison also
requires target recovery and paired rho under the repository measurement
contract.
