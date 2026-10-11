# E-1: sparse 24-bit root directory

The sparse 24-bit directory retains exact root lookup and first-witness
selection while reducing allocated table memory by 9,437,184 bytes (10.1%)
against the merged sparse 26-bit index. It uses the same hashed prefix,
16-byte root records, singleton tags, unrolled N83 basis conversion, and
early-stop canonicalization. On the frozen one-target stage, all six rows
matched the reference on root and state counts, lookup samples, arithmetic
counts, relation checks, and bounded target status. Median child CPU was
4.593 versus 4.831 seconds in this exploratory local panel; the candidate
used less child CPU in each adjacent pair.

The curve is `EC1N83Ckb1h876c2921cb64`, workload `981ac530e67e`, and
proposal `Q2026101013`. The parent base has 30,977,592 usable points and
186,612 folded columns. Each arm indexes 2,000,000 pair states and 4,000,000
16-byte root records, then scans the same public target. The resource cap is
1,024 MiB RSS and 180 seconds per arm. Every row ended
`state_cap_no_relation` at the specified pair-state cap.

| Directory | Median child CPU | Median index build wall | Median target stage wall | Table bytes | Median peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sparse 26-bit | 4.831 s | 8.813 s | 18.160 s | 93,360,128 | 521,175,040 B |
| Sparse 24-bit | 4.593 s | 6.507 s | 18.034 s | 83,922,944 | 521,715,712 B |

The counterbalanced order was reference/candidate, candidate/reference,
reference/candidate. Child CPU ranges were 4.620–4.874 seconds for the
reference and 4.430–4.742 seconds for the candidate. The local wall
intervals varied enough that these stage times remain exploratory under the
repository's [CPU isolation gate](../../../docs/ISOLATED_BENCHMARKS.md).
The target-stage clock starts after reusable factor-base and index setup.
Its exclusive measured components are query preparation, batched S3 roots,
partner checking, and the recorded residual. Partner checking includes
canonicalization and exact lookup; those nested intervals are not added
again. [`summary.json`](summary.json) retains all phase, CPU, RSS, and
operation-count rows.

The 24-bit bitmap and rank arrays use one quarter of the 26-bit width, and
the number of occupied buckets falls from 3,882,730 to 3,559,167. This
reduces directory memory while increasing singleton-tag rejections from
445,046 to 1,490,860 and full-key target probes from 35,837 to 471,510.
The latter costs are included in every target-stage row.

Five Rust release tests passed, including exact duplicate first-witness
lookup parity and 100,000 N83 basis-conversion comparisons. Independent
wrapper replays of both arms produced the same pair certificate
`2665304bcdb73b73a19a155744d2fcfde7cb8dfde41e7ef05c454b2a47add288`;
[`replay_check.json`](replay_check.json) records their raw-output digests.

Run `python3 run.py` here to check the frozen inputs, build, and execute the
six-arm panel. Set `N83_E1_TARGET_DIR` to a volume with enough Cargo space.
`make_manifest.py` validates all source and input receipts and prepares a
paired manifest for a physical-host isolated replay.
