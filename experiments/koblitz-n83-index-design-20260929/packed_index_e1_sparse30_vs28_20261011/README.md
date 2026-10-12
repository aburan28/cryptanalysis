# N83 E-1 sparse30 compact-rank directory against sparse28

The sparse30 compact-rank directory reduces exact full-key target probes from
7,415,319 to 819,487 (88.95%) at the 29,900,000-pair-state cap on the frozen
N83 single-target stage. Its root table grows by 117,506,048 bytes (112.0625
MiB). The full-capacity candidate and the merged sparse28 reference agree on
all 23 frozen semantic fields, including the first-witness pair certificate
`083d0561e2d3f52763840c10d4c540550b71446daaf09f3d1ef50a53def81a51`.
The directory gain now has a direct eight-pair Tier 1 CPU comparison.

This is proposal `Q2026101135`, curve `EC1N83Ckb1h876c2921cb64`, and workload
`63dd0929cf33`. The compared result is the target-dependent bounded native
PDP stage, with target-independent index and cached point coordinates ready
before the timer. The stage ends at the 29,900,000-state cap and records
`state_cap_no_relation`. The complete IC candidate ID remains `null` while
relation collection, matrix work, target descent, and recovery have not been
specified for this variant.

| Frozen observation | Sparse28 reference | Sparse30 compact-rank |
| --- | ---: | ---: |
| Indexed pair states | 29,900,000 | 29,900,000 |
| Full-key target probes | 7,415,319 | 819,487 |
| Root table bytes | 1,275,567,104 | 1,393,073,152 |
| Exact semantic fields matched | 23 | 23 |

The reference raw result is copied unchanged from the merged sparse28
experiment. Its source hash is
`9969359d0605bdc8ef1a5f8ef2e3d204055ae391e14ff6f5bec3c0bdcca1463f`.
The sparse30 source hash is
`c563a232b0d456250b59d3e239fc7039957196a5fe7ced1d36626998bb1b1c60`.
The Tier 1 replay builds that sparse30 source once and runs both modes from the
same release binary, so its paired timing has one code snapshot. The original
sparse30 full-capacity screen and its interrupted sparse29 control are retained
as input evidence; `verify_screen.py` checks those source-bound records.

`comparison_protocol.json` binds the direct sparse28/sparse30 comparison and
`benchmark_stage.py` checks each arm against its frozen raw result, the input
hash, the source hash, the stage cap, the memory cap, and the exact certificate.
`tier1_protocol.json` binds the comparison protocol by SHA-256 and fixes eight
alternating pairs with a 300-second cap per arm. The Tier 1 runner records
allocation, affinity, cgroup throttle and OOM counters, every raw arm and
failure, phase timing, and paired bootstrap uncertainty. A stage speedup is
eligible only when all exact/noise gates pass and the lower 95% paired
bootstrap bound exceeds one.

The workflow `.github/workflows/n83-e1-sparse30-vs28-tier1.yml` runs on a fresh
Linux GitHub Actions instance. It restores the pinned public crypto snapshot,
checks its source hashes, builds the release binary, verifies the frozen screen,
runs the Tier 1 preflight, and preserves the paired receipts as an artifact.
The comparison uses the repository's Tier 1 instance-scoped measurement policy.
