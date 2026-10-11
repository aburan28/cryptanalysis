# Exact target-conditioned first-pair support on the N41 public point

The complete eight-slot N41 fiber contains **12 canonical, distinct-column
rows** for the transported public point. Across those rows, the first pair
uses only **11 of 63 possible seed sums**, so an exact target-conditioned
lookup on that six-bit sum would reject `52/63` first-pair families. The
11 supported sums have full affine rank six and no nontrivial linear mask
equality; their Boolean indicator has algebraic degree six. This quantifies
both the rejection opportunity and the algebraic work needed to obtain it.

## Frozen instance and exhaustive method

The [protocol](protocol.json) fixes `GF(2)[t]/(t^41+t^3+1)`, curve
`y^2+xy=x^3+1`, subgroup order `549756390943`, eight source slots at
rotations `(0,0,10,10,20,20,30,30)`, actual base `B=256`, and 26 folded
columns. The public point is `Q=(1458168294740,1672312028033)`; the
transported target is `(1+Frobenius)Q=(920359962848,755404565011)`.
The [native producer](projection.cpp) transports each frozen projected source
point by the same map, makes four canonical same-rotation pair lists, indexes
all valid sums of the first two pairs, and probes every sum of the last two
pairs. It checks all eight columns and replays every exact group hit.

| Exact census item | Count |
| --- | ---: |
| Valid canonical pairs in each of four lists | 1,956 |
| Distinct seed sums possible in each pair | 63 |
| First-four index rows after column filtering | 3,167,136 |
| First-four column rejections | 658,800 |
| Last-four target probes | 3,825,936 |
| Exact group-sum hits before final column filtering | 20 |
| Cross-half column rejections | 8 |
| Valid canonical rows | 12 |
| Supported prefixes of 1, 2, 3, 4 pair seed sums | 11, 12, 12, 12 |

The [receipt](receipt.json) records `COMPLETE_EXACT_FIBER`, 1.451019084 s
to build the reusable first-four index, 5.436809042 s for the exhaustive
target-dependent probe, 19,082 ns for final relation replay, and
103,432,192 bytes peak RSS. The frozen limits were one worker, 120 s for
setup, 120 s for target-dependent probing, and 4 GiB RSS. These are
exploratory local stage times. Source transport and fixture loading occur
before those timed phases, so these stage times are not a complete IC online
interval. The [source/input lock](protocol.json) includes content hashes
for the native producer, binary, helper, input, fixture, and checked Sage
runtime.

The [independent Sage replay](sage_replay.json) used the repository's checked
Sage launcher, reconstructed every source point from the frozen input,
transported each point independently, verified the same public target,
checked eight distinct columns and the group sum for **all 12 rows**, and
recomputed all four prefix-support sets. Its first row reproduces the prior
public-point witness. The [analysis receipt](analysis.json) gives the exact
first-pair support
`{6,11,23,29,38,40,41,42,47,52,53}`, affine rank six, no
nontrivial linear equality, and indicator algebraic degree six with 18
nonzero ANF terms.

## Algorithmic decision

The 11-value support table is a compact exact constraint, but this run
constructed it by exhausting 3.83 million target-dependent four-pair
probes against a 3.17 million-row reusable index. It therefore diagnoses
the opportunity; it is not a cheaper way to find a relation than the
existing early-stop indexed join on this N41 point. The next constructive
gate is to derive a *sound over-approximation* of first-pair support from
the public target and two or more unresolved partial sums, with less work
than completing their pair lists. Measure its rejection rate and cost on
this same N41 point before a frozen N131 trial. The complete IC pipeline
remains a design proposal with `candidate_id: null`.
