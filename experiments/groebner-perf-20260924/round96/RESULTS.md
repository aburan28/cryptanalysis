# Producer profile results

Frozen executable source: `4db384914952faa3a0e8b88f52bd12376514d623`.
The build binds 59 sources, 14 native libraries, two native control executables,
seven generated sources and two freshly regenerated polynomial resources.
Later documentation/evidence commits leave that executed source closure intact.

Six Python test groups passed, including native controls in optimized and
UBSan builds. Removing the diagnostic insertions reconstructs the baseline
engine and adapter source exactly. Budget, node/row/checker exhaustion,
fresh-input and concurrent calls retain their original non-timing result.

The panel contains 23 fixtures × two arms × two orders × two build modes =
184 calls. Its independent native-free audit passes 92 exact baseline/profiled
trace pairs and 23 reproducible profiles, with 80 certified algebra calls,
40 solved PDP calls, and 104 unsuccessful calls. It rechecks seven distinct
mathematical outputs. All 26 artifact-corruption controls are rejected.
Every exclusive work partition sums to the original producer work; no counter
overflow or unclosed scope occurs. Accepted bases, derivation DAGs, independent
checker counters, failure statuses and reasons remain identical.

## What the counters show

The percentages below are fractions of the existing **logical work budget**.
They are not CPU-time shares or counts of physical hardware operations. Rows
remain inconclusive unless explicitly marked solved/certified.

| Fixture | Outcome | Packed elimination | Normal scan | Ordered row merge | Matrices entered | Peak packed words per row |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| PDP 6, seed 1 | solved | 55.3% | 16.1% | 10.8% | 14 | 1 |
| PDP 9, seed 1 | inconclusive | 66.0% | 26.2% | 2.1% | 58 | 6 |
| PDP 9, seed 4 | inconclusive | 92.0% | 3.6% | 1.7% | 41 | 8 |
| PDP 12, seed 1 | inconclusive | 22.9% | 57.7% | 14.4% | 2 | 35 |
| Dense MQ 16 | inconclusive | 14.9% | 76.0% | 7.8% | 2 | 11 |

Across the five nine-variable PDP fixtures, packed elimination accounts for
65.2–92.0% of the charged budget. Across the five twelve-variable fixtures,
normal scanning accounts for 54.6–59.0%, and ordered merges for 12.7–14.4%.
Their repeated fixtures and planted input law do not estimate natural yield.
All thirteen hard fixtures still stop at the same producer limit, before any
checker is invoked.

The physical packed-word counter provides useful context: nine-variable seed 1
charges 13,208,444 logical units in packed elimination while performing 284,175
64-bit word XORs. Twelve-variable seed 1 performs 72,900 such XORs. These
different units must not be substituted for one another. Word XORs also omit
popcounts, lookup, allocation and other work. The logical budget intentionally
preserves the historical sparse trace and can charge operations that a shortcut
has already avoided physically.

## Next implementation selected

Test bounded scratch storage for `normal()`'s ordered symmetric-difference
merges. The current ordered merge allocates a new output vector each time.
The existing scratch path applies to the sparse matrix fallback; packed matrix
execution does not reuse that storage for normal reduction. A per-reduction
scratch vector can be reused without retaining target-dependent answers across
queries. Preserve comparator order, XOR witness emission, atomic budget charges,
exception behavior and a portable CPU fallback when the scratch cap is exceeded.

This is a representation hypothesis, not an established speedup. Record reused
versus fresh allocations and peak retained capacity, then compare uninstrumented
complete queries on an isolated host. Keep the thirteen unsuccessful fixtures
and identical work limits in the comparison. The earlier divisor-index
experiment in round13 already had mixed incremental benefit; this profile alone
does not justify enabling it or claiming that indexed lookup dominates time.

For GPU work, these particular matrices have small row widths, and the profile
also identifies substantial non-matrix work. A kernel-only result cannot replace
the complete single-query crossover measurement. No GPU routing, novel F6
asymptotic claim, complete IC result or qualified CPU ratio is introduced here.
