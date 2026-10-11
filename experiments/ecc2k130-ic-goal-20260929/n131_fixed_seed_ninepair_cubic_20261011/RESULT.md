# Exact nine-pair source count and public-point cubic gate

A ninth fixed-seed W18 pair raises the exact N131 distinct-column signed-tuple
count by **132,731.875 times** over eight pairs. Dividing by the full curve order
`4r` gives a uniform raw-point average upper ceiling of **4,702,411.07** labeled
nine-pair tuples, versus **35.4279** for eight pairs. The paired N41 W8 geometry
has 35 column-disjoint seed-184 edges and a corresponding nine-pair ceiling of
**3,054,381.39**. These are exact source-count averages, not measured
fixed-target relation yields. The [source count](support_result.json) records the
matching coefficients; [cofactor interpretation](support_interpretation.json)
uses the full curve order.

## Geometry and construction

The N131 field is `GF(2)[t]/(t^131+t^13+t^2+t+1)`, on
`y^2+xy=x^3+1`, with curve ID `EC1N131Ckb1heb5f1998f20b`, subgroup order
`r=680564733841876926932320129493409985129`, and cofactor four. Source
coordinates are `w=sum(mask_i*t^(i+1))` for 18 mask bits. Seed 212 gives 33,191
eligible unordered source pairs after excluding equal signed-Frobenius columns.
Their column conflict graph has 33,082 isolated edges, 26 two-edge components,
and 19 three-edge components. [support.py](support.py) computes its matching
polynomial through degree nine and independently checks coefficients one and
two from the edge-conflict graph. The N41 control uses `GF(2^41)` with
`t^41+t^3+1`, curve `y^2+xy=x^3+1`, W8 source masks, and seed 184.

The nine pair slots use Frobenius rotations `0,16,32,48,64,80,96,112,128`.
Each slot has 17 selector bits and an exact rational-source BDD. The compact
pair equation and eight halftrace-cubic group links produce a 499,736-variable,
215,343-AND ordinary XCNF formula. The [constructed control](control_result.json)
passes every clause and native-XOR row; [independent Sage replay](sage_fixture_result.json)
checks all nine source pairs, the ninth point addition, and the cofactor-four
subgroup projection using the checked [Sage runtime](sage_runtime_info.json).
The formula enforces distinct columns within each pair; a future SAT model
must additionally be checked for cross-slot column reuse and replayed on the
curve.

## Frozen public-point query

The [protocol](protocol.json) fixes public workload `cc09e7eb202a`, point
`Q=(1052727368764798954359115163823647684025,
2071227447786120917960296877345506689833)`, raw preimage index zero with
`[4]U=Q`, one CryptoMiniSat worker, 4 GiB combined RSS cap, 180-second solver
setting, and 195-second parent cap. It hashes executed source, the source table,
control fixture, solver binary, and target file before the query. The ordinary
formula took 4.387 seconds to construct and 0.038 seconds to write on this
unisolated host; these are diagnostic stage times.

| Stage | Recorded result |
| --- | --- |
| Exact N131 source | 33,191 eligible pairs; nine-pair full-curve mean upper ceiling 4,702,411.07 |
| Constructed control | `PASS_FULL_N131_HALFTRACE_CUBIC_CONSTRUCTED_WITNESS`; independent Sage group replay passed |
| Ordinary public query | `BOUNDED_UNKNOWN` at 195.050 seconds parent wall; sampled combined peak 683,196,416 bytes |
| Solver search | 229 bracketed diagnostics, restart trace present, empty stderr, no terminal SAT/UNSAT line |
| Relation and rank | No verified ordinary relation in this capped query; rank measurement remains pending |

The [query record](query_result.json) and [solver trace](solver.stdout.txt)
preserve the censored outcome. Formula construction, solver work, source-count
calculation, and group verification are separate costs. The candidate ID remains
`null` because this construction has not specified relation collection, final
matrix solve, factor-log preparation, and target recovery as one pipeline.

The next algorithmic gate is a target-conditioned selector restriction that
retains a verified N41 W8 nine-pair public decomposition under a frozen cap,
followed by an N131 ordinary query using the same restriction. The exact source
counts show that adding tuple multiplicity alone does not resolve the current
SAT search bottleneck.
