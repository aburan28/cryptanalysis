# Rank-seven bilinear encoding reduces the fixed-sum N41 SAT circuit

**The exact seed-sum kernel eliminates one seed coordinate from each pair
product and shrinks the matched six-block N41 formula by 3,276 AND gates,
9,828 CNF clauses, 951 XOR rows, and 4,227 variables.** The public-point
formula remains satisfiable: the saved ordinary N41 six-block relation
gives a complete assignment that independently passes every unpinned
XCNF record. The one-worker CryptoMiniSat public query nevertheless
reached its frozen 120-second cap after active search. This separates
encoding size from the unresolved search bottleneck.

## Exact construction

The input is the frozen `EC1N41Ckb1h7d5e80d3c4d0` public point
`Q=(1458168294740,1672312028033)` in the subgroup of order
`r=549756390943`. Six fixed-sum blocks use Frobenius rotations
`[0,6,12,18,24,30]`, 40 usable unordered mask pairs per block, 160
signed subgroup pair states per block, **B=960** actual subgroup-usable
factor-base points, and **K=77** folded columns. The geometry and known
public relation are bound in the [protocol](protocol.json); proposal
`Q20261009175500` has `candidate_id: null` because this experiment
specifies the point-decomposition stage.

For `A(t)=t²+t`, seed `a`, fixed sum `s=a+b`, and pair output `z`, the
equation is

`A(z)[A(a)² + A(s)A(a)] = (s+z)²`.

The product map `L_s(a)=A(a)²+A(s)A(a)` is binary linear and has kernel
`{0,s}` on this subspace. Since seed-sum code `56` has bits `3,4,5`, the
product-basis columns obey `p_3+p_4+p_5=0`. The circuit drops bit `5`,
replaces selectors `3,4` by their XOR with selector `5`, and multiplies
`A(z)` by the seven remaining fixed field elements using direct binary
linear maps. Only seven selector-by-output products per field bit require
AND gates. The [preflight](preflight.json) checks 2,928 field-map and
saved-state equalities and builds both circuits with identical six-block
topology and the same pinned public witness.

| Matched pinned six-block formula | Generic field product | Rank-seven bilinear product |
| --- | ---: | ---: |
| Variables | 24,261 | **20,034** |
| CNF clauses | 44,821 | **34,993** |
| Native XOR rows | 9,833 | **8,882** |
| AND gates | 13,966 | **10,690** |

The generic formula is a source-identical construction except for the
local fixed-sum product implementation; these counts are circuit-size
diagnostics, not CPU speed ratios.

## Frozen runs and independent checks

| Run | Terminal status | Charged target-dependent wall | Peak combined RSS |
| --- | --- | ---: | ---: |
| [Pinned correctness control](control/result.json) | `FOUND_VERIFIED_RELATION` | 0.237 s | 35.1 MB |
| [Unpinned public query](public/result.json) | `ONLINE_TIME_CAP` | 120.086 s | 143.7 MB |

The pinned model passed full XCNF evaluation and native group lifting.
The [independent Sage audit](audit.json) replayed its six exact pair
states and all 12 subgroup leaves, then checked both terminal receipts.
The separate [public-formula audit](formula_audit.json) evaluated the
pinned model against the *unpinned* public XCNF and passed all 34,534
CNF clauses and 8,882 native XOR rows. Thus the public run's cap is a
search result rather than an unsatisfiability result. Raw solver streams,
formula, source hashes, checked Sage runtime, and the four-branch target
preimage policy are retained beside the receipts. Timings on this host
are exploratory without a host-isolation record.

## Next experiment

The remaining 10,690 AND gates are mostly in the five outer S3 links.
The next exact encoding replaces each local pair equation with its
precomputed 80 possible `(mask, pair-output)` descriptors and keeps
all target-linked S3 constraints and distinct-column checks. It should
preserve the same independently replayed public relation, measure the
unpinned natural query and full formula size, and project the N131 d13
2,204-descriptor-per-block tables under the 600-second/4-GiB gate.
