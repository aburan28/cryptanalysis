# Q1371: 83-bit external root-index layout and relation-work model

**Status:** design and arithmetic audit only. `candidate_id`, `workload_id`,
and `run_id` are null. No Q1371 root index, natural relation, relation matrix,
factor-log solve, target DLP, or rho pair has been run.

Q1371 extends the existing packed wide-root-index design with a bounded
external-memory bucket layout for the exact Q1104 `d=12` base. The earlier
packed format already carries an 83-bit key; this note addresses how to lay
out its 10.203 GiB projected payload across the two currently available
volumes without a full-size sort copy. The projection remains a model until a
complete index build measures records, wall time, peak RSS, and target lookup
cost.

## Frozen input and exact record geometry

The curve is `EC1N83Ckb1h876c2921cb64`, with subgroup order
`2417851639230796216685689`. Q1104's independently replayed `d=12` base has
`B=337146` usable points before folding and `K=2031` effective columns. Its
enumerated base digest is
`4cec7215223fd372d49b4b87460d58e8ca13553172d1d62819719132cfddc3db`.
The exact state count is `K^2 * 83 = 342371763`.

Each projected root record is 16 bytes:

| Field | Bytes | Meaning |
| --- | ---: | --- |
| canonical root key | 11 | unsigned big-endian 83-bit field element; the top five padding bits must be zero |
| state ID | 4 | enumeration state in `[0, 342371763)`; 29 significant bits |
| root and orbit selector | 1 | root ordinal plus the seven-bit canonical Frobenius shift |

The current Q1104 model assumes two root records per state, for 684743526
records and 10955896416 bytes (10.203 GiB). Both records are retained when
keys collide. Queries compare the complete 83-bit key and inspect the full
equal-key range; a partition hash is only a routing hint and never establishes
key equality.

The record width is derived from the Q1104 descriptor rule in
[`N83_PACKED_WIDE_ROOT_INDEX_MODEL_20261005.md`](../N83_PACKED_WIDE_ROOT_INDEX_MODEL_20261005.md).
The two-root count remains an explicit projection for this base. Q1371 must
count actual emitted roots and retain any deviation from that projection.

## External bucket design

Use 256 final buckets selected by the first eight bits of a frozen digest of
the canonical 11-byte key. Sort each bucket by
`(full_key, state_id, root_ordinal, Frobenius_shift)`. The first eight digest
bits are split into a four-bit high digit and a four-bit low digit during
streaming; this keeps the lookup rule deterministic while retaining exact
full-key comparisons.

Generate records once into 256 append-only bucket streams. Keep at most 64
file descriptors open with an LRU writer and 1 MiB buffers per bucket, for a
256 MiB buffer ceiling. Assign 55 buckets to `/Volumes/SSD990` and 201 to
`/private/tmp` using the current free-space snapshot. A small pilot histogram
must confirm the assignment before a full build. The full build records exact
per-bucket counts and bytes; if either volume would fall below the 1.25 GiB
free-space reserve, stop before sorting and preserve the partial receipt.

The mean projected final bucket is 2674779.4 records, or 40.8 MiB. Sort one
bucket at a time with a 64 MiB in-memory cap and a same-volume temporary file;
replace the bucket atomically only after its sorted checksum and record count
match. If any bucket exceeds 64 MiB, recalculate the disk gate before further
partitioning. Do not assume uniform hashing as a measured fact: preserve the
complete bucket histogram and reject a build whose observed skew violates the
space or memory limits.

At the current free-space snapshot, the 55/201 split projects about 2.19 GiB
of raw payload on the SSD volume and 8.01 GiB under `/private/tmp`. Including
one 64 MiB sort temporary, the projected remaining free space is about 1.43
GiB and 1.46 GiB respectively, leaving only about 0.18–0.21 GiB above the
1.25 GiB reserve. These margins vary with other activity; a fresh byte-exact
preflight is required immediately before any build. The total raw payload plus one maximum bucket
temporary is about 10.27 GiB, versus 20.41 GiB for the prior full two-copy
sort model.

The build's initial resource envelope is a 2 GiB combined process-tree RSS
cap, 256 MiB of output buffers, at most 64 MiB for one bucket sort, and no
more than 64 open bucket files. These are design limits, not measured RSS.
Index construction time, hash cost, and lookup I/O cost remain unknown. In
particular, a disk-resident table is useful only if the target-conditioned
join can avoid enough random I/O to beat the matched one-target rho interval.

## Relation-work scale on existing Q1104 bases

The exact uniform-target mean number of distinct unordered five-supports is
`binom(B,5)/r`. The table uses the corrected unordered-support audit, not the
ordered `B^5/r` tuple scale.

| Base | `B` | `K` | Packed root payload | Mean distinct five-supports per uniform target | Optimistic targets for `K` rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q1104 `d=10` | 78684 | 474 | 596739456 B (0.556 GiB) | 0.0103936 | about 45605 |
| Q1104 `d=11` | 168656 | 1016 | 2741671936 B (2.553 GiB) | 0.470297 | about 2161 |
| Q1104 `d=12` | 337146 | 2031 | 10955896416 B (10.203 GiB) | 15.012958 | about 135.28 |

The last column divides `K` by the mean support count and assumes that every
support is found and gives a novel rank-increasing row. It is an optimistic
query-count model, not a lower bound on a specific solver's runtime or a
prediction of observed rank growth. The d12 audit records zero natural queries
and zero verified natural relations. PDP cost, support discovery probability,
novel rows per target, rank completion, factor-log recovery, and DLP time all
remain unknown.

## Gates and next action

1. Run the checked codec controls for 83-bit keys, 29-bit state IDs, root
   ordinals, orbit shifts, duplicates, and padding; the existing packed codec
   receipt is a prior control, not a Q1371 build result.
2. Freeze and run a bounded d10 planted five-point control against a small
   bucketed index, with the five seed masks withheld from the solver and an
   independent checked-Sage group replay. Record actual bucket counts and
   exact target lookups.
3. Only after that control passes, decide whether the d12 external build is
   worth its 10.203 GiB footprint. Then measure ordinary target attempts,
   verified relations, novel rank, lookup throughput, setup, and target PDP
   separately.
4. A complete N83 DLP requires recovered base logs, final matrix solve,
   target descent, and independent scalar replay. Pair any completed one-target
   result with rho on the same public point and the same frozen resources.

The design extends an existing serialization model; it is not a new IC
candidate or a measured speed result.
