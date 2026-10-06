# Q1468: exact N53 pair-sum oracle on Q1467's base

Q1468 compares `PDP4mitm` with Q1467's `PDP4hybrid` on **the same** N53
curve, exact 2,756-point factor base, workload IDs, and public targets. It is
a stage proposal: `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. There is no complete IC candidate, controlled CPU speedup,
or degree-131 work estimate.

The [input generator](make_inputs.py) independently materializes all 2,756
nonidentity subgroup points from Q1467's 1,378 allowed raw x masks, retaining
their 26 distinct signed Frobenius columns (106 points each). The native
[oracle](pair_oracle.cpp) forms every unordered pair from *different* columns:

`C(26,2) × 106² = 3,651,700` pair sums.

It sorts the full sums, then for each pair sum `S` checks whether the table
contains `target − S` with two more distinct columns. Every four-point sum
with four distinct folded columns has such a partition. The program checks
the full table count and every query candidate count before reporting absence.
Batch inversion changes the implementation cost; it does not omit pairs.

## Frozen single-target observations

The [protocol](protocol.json) binds the exact base, binary, checked Sage
runtime, targets, code hashes, order, and 600-second caps for table and
query phases. It first runs 64 deterministic native batch-addition controls.
All 64 independently match checked-Sage curve arithmetic. The
[archive audit](archive_verification.json) separately replays the returned
four-point relation and verifies the complete-enumeration counts.

| Matched Q1467 target | Pair-table result | Complete table setup | Target query | Query pair sums examined | Peak child RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 planted, leaves unpinned | verified four-distinct-column relation | 3.933 s | 1.958 s | 1,540,096 | 91,291,648 B |
| N53 ordinary | no four-distinct-column sum on this exact base | 3.648 s | 4.334 s | 3,651,700 | 91,193,344 B |

Both Q1467 chained-\(S_3\) runs on these public points reached their
60-second cap. The ordinary point's pair-table result explains why its SAT
timeout cannot measure a successful-solver cost. The planted point is known
representable and the pair table recovers it, so its SAT timeout still shows
a limit of that frozen solver. The pair-table setup is target independent and
is recorded separately from the target-dependent query. The host was not
isolated, so all wall times are exploratory; no wall-time speedup ratio is
promoted. Exact field multiplication, squaring, and inversion counts for
both phases are in the run receipts and [work ledger](../work_ledger.json).

The ordinary absence is a result of the source-bound complete native
enumeration, supported by independent arithmetic samples and a recovered
control relation. It has not been replicated by a second full oracle. One
ordinary absent target does not estimate natural relation yield, useful-row
cost, or rank. This table's quadratic size also gives no efficient N131
solver by itself. N83 success cost, final relation-matrix work, target
descent, and complete N131 \(2^x\) remain unknown; the challenge stays closed.

## Reproduce

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/make_inputs.py --check
python3 experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/build.py --check
python3 experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/verify_archive.py --check
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The next natural-yield experiment should freeze a panel of uniform,
previously unseen N53 subgroup targets and query this exact table. Report
success and absence counts with uncertainty, each target's online cost, and
novel relation rank. A shared table panel is secondary to the already
completed single-target measurements and must keep its setup separate.
