# E-1 sparse26 cached-coordinate N83 root directory

Changing the sparse root-directory hash prefix from 24 to 26 bits reduced
exact full-key probes on the frozen N83 one-target stage from **471,510 to
35,837**. Target process CPU was lower in all three adjacent matched pairs;
the six-run exploratory median was **1.655 s for sparse24** and **1.489 s
for sparse26**. Both arms preserved the same four million indexed roots,
first-witness sample, operation counts outside the directory, and
`state_cap_no_relation` status.

This is proposal `Q2026101130`, curve `EC1N83Ckb1h876c2921cb64`, and
workload `981ac530e67e`: one public target point, 2,000,000 sampled pair
states, 30,977,592 usable factor-base points, 186,612 folded columns, and
one orientation per target state. The full IC candidate ID remains `null`
while this is a bounded point-decomposition stage. The source SHA-256 is
`8a57c4d994c47344d7093c1103bfadc80e48f666e49f346bf729b80404132b05`.

## Paired exploratory panel

| Measurement | Sparse24 cached x/y | Sparse26 cached x/y |
| --- | ---: | ---: |
| Target process CPU median | 1.655 s | 1.489 s |
| Target-stage wall median | 17.159 s | 16.137 s |
| Target partner-check wall median | 11.876 s | 9.558 s |
| Full-key probes | 471,510 | 35,837 |
| Root-table allocation | 83,922,944 bytes | 93,360,128 bytes |
| Peak RSS median | 614,662,144 bytes | 630,521,856 bytes |
| Index build process CPU median | 1.372 s | 1.318 s |
| Target field multiplications | 19,998,533 | 19,998,533 |
| Target canonical rotation steps | 11,325,200 | 11,325,200 |

The paired target process CPU times, in run order, were 1.543/1.478 s,
1.655/1.489 s, and 1.749/1.654 s (sparse24/sparse26). The host ran other
builds during this panel, so wall and CPU ratios are exploratory. The raw
[summary](summary.json) preserves every row, phase, memory value, status,
and range. Index construction and cached x/y root lifts occur before the
target clock; all target-dependent preparation, partner generation, and
partner checks are charged to the target stage. The exclusive phase sum and
its residual are retained per run.

## Exactness and replay

The [full audit](audit_sparse26_cachedxy.json) compared every one of
4,000,000 generated partner pairs after Frobenius rotation against the
original S3 evaluator on the original shifted roots. All 8,000,000 partner
roots agreed. It used the same source and frozen workload; peak RSS was
631,635,968 bytes under the 1,024 MiB cap. Seven source-level Rust tests
passed, covering exact keys, duplicate first witnesses, all GF(32) input
pairs, and Frobenius-shifted point partners. Sparse26 uses the same
parameterized sparse-directory and first-witness routine as sparse24; the
six N83 runs agree on the indexed first-witness lookup sample.

[verify.py](verify.py) checks source and input hashes, the canonical workload
ID, each raw run digest, exact invariant agreement across both arms, phase
sums, the audit digest and counts, and the host-isolation field. Run
`python3 verify.py` from this directory. A fresh checkout also needs the
public [`crypto` source commit](https://github.com/aburan28/crypto/commit/904f0f844f3c1e69e8d22ae5e60ecd56e6648611): clone that repository,
set `CRYPTO_REPO` to its checkout, and run `python3 restore_crypto_source.py`
first. The restore script archives the pinned commit, checks all source-tree
digests against `protocol.json`, and fills the missing linked snapshot only
after those checks pass. The verifier and isolated manifest builder invoke it
automatically when needed. To rebuild and rerun the paired panel, set
`N83_E1_TARGET_DIR` to a writable build path and run `python3 run.py` after
restoring the snapshot; it freezes inputs before compilation and preserves
six raw run records. [audit.py](audit.py) replays the separate full audit
against the built binary using [audit_protocol.json](audit_protocol.json).

The same-point physical-host replay remains the gate for a controlled
wall-time comparison. The 29.9-million-state capacity result uses its own
workload `63dd0929cf33` in the [capacity receipt](../packed_index_e1_capacity_20261011/README.md);
this 2-million-state comparison preserves the original workload ID.
