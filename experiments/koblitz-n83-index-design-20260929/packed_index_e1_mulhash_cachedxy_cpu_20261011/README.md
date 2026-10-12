# E-1 sparse26 root-directory hash screen

The one-multiply hash preserved the exact N83 root-index behavior and passed a
full comparison of 4,000,000 target partner pairs and 8,000,000 roots with the
original S3 evaluator. On the frozen 2,000,000-state, one-target workload, it
made 36,244 exact full-key probes versus 35,837 for the SplitMix64 reference.
In the same-binary exploratory panel, its median target-process CPU was
1.571 s versus 1.470 s for the reference. This result retains the hash as a
measured screen rather than a promoted speedup.

The proposal is `Q2026101131`, curve `EC1N83Ckb1h876c2921cb64`, workload
`981ac530e67e`. It uses 30,977,592 usable factor-base points, 186,612 folded
columns, one frozen public subgroup target, one orientation per sampled state,
and a 1,024 MiB RSS cap. The full IC candidate ID remains `null` for this
bounded point-decomposition stage. Both arms use the same cached x/y roots,
point-partner generator, 16-byte exact-key records, sparse 26-bit bitmap-rank
directory, singleton tags, first-witness rule, and compiled binary. The
candidate changes only the directory hash to a folded 64-bit value multiplied
by `0x9e3779b97f4a7c15`; its top 26 bits select the bucket.

## Paired exploratory panel

| Measurement | SplitMix64 | One multiply |
| --- | ---: | ---: |
| Target-process CPU median | 1.470 s | 1.571 s |
| Target-stage wall median | 5.301 s | 7.945 s |
| Full-key probes | 35,837 | 36,244 |
| Occupied directory entries | 3,882,730 | 3,883,039 |
| Root-table allocation | 93,360,128 bytes | 93,360,128 bytes |
| Peak RSS median | 630,554,624 bytes | 630,587,392 bytes |
| Index-build process CPU median | 1.325 s | 1.300 s |
| Target field multiplications | 19,998,533 | 19,998,533 |
| Target canonical rotation steps | 11,325,200 | 11,325,200 |

The three adjacent target-process CPU pairs (reference/candidate) were
1.446/1.547 s, 1.645/1.573 s, and 1.470/1.571 s. The host was not isolated;
the wall and CPU ratios are exploratory. [summary.json](summary.json) retains
the six raw rows, phase sums, memory, and status. Both arms processed the full
state cap and recorded `state_cap_no_relation`. The target clock begins after
index construction and cached-coordinate preparation. The exclusive target
query, partner generation, partner check, and residual phases sum to each
charged target-stage interval. Setup and index costs are separate.

## Exactness and replay

[audit_mulhash_cachedxy.json](audit_mulhash_cachedxy.json) compares every
generated partner pair after Frobenius rotation with S3 on the original
shifted roots. All 8,000,000 roots agreed; audit peak RSS was 631,848,960
bytes. All seven Rust tests passed, including exact key lookup and duplicate
first-witness controls. The paired runs agree on the indexed first-witness
sample, state and root counts, target status, and operation counts.

Run `python3 verify.py` from this directory to check the frozen source and
input hashes, workload ID, raw-run digests, phase sums, audit counts, and
exact invariants. A fresh checkout requires the public
[`crypto` source commit](https://github.com/aburan28/crypto/commit/904f0f844f3c1e69e8d22ae5e60ecd56e6648611): clone that repository,
set `CRYPTO_REPO` to its checkout, and run
`python3 restore_crypto_source.py`. The restore script checks the pinned
source-tree digests before populating the ignored local snapshot. The verifier
also invokes it when needed.

To rebuild and rerun in an isolated copy, set `N83_E1_TARGET_DIR` to a writable
build path and run `python3 run.py`. This freezes the input receipts before
compilation and records six raw executions. Run `python3 audit.py --binary
<path-to-built-native_packed_index>` for the full partner-root audit using
the checked [audit protocol](audit_protocol.json). The repository CPU
isolation gate still applies before promoting a physical-host wall-time
comparison.
