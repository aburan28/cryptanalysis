# Q1420 ordinary-Q0 XOR component scoreboard

The [component-selection gate](../ecc2k130-263-gauss-components-20261010/RESULT.md)
uses the exact source and degree-263 descendant ordinary Q0 XCNFs of workload
`eee7f6ee5f6b`, with equal `B=16,772,828` W24 usable point counts. Its
precommitted 2,000-conflict panel isolates CryptoMiniSat Gaussian matrix
selection on identical mathematical inputs. The [prior solver-stage
scoreboard](Q1420_SOLVER_STAGE_SCOREBOARD.md) retains the longer default and
wide-matrix wall-capped attempts.

| Policy | Source selected matrix | Descendant selected matrix | Q0 outcome at 2,000 conflicts | Peak sampled RSS MiB, source / descendant |
| --- | --- | --- | --- | ---: |
| Default limits | largest 730 × 733, five selected | largest 875 × 931, five selected | both `BOUNDED_UNKNOWN` | 177.94 / 186.69 |
| 8,000-row selector window | 7,380 × 7,524, one selected | 7,380 × 7,524, one selected | both `BOUNDED_UNKNOWN` | 233.52 / 237.42 |
| Largest only | 17,665 × 27,342 | 17,754 × 27,561 | both `BOUNDED_UNKNOWN` | 656.77 / 621.78 |
| Five large matrices | largest plus four 9,061 × 13,883 | largest plus four 9,061 × 13,883 | both `BOUNDED_UNKNOWN` | 1,103.31 / 1,091.16 |

The independent raw-XCNF inventory identifies the one 7,380 × 7,524
selector matrix with all 144 W24 selector inputs on each curve. The largest
raw components have no named input variables; an [erratum](../ecc2k130-263-gauss-components-20261010/ERRATUM.md)
corrects their earlier exploratory classification. All eight cells entered
search and reached 2,001–2,003 conflicts; zero verified relation rows were
emitted under that cap. Source largest-only and five-large policies had the
same printed restart rows but the latter used 1.680× peak sampled RSS;
descendant traces diverged at row five and the RSS ratio was 1.755×.

The next gate is selector-derived field-linear leaf propagation on archived
controls followed by held-out ordinary queries with complete branch, relation,
rank, and target accounting. Q1420 remains `candidate_id: null`; the shared
host has no CPU-isolation receipt, so solver timing ratios remain exploratory.
