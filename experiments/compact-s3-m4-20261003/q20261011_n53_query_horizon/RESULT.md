# Q1456: a three-million-query horizon improves N53 pair-add cost per rank row

On the exact N53 ordinary target and complete quotient-pair index, a frozen
three-million-query prefix returned **50 independently verified rank rows**
for **8,742,948 charged pair-add attempts**. Its **174,858.96 pair additions
per novel row** (`2^17.416`) is the best of the three measured query caps and
is **1.564× lower** (0.645 bits) than Q1455's 1.5-million-query prefix.
Extending to five million queries returned 70 rank rows at 182,040.9 pair
additions per row; the extra horizon increased total rank but moved this
particular work ratio above the three-million checkpoint.

The curve is `EC1N53Ckb1hf77aab617904`; the ordinary one-point workload is
`74f2979b3e68`. The exact factor base has B=24,062 subgroup-usable points,
K=227 signed-Frobenius columns, and enumerated-set SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
The isogeny field is `none`. Q1456 is a `PDP4mitm` stage proposal with null
candidate and run IDs because the generator-anchored relation collection,
final matrix solve, and target descent are not wired into this configuration.

## Frozen query-cap sweep

Q1456 uses Q1455's complete 2,743,068-state table, the same shuffled orbit
pair blocks, the same public subgroup point, and the same Python MT query
seed. Its regenerated first 1.5 million query pairs have exactly Q1454's
SHA-256; their native match list and table counts match Q1455 byte for byte.
The [query audit](query_prefix_audit.json) independently regenerated all
five million pairs, checked the complete stream digest, and counted the
identity-pair exceptions used in exact addition accounting.

| Query cap | Native matches | Verified distinct rows / augmented rank | Charged pair additions | Additions per rank row |
| ---: | ---: | ---: | ---: | ---: |
| 1,500,000 | 21 | 21 / 21 | 5,743,008 | 273,476.57 |
| **3,000,000** | **53** | **50 / 50** | **8,742,948** | **174,858.96** |
| 5,000,000 | 76 | 70 / 70 | 12,742,863 | 182,040.90 |

The charge is one pair addition for every table state, one for every query
pair, and one target-complement addition except when the query pair is the
identity. The respective skipped complement counts are 60, 120, and 205.
All 76 native candidates were expanded into subgroup points, checked against
the public target with the independent Python curve implementation, and
ranked modulo the exact subgroup order. At each cap the maximum verified
relation count per query was one. The added 1.5-million-query interval gave
29 new rows from 32 matches; the final two-million interval gave 20 new rows
from 23 matches. Duplicate rows account for the other matches.

The match rates on this fixed public point and table are 14.0, 17.67, and
15.2 per million queries at the three cumulative caps. Their Wilson 95%
intervals, conditional on uniform-with-replacement query draws against this
fixed target and table, are respectively 9.16–21.40, 13.51–23.11, and
12.15–19.02 per million. They describe this query distribution; they are
not a degree-131 relation-yield estimate.

## Native phases and receipt recovery

The five-million-query native process completed its frozen 1,200-second
wall cap with 229,621,760 bytes peak RSS. It recorded 0.427 s input loading,
0.002 s table allocation, 202.835 s table construction, and 211.649 s
target query and lookup, for a **414.914 s native phase sum**. CPU wall ratios
are exploratory on this unisolated host. Q1455's earlier table phase took
77.534 s on the same source, which illustrates the host variation; the
work improvement above uses exact pair-add counts and rank, not wall time.

The native process wrote its complete [raw output](native_raw.json) to
`/private/tmp`. The SSD reached `ENOSPC` while the Python wrapper wrote the
measurement JSON, so its exact launcher wall interval was lost. The
[recovery script](recover.py) reconstructed the
[measurement receipt](native_measurement.json) from that preserved native
output, checked its frozen source and prior-receipt links, and records
`launcher_wall_ns: null` and
`receipt_write_status: recovered_from_native_raw_after_enospc`.
The independent [relation replay](independent_replay.json),
[query audit](query_prefix_audit.json), and [accounting](analysis.json) ran
after recovery. The raw native phase timers and operation counters survived
the write failure; no native search was repeated.

## Degree-131 work distance and next experiment

The best measured N53 cost per new rank row is `2^17.416` **pair-add
attempts per row**. Q1447's conditional N131 W≤7 model remains `2^85.18`
**logical pair actions**, 24.18 bits above an abstract `2^61` action cap;
its index construction alone is `2^64.53` states. Those are different work
boundaries. The fully charged N131 solve exponent and its numerical
challenge gap remain null until exact ordinary relation/rank yield, final
matrix work, and target recovery are measured together.

This sweep shows a useful cap choice for the N53 comparator, while its
one-row-per-query behavior leaves Q1447's all-output requirement of about
12,560 useful rows per successful N131 query unmet. The next solver
experiment should change target-compatible middle-pair discovery on the
exact N83 Q1325 factor base, with ordinary-query rank and a fully charged
operation count. The prior Q1091 N83 group-law run recovered a scalar on a
different base whose logs were known from construction; its direct-target
result is a separate comparison from the unknown-log relation-matrix path.

Reproduce the independent checks from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261011_n53_query_horizon/audit_queries.py
PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261011_n53_query_horizon/verify.py
PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261011_n53_query_horizon/analyze.py
PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261011_n53_query_horizon/validate.py
```
