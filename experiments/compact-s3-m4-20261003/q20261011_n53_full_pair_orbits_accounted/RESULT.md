# Q1452: complete N53 quotient pair orbits give 2,730,335 distinct keys

Enumerating every relative sign and Frobenius state of two folded
factor-base representatives built a complete quotient pair index with
**2,743,068 pair-add attempts** and **2,730,335 distinct keys**. An ordinary
same-point query run then reached its frozen 900-second wall cap after
**123,033** query positions. It returned one independently verified
four-point relation and one augmented rank row. The matching position was
query **13,323**, also the first match in Q1451's identical query prefix.

The exact curve is `EC1N53Ckb1hf77aab617904`, workload
`74f2979b3e68`, with `isogeny: "none"`. The exact factor base has
B=24,062 subgroup-usable points, K=227 signed-Frobenius columns, and
enumerated-set SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
Q1452 is a `PDP4mitm` stage proposal; candidate and run IDs remain null.

## Index and query result

For each `0 <= i <= j < 227`, the index stores the sum of representative
`i` with both signs of each of the 53 Frobenius lifts of representative
`j`. The base-lift check covered all 24,062 base points. All descriptors
at a signed-Frobenius pair-sum key are retained. The 2,743,068 generated
states yielded 2,730,335 distinct keys, 12,506 repeated-key descriptors,
and 227 identity pairs. Thus 99.54% of attempted states produced a new
nonidentity key.

| Charged event or result | Q1451 random 2m table, full query cap | Q1452 complete orbit table, wall-capped |
| --- | ---: | ---: |
| Table pair additions | 2,000,000 | 2,743,068 |
| Distinct table keys | 1,418,520 | 2,730,335 |
| Ordinary query positions | 1,500,000 | 123,033 |
| Target complement additions | 1,499,940 | 123,030 |
| Verified occurrences / distinct rows | 15 / 11 | 1 / 1 |
| Augmented rank / same-target difference rank | 11 / 10 | 1 / 0 |
| Maximum distinct rows at one query | 1 | 1 |

Q1452 charged **2,989,131** pair additions: table additions, one query
pair addition per position, and one target complement addition for every
nonidentity query pair. The capped interval contains one novel row, so the
observed cost is 2,989,131 additions per row within this interval. Q1451's
full schedule cost 454,540 additions per novel row. These are different
table schedules and different query horizons; the Q1452 wall cap censors
its later-query yield. The Q1452 conditional match rate is 1/123,033,
or 8.13e-6 per query, with a Wilson 95% interval of 1.43e-6 to 4.60e-5
under uniform-with-replacement draws conditional on this point and table.

The complete index removes most repeated table states, but the first
123,033 query positions supplied the same single row as Q1451's prefix.
No matching position in the measured Q1452 interval returned multiple
verified relations. The full schedule needs a longer run before its rank
yield can be compared to Q1451 over identical query counts.

## Exclusive work phases and status

| Phase | Wall seconds |
| --- | ---: |
| Base and column setup | 46.670 |
| Quotient orbit lift index | 0.049 |
| Complete pair table build | 717.843 |
| Target queries and lookup | 135.656 |
| Relation verification and rank | 0.0005 |
| **Sum** | **900.218** |

Peak RSS was **704,954,368 bytes**. CPU wall times are exploratory because
the host was not isolated. The target-dependent interval was 135.657 s;
the complete index is reusable target-independent preparation. The wall cap
status is `wall_cap`, not a complete 1.5-million-query comparison. All
attempts made by this frozen replay are charged. The earlier frozen attempt
has `PRODUCER_INTERRUPTED_NO_RECEIPT` status and unknown work, recorded in
the adjacent directory; its output and work are not folded into this run.

## Challenge distance and next experiment

The Q1447 conditional N131 W<=7 pure pair-index model remains
`2^85.18` logical actions, 24.18 bits above an abstract `2^61` action
cap, with `2^64.53` index-build states alone. Those logical units are
separate from the N53 pair-add count and wall time here. The complete
N131 solve exponent and numerical challenge gap remain null because the
W7 exact base, ordinary relation yield, rank novelty, final matrix cost,
and target recovery have not been measured together.

The next useful hyperparameter experiment is a **unique-state prefix**
of this deterministic quotient orbit schedule, with several table caps
and a fixed common query horizon. It can test whether a table of about
two million *unique* states reaches Q1451's relation yield with fewer
pair additions, and whether increasing toward the complete index returns
multiple distinct rows per query. N83 still needs an ordinary relation
under a charged exact-base schedule.

## Reproduce and verify

`freeze.json` binds the protocol, exact base archive, curve, public target,
source hashes, and preceding measurement. `measurement.json` records
the completed index, all observed relations, phase work, and wall cap.
`independent_replay.json` rebuilds the factor base from the archived
canonical x keys, checks subgroup membership and the exact four-point sum,
and recomputes rank in a different column orientation.

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n53_full_pair_orbits_accounted/validate.py
```
