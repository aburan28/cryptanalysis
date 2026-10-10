# Exact two-pair backtracking gives 99,456 distinct N41 residuals

**Two backward fixed-sum pair blocks from the frozen N41 public point
produce 99,456 valid labeled residuals, all at distinct group points and
distinct x coordinates.** The saved six-pair public relation occurs at
table offset 90,537, and an independent checked-Sage audit replayed that
relation plus 40 sampled residuals. The measured construction took
9.265 s of target-dependent wall and 56,983,552 B peak process RSS on
one worker. Thus the exact two-pair table provides no collision
compression on this source policy.

## Method and exact domain

The point is `Q=(1458168294740,1672312028033)` on
`EC1N41Ckb1h7d5e80d3c4d0`, with subgroup order `549756390943`.
The fixed geometry uses six blocks of 160 signed pair states, rotations
`[0,6,12,18,24,30]`, B=960 usable subgroup factor-base points, and
K=77 folded columns. For each of the four raw preimages `T` with
`4T=Q`, and signed pair states `P4,P5` from the last two blocks, the
[builder](build.py) computes the full group point

`R=T-P4-P5`.

It admits a pair of states only when their four folded factor-base
columns are distinct. It excludes the identity and `x=1` from the
nonexceptional phi-coordinate table. On this point neither exceptional
case occurred. The table stores both 41-bit coordinates and the
`(T,P4,P5)` labels in 15 bytes per record, preserving the group sign and
an exact witness path. A root constraint on the first four blocks can
then ask whether their group sum is in this target-derived domain. The
proposal is `Q20261009181500`; `candidate_id` and `run_id` are null for
this point-decomposition stage.

| Frozen domain quantity | Exact count |
| --- | ---: |
| Signed state pairs before column filtering, per target preimage | 25,600 |
| Pairs rejected for a repeated folded column, per preimage | 736 |
| Valid state pairs, per preimage | 24,864 |
| Stored labeled residuals over four preimages | 99,456 |
| Distinct residual group points / x coordinates | 99,456 / 99,456 |
| Group collision excess / exceptional residuals | 0 / 0 |
| Packed table bytes | 1,491,840 |

The [protocol](protocol.json) fixed eight source and input hashes, the
public point, and the 600-s/4-GiB envelope before the run. The checked
[Sage runtime receipt](sage_runtime_info.json) was saved before the
measured construction. The [result](result.json) binds the packed
[table](table.bin) by SHA-256. The [audit](audit.json) independently
recounted all packed records and their labels, verified the four raw
target preimages, replayed 41 group residuals in Sage, and checked the
known first-four partial sum against its table entry. The audit receipt's
`witness_scalar_replay` key denotes this group equality and subgroup
projection; it is not a discrete-log certificate.

| Phase | Exact wall nanoseconds |
| --- | ---: |
| Target-independent geometry and pair filtering | 10,176,792 |
| Four raw target preimages | 6,314,583 |
| Target-dependent residual construction and exact replay | 9,254,614,708 |
| Table serialization and receipt | 4,110,834 |
| **Charged target-dependent total** | **9,265,040,125** |

The phase times are from one local run without host isolation; they are
algorithmic diagnostics. The target-dependent table is a preparation
stage for a relation search, not a complete target query. For context,
the earlier exact [3+3 join](../n41_w8_fixed_sum_pair_blocks_20261009/six_block_join/result.json)
found the same public relation in 0.650 s of target search after 1.522 s
of reusable left-table construction, under its recorded workload.

## Gate from the measured cardinality

The previous [one-pair backward table](../n41_w8_fixed_sum_backward_20261009/RESULT.md)
has 640 distinct residual coordinates. The second backward pair expands
the target-derived domain by `99,456/640=155.4`, or 7.280 bits, while
removing one forward block with 160 signed choices, or 7.322 bits. The
0.042-bit difference is explained by the 736 repeated-column pairs per
preimage; there are no additional point-sum collisions to merge. Thus
moving another block backward alone transfers almost the same number of
choices from the forward search into the target table. It does not
provide the early family rejection sought for the N131 relation gate.

The next design step is a joint constraint on several forward partial
sums that rejects whole incompatible state families **before** their
pairwise enumeration. Its first test should keep the saved public
relation, measure actual rejected family counts and construction cost
on unpinned N41 queries, and then provide a source-bound work and memory
estimate for N131 before running that public query.
