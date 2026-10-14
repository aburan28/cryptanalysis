# Q1455: the complete N53 quotient pair index supplies 21 independent rows

The complete 2,743,068-state N53 quotient-pair index returned **21 distinct,
independently verified four-point relations** on the frozen 1.5-million-query
ordinary public point. All 21 increased augmented rank over the exact
subgroup order. The full table has **2,730,335 distinct signed-Frobenius
keys**, **12,506 repeated-key descriptors**, and **227 identity pairs**,
exactly matching Q1452's separate Python enumeration of the same complete
state set. The first two million native states reproduce Q1454's 15 query
matches and table-key count exactly.

The curve is `EC1N53Ckb1hf77aab617904`, workload `74f2979b3e68`, with
`isogeny: "none"`. Its exact factor base has B=24,062 subgroup-usable
points, K=227 folded columns, and enumerated-set SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
Q1455 remains a `PDP4mitm` stage proposal with null candidate and run IDs.

## Complete-index cap sweep

The same native field/curve/key kernel and hashed Q1454 base, lifts,
shuffled block order, public target, and query-index stream were used for
three table prefixes. Each count below is a completed pair-add attempt;
all candidate matches were independently expanded to full subgroup points,
re-added to the public point, and ranked in a separately oriented log
matrix.

| Table pair additions | Distinct keys | Matching queries | Verified distinct rows / augmented rank | Charged pair additions per novel row |
| ---: | ---: | ---: | ---: | ---: |
| 2,000,000 | 1,990,692 | 15 | 15 / 15 | 333,329 |
| 2,500,000 | 2,488,726 | 19 | 19 / 19 | 289,471 |
| **2,743,068** | **2,730,335** | **21** | **21 / 21** | **273,477** |

Every cap charges its table additions, 1,500,000 query-pair additions,
and 1,499,940 target-complement additions. The complete-index interval
therefore charges **5,743,008** pair additions (`2^22.453`), or
**273,476.6** additions per novel row (`2^18.061`). The same-target
homogeneous difference rank is 20. Each matching query produced one
verified occurrence, one distinct row, and one novel row; the measured
maximum is **one row per query**.

Q1451's two-million-draw random table cost 454,540 pair additions per
novel row on this same target and query stream. Q1454's deterministic
two-million-state prefix cost 333,329. Q1455's complete index cost
273,477: a **1.662×** stage efficiency gain over Q1451 and a **1.219×**
gain over Q1454, equivalent to 0.733 and 0.286 bits in this measured
N53 event quotient. The Q1451-to-Q1455 comparison changes both table
schedule and table size; the Q1454-to-Q1455 comparison changes only the
prefix cap.

The complete-index conditional match rate is **14.0×10⁻⁶ per query**.
Its Wilson 95% interval is **9.16–21.40×10⁻⁶** under uniform-with-
replacement draws against this fixed public point and table. The
2.0-million and 2.5-million prefixes return 10.0×10⁻⁶ and
12.67×10⁻⁶. These are conditional N53 query rates, not a target
population or degree-131 solve estimate.

## Native work and replay

| Native phase | Wall seconds |
| --- | ---: |
| Input loading | 0.036 |
| Table allocation | 0.007 |
| Complete table build | 77.534 |
| Target queries and lookup | 130.295 |
| **Native phase sum** | **207.871** |
| Launcher interval, including result serialization | **209.524** |

Peak native RSS was **207,863,808 bytes**. Independent base rebuilding took
1.889 s and independent match replay/rank took 2.360 s after the native
interval. Wall times are exploratory on this unisolated host. The stage
work comparison uses charged pair additions and independently verified
rank. The full table finished under the declared 1,200-second wall and
2,048 MiB RSS caps; all query positions were processed.

The complete table's key/repeat/identity counts match Q1452's Python
construction even though Q1455 shuffled its block order. The first
2,000,000 states give exactly Q1454's key and candidate counts, including
its 15 matching query positions. Q1454's native arithmetic control
passed 1,000 random nonzero field and 208 curve-add/quotient-key cases
against the checked Python ONB implementation; Q1455 used the identical
hash-bound arithmetic header.

## Degree-131 work distance

Q1447's conditional W≤7 pure pair-index model remains `2^85.18`
**logical pair actions**, **24.18 bits** above an abstract `2^61`
action cap. Its index construction is `2^64.53` states, 3.53 bits above
the cap, and its scalar sparse-matrix proxy is `2^59.50` modular events.
That model already assumes efficient quotient-pair state enumeration;
Q1455's measured N53 key coverage does not reduce its N131 exponent.
The complete N131 solve exponent and numerical challenge gap remain null
because the exact W7 base, degree-131 ordinary relation and rank yield,
final matrix work, and target recovery are not jointly measured.

The complete N53 index still yielded at most one independent row per
query. Q1447's conditional W≤7 all-output affordability calculation
requires roughly 12,560 useful rows per successful N131 query. The
N53 observation is a measured constraint on this method, while transfer
to N131 requires its own ordinary-query experiment. The next informative
N53 run should extend the query horizon against this fixed complete
index to measure rank novelty as it approaches K=227; N83 still needs
its first verified ordinary four-point relation from an exact charged
solver.

## Reproduce

`freeze.json` binds the source, exact Q1454 input fixture hashes, public
point, and prior Q1452/Q1454 receipts. `build_receipt.json` binds the
native binary; `native_raw.json` preserves its original output;
`native_measurement.json` records all cap and phase counts.
`independent_replay.json` reconstructs all returned four-point relations
from the committed Q1454 fixtures, and `analysis.json` derives the
named-unit work comparisons.

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n53_native_full/validate.py
```
