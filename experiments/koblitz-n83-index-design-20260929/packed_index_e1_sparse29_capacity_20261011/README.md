# E-1 sparse29 exact root directory: capacity screen

The 29-bit sparse root directory reduced full-key probes from **7,415,319 to
2,381,131** (67.9%) on the frozen N83 one-target, 29.9-million-state
workload. Its root table grew by **50,331,648 bytes (48 MiB)**. Three completed
same-binary runs preserved 23 exact invariants, including operation counts,
the first-witness lookup sample, native control status, and bounded-stage
outcome. All three remained below the 5,500 MiB RSS cap. The fourth local run
was interrupted when macOS swap pressure reduced system-volume free space to
739 MiB; the three raw runs and [interruption receipt](interruption.json) are
preserved.

This is proposal `Q2026101133` on curve `EC1N83Ckb1h876c2921cb64`, workload
`63dd0929cf33`, and native source SHA-256
`d9cbef74955d120b0c8051da30a3d391a802ebd342d2bb289ccfbcfe1230bfe5`.
The full IC candidate ID remains `null` for this bounded point-decomposition
stage. The exact one-target inputs, 30,977,592 usable factor-base points,
186,612 folded columns, 29,900,000 sampled states, and memory cap are fixed
in [the workload](workload.json) and [stage manifest](stage_manifest.json).
Both arms use the same binary, cached point coordinates, generated partners,
exact 16-byte root keys, singleton tags, and first-witness rule. Only the
SplitMix64 sparse-directory prefix changes from 28 to 29 bits.

## Preserved local panel

| Run | Mode | Target CPU (s) | Target wall (s) | Full-key probes | Root table (bytes) | Peak RSS (bytes) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | sparse28 | 32.273 | 55.291 | 7,415,319 | 1,275,567,104 | 5,491,818,496 |
| 2 | sparse29 | 30.287 | 53.990 | 2,381,131 | 1,325,898,752 | 5,609,488,384 |
| 3 | sparse29 | 32.552 | 111.427 | 2,381,131 | 1,325,898,752 | 5,608,538,112 |
| 4 | sparse28 | interrupted by host disk pressure | — | — | — | — |

The order, source and binary hashes, input laws, target point, and limits were
frozen in [protocol.json](protocol.json) before run 1. The two sparse29 target
CPU values bracket the single completed sparse28 value. Wall time varied
strongly with host contention and swapping. This panel has status
`PARTIAL_HOST_RESOURCE_STOP`; a controlled CPU wall-time ratio remains
unknown. The target clock includes query preparation, batched partner
generation, canonicalization, exact lookup, and native relation checks. The
raw timing records retain exclusive query, generation, check, and residual
costs; index construction and cached-coordinate preparation precede the
target clock.

The seven Rust release tests passed, including exact hit/miss and duplicate
first-witness parity with the hash table for the 29-bit mode. Run
`python3 verify_partial.py` to check the frozen inputs, source and raw hashes,
all completed rows, memory cap, phase sums, 23 exact invariants, and the
interruption record.

For a complete replay, make a fresh isolated copy of this directory without
the `run_*.json`, `run_*.record.json`, panel outputs, `interruption.json`, or
`protocol.json` files. Restore the pinned public crypto source with
`python3 restore_crypto_source.py`, build the native binary with the source and
Cargo-manifest hashes embedded as `NATIVE_S3_SOURCE_SHA256` and
`NATIVE_S3_BUILD_MANIFEST_SHA256`, then run
`python3 run.py --binary ABSOLUTE_BINARY_PATH --freeze-only` before
`python3 run.py --binary ABSOLUTE_BINARY_PATH`. The runner refuses to
overwrite receipts and records the new host's binary hash before timing.
The repository [CPU isolation gate](../../../docs/ISOLATED_BENCHMARKS.md)
governs any controlled wall-time comparison.
