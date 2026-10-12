# Q1451: a larger N53 pair index supplies eleven independent relation rows

Increasing the frozen N53 quotient-pair table from 500,000 to 2,000,000
descriptors while keeping the same ordinary public point and 1,500,000-query
schedule produced **11 distinct, independently verified four-point
relations**. They have augmented rank **11** over the subgroup modulus and
same-target homogeneous difference rank **10**. The first 500,000 table
draws and every query draw are identical to Q1448, so its three rows recur;
the larger table adds eight distinct rows.

The exact curve is `EC1N53Ckb1hf77aab617904`, workload
`74f2979b3e68`, with `isogeny: "none"`. The actual factor base has
B=24,062 usable subgroup points, K=227 signed-Frobenius columns, and
enumerated-set SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
Q1451 remains a `PDP4mitm` stage proposal with null candidate and run IDs.

## Work and output multiplicity

The full frozen query cap completed. The table had 1,418,520 distinct
signed-Frobenius keys, 581,381 repeated-key descriptors, and 99 identity
pairs. Eleven query positions matched; all 15 checked descriptors yielded
valid full-point relations. Independent replay found 11 distinct point
multisets and 11 distinct rank rows. Three query positions had two or three
relation **occurrences**, but each such position supplied only **one
distinct, novel row**. Thus the maximum distinct and novel output per
matching query is one under this schedule.

| Event or phase | Q1448, 500k table | Q1451, 2m table |
| --- | ---: | ---: |
| Table pair-add attempts | 500,000 | 2,000,000 |
| Target query pair-add attempts | 1,500,000 | 1,500,000 |
| Target complement-add attempts | 1,499,940 | 1,499,940 |
| Verified occurrences | 3 | 15 |
| Distinct relations / novel augmented rows | 3 / 3 | **11 / 11** |
| Pair-add attempts per novel row, cold stage | 1,166,647 | **454,540** |
| Conditional matched-query yield | 2.00×10⁻⁶ | **7.33×10⁻⁶** |
| Maximum distinct rows from one query | 1 | **1** |

The cold-stage pair-add count per novel row improved **2.57×** at the
declared event boundary. Q1451's 11 matches in 1.5 million query draws
give a Wilson 95% interval of **4.09–13.13×10⁻⁶** per query under a
uniform-with-replacement sampling model *conditional on this one table and
public point*. This is not a cross-target or N131 relation rate.

Exclusive recorded wall phases were 110.284 s for base/column setup,
213.104 s for table build, 175.387 s for target queries and lookup, and
0.024 s for in-run relation verification/rank. They sum to 498.800 s;
the target-dependent query plus in-run check interval was 175.412 s.
Peak RSS was 472,317,952 bytes. Wall-time differences from Q1448 are
exploratory because the host is not isolated. All failed and identity
attempts are charged. Across Q1301, Q1448, and Q1451 on this public point,
the pair-table lane has charged **3,000,000** table samples and
**3,171,218** target query samples.

## N131 gate and next measurement

Q1447's conditional W≤7 all-output model needs roughly 12,560 useful
novel rows per successful query to fit its `2^61` residual-work window.
Q1451 increased N53 relation supply but did not create more than one
distinct row at a matching query. The N53 result does not transfer a
success cost to N131. The separate W≤7 pure pair-index model remains
`2^85.18` logical actions, **24.18 bits** above an abstract `2^61`
action cap; its units are separate from the pair-add count here. The fully
charged N131 solve exponent and challenge gap remain null.

The next N53 table experiment should continue target queries while keeping
the 2-million-descriptor table alive, measuring rank novelty as it grows
toward K=227 and preserving duplicate rows. In parallel, N83 needs its
first verified ordinary relation under an exact, charged method; Q1451's
one-point yield cannot substitute for that gate.

## Reproduce and verify

The [protocol](protocol.json) and [pre-run freeze](freeze.json) bind the
source, exact base archive, target, table/query seeds and caps.
[measurement.json](measurement.json) records every returned relation and
phase; [independent_replay.json](independent_replay.json) reconstructs all
24,062 base points, checks every four-point sum and subgroup membership,
and recomputes rank with a different column orientation. [analysis.json](analysis.json)
groups occurrences by query and accounts for pair additions.

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n53_table2m/validate.py
```
