# N83 E-1 sparse30 compact-rank directory against sparse28

The sparse30 compact-rank directory reduces exact full-key target probes from
7,415,319 to 819,487 (88.95%) at the 29,900,000-pair-state cap on the frozen
N83 single-target stage. Its root table grows by 117,506,048 bytes (112.0625
MiB). The full-capacity candidate and the merged sparse28 reference agree on
all 23 frozen semantic fields, including the first-witness pair certificate
`083d0561e2d3f52763840c10d4c540550b71446daaf09f3d1ef50a53def81a51`.
The directory gain has a direct eight-pair Tier 1 CPU comparison. On that
instance, the larger directory increased the target-stage wall time.

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

## Tier 1 result

The [GitHub Actions run](https://github.com/aburan28/cryptanalysis/actions/runs/38196155527)
completed eight alternating pairs on instance
`gh-38196155527-1-paired-stage`. All 16 raw arms and eight pairs passed the
frozen exact-result, RSS, and observed noise checks. The independent
`verify_tier1_receipt.py` replay passes against the archived raw outputs in
`tier1_github_38196155527/`.

| Tier 1 target-stage measure | Sparse28 | Sparse30 compact-rank |
| --- | ---: | ---: |
| Median online wall, seconds | 31.271 | 33.533 |
| Median target process CPU, seconds | 31.268 | 33.530 |
| Median query preparation, seconds | 2.668 | 2.683 |
| Median partner generation, seconds | 10.451 | 10.568 |
| Median partner check, seconds | 18.242 | 20.328 |
| Maximum native RSS, bytes | 5,308,686,336 | 5,444,669,440 |

The median paired sparse28/sparse30 wall ratio is **0.9370**, with a paired
bootstrap 95% interval of **[0.8917, 0.9782]**. Seven of eight pairs favored
sparse28. The sparse30 mode reduces full-key probes but adds about 2.09
seconds to the median partner-check phase on this instance. The exact cause
within the lookup path remains to be isolated; a smaller sparse29 directory
is the next direct comparison.

## Exact local replay

Both modes also completed one full-capacity local replay from the same new
binary. The wrappers verified the frozen result and certificate for each arm.
The raw results and binary/source hashes are in `local_replay_summary.json`,
`local_sparse28.json`, and `local_sparse30.json`.

| Exploratory local measure | Sparse28 | Sparse30 compact-rank |
| --- | ---: | ---: |
| Target-stage wall, seconds | 183.725 | 177.783 |
| Target-stage process CPU, seconds | 35.691 | 27.944 |
| Peak native RSS, bytes | 3,253,207,040 | 5,686,083,584 |

This unisolated sequential pair gives a 1.0334 wall ratio and a 1.2772
process-CPU ratio. The Tier 1 paired panel is the frozen wall-time gate.
