# Exact XOR projection of the frozen N131 d10/m15 query

Fill-limited elimination removes 147,152 CNF-private XOR variables from the
first saved precomputation query of the frozen d10/m15 v3 run. It reduces the
largest XOR-connected component from 168,622 to 43,467 rows while preserving
all 225,092 CNF clauses and keeping the total XOR literal count within its
original budget. This is an exact encoding improvement on the same query;
the running unprojected candidate is unchanged.

| Saved N131 d10/m15 precomputation query | Original | Projected |
| --- | ---: | ---: |
| Variables | 282,598 | 135,446 |
| CNF clauses | 225,092 | 225,092 |
| Native XOR rows | 208,783 | 61,631 |
| XOR literal occurrences | 899,559 | 899,557 |
| Largest XOR-connected component, rows | 168,622 | 43,467 |
| XCNF bytes | 10,887,544 | 9,879,561 |

The [projection receipt](budget1/result.json) binds the original XCNF SHA-256
`0ff3d72c2e45daa3539607ae82059523b4d58977d5a304a7b44b985a00e75036`,
the projected XCNF, variable map, reverse-lift rows, checked Sage runtime,
and transform source. The transform used an XOR-literal budget multiplier of
`1` and no pivot-width cap. It made 215,070 GF(2) row additions and retained
9,964 CNF-private variables; its widest intermediate row had 437 literals.
The [independent audit](budget1/independent_elimination_audit.json) replayed
all 147,152 pivots and row additions, then matched every mapped CNF clause
and residual XOR row. The [component profile](xor_components.json) counts
rows by shared XOR variables in both saved inputs. Its largest-component
figures describe the input graphs; CryptoMiniSat may partition or simplify
them differently at runtime.

The active solver's raw log says it disabled a 166,788-row XOR matrix as too
large. The projected input has a substantially smaller connected component,
but no projected ordinary solver attempt or verified relation has yet been
measured. This proposal has `candidate_id: null` and `run_id: null`. Before
promotion, freeze a separate solver protocol on an unpinned ordinary query,
check any projected model against every saved XCNF record, reverse-lift it,
independently replay the original formula and curve relation, and retain
every failed or timed-out attempt. Measure formula construction, projection,
solver, and verification as exclusive charged phases. The already-running
d10 query and the frozen d13/m12 public-Q probe keep their existing order and
resource caps; a projected trial must not be folded into either run record.
