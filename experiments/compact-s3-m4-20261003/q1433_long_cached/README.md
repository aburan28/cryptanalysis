# Q1433: longer ordinary queries with the exact Q1432 cached solver

Q1432 lowered the guarded span filter's field-operation cost, but its
ordinary N53/N83 queries remained censored at 60 seconds. Q1433 keeps the
same solver binary, CNF, exact curve and factor-base records, public targets,
target-preimage lists, and decision policy. Its [frozen protocol](protocol.json)
changes only the run cap to 300 seconds and five million conflicts, with a
330-second external safeguard. It gives that termination policy a new stage
configuration digest, while preserving the Q1432 workload IDs. The protocol
and N53 known-witness control were committed before the ordinary run.

Both known-witness freed-partner controls independently returned verified
four-point relations. The [archive verification](verification.json) rebuilds
the CNFs, checks the exact input and binary hashes, replays both controls,
and verifies sampled span rejections. The two unpinned ordinary queries
both reached the 300-second wall cap without a relation:

| Degree | Curve ID | Actual usable base `B` | Folded `K` | Ordinary result | Decisions | Span checks / rejections | Field mul / sqr / inv calls | Peak child RSS |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 | Censored; 0 relations | 903,175 | 867,084 / 846,828 | 4,753,049 / 8,927,113 / 102,986 | 1,557,807,104 bytes |
| 83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 | Censored; 0 relations | 677,658 | 599,283 / 595,290 | 4,490,849 / 18,307,009 / 163,592 | 2,222,800,896 bytes |

The exact factor-base enumerated-set digests, public points, stage run IDs,
and memory receipts are in the protocol and per-cell receipts. The N53
public target is known representable from Q1301, but this unpinned solver
did not recover it. The recorded operation counts and 300-second intervals
are lower bounds for these **specific failed attempts**. They do not supply
cost per useful relation, a natural relation yield, or two solved cost points
from which to fit growth. The CPU host lacks an isolation receipt, so wall
times are exploratory. Peak RSS rose substantially from Q1432's 60-second
runs as checked states and permanent rejection clauses accumulated.

This is proposal `Q1433`, with `candidate_id: null` and
`isogeny: "none"`. No complete N131 `2^x` is justified, and no challenge
run follows. Another longer cap on the same search order is a weak next
experiment. The next solver needs a compact target-conditioned pair-sum
membership and witness procedure that changes the ordinary-query search,
with its own solution-preservation proof and N53/N83 measurement.

## Reproduction

Rebuild the exact Q1432 binary and verify the Q1433 archive from a checkout:

```sh
python3 experiments/compact-s3-m4-20261003/q1432_coefficient_cache/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1433_long_cached/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1433_long_cached/verify_archive.py --require-complete --emit
```

The checked Sage runtime receipt was captured before the measured cells.
`run_stage.py` refuses to overwrite an archived result.
