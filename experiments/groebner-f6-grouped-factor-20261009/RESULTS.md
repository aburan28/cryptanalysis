# Exact bit-sliced S3 factors admit the six-bit chain cases

Packing the nine Boolean coordinates of each static S3 link into one 16-bit
truth-table transform reduced counted static factor states by about ninefold
on the frozen GF(2^9) chains. Under the unchanged 24-variable bag and
200,000,000-state limits, the native separator completed four- and
five-summand chains with six-bit summand coordinates. The separate-coordinate
predecessor reached its state cap during construction on both geometries.

The source was frozen at commit
`c6ce1a6a656298870ea542276fd3e02c1c6a6701`. The source-bound local
build produced optimized and UBSan libraries. Across 160 arbitrary Boolean
systems, all native statuses and satisfiable assignments matched exhaustive
six-variable enumeration. The curve panel passed 5,120 grouped target runs
and 3,072 matched predecessor runs: every status agreed with independent
curve-sum enumeration, and every satisfiable witness passed the original ANF
equations and curve-point replay. The width-cap counterexample also returned
its expected status.

| Summands | Coordinate bits | Variables | Boundary bits | Base points | Grouped factor states | Separate-coordinate factor states | Grouped elimination states | Predecessor status |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 4 | 4 | 34 | 13 | 11 | 4,326,464 | 38,700,096 | 8,648,704 | Complete |
| 4 | 5 | 38 | 14 | 23 | 8,914,048 | 80,217,216 | 17,823,744 | Complete |
| 5 | 5 | 52 | 14 | 23 | 17,303,200 | 155,715,232 | 34,599,936 | Complete |
| 4 | 6 | 42 | 15 | 57 | 18,875,648 | 169,870,592 | 37,746,688 | State cap |
| 5 | 6 | 57 | 15 | 57 | 35,653,440 | 320,866,112 | 71,300,096 | State cap |

The grouped and predecessor counters in the first three rows are native
measurements from completed setups. The separate-coordinate counts for the
last two rows are deterministic sums of `2^support_width` over their canonical
ANF equations; the predecessor stops at its cap before finishing those
tables. All five grouped counters are measured native setup counters. Each
row represents all 512 target abscissae in both optimized and UBSan builds.
The `(4 summands, 7 coordinate bits)` middle link still has a 25-variable
union scope and returned `width-cap` at the unchanged maximum bag of 24.

The complete report is [report.json.gz](evidence/report.json.gz) (SHA-256
`0ec1b47dc33e86430768f3d31e76721ba12906f6e04bd0262dcc5c445bfc7449`).
The flushed arm-level [journal.jsonl.gz](evidence/journal.jsonl.gz) has
SHA-256 `9ea6010cc4e6279b6d713e2d728409a14dfde10cf76f4fba3a7a6c510f5ab517`;
its uncompressed SHA-256 is
`971454bc5f025ced4526b0347c680026738eba1b4e82ef19571b18c499ed5859`.
The report includes exact source and binary hashes, all completed/failure
rows, native counters, and the independent expected target set. The local
host is contended and lacks the required isolation receipt, so its timings
remain exploratory and the report keeps `timing_eligible=false` and
`qualified_speedup=null`.

This result changes the next F6 bottleneck: at seven coordinate bits, the
middle-link union scope itself exceeds the current 24-variable table limit.
A further exact extension should factor that link without materializing its
full 25-variable table, or prove a smaller separator representation, then
replay the same all-target and arbitrary-system controls. The grouped
Möbius-transform argument in [PROTOCOL.md](PROTOCOL.md) proves exact
conjunction of the packed coordinates; it does not imply a general
high-degree-of-regularity or asymptotic advantage for unstructured systems.
