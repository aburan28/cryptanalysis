# Q1447: weight seven changes the N131 four-summand bottleneck

Sampling the next two normal-basis weight strata shows a conditional N131
weight-at-most-seven base with about **450,968,776 folded columns**. In a
four-entry-row scalar sparse-matrix proxy, final linear algebra then costs
`2^59.50` modular operation events, about **35.3%** of an abstract `2^61`
work budget. This leaves a narrow but nonzero modeled window for relation
collection. Weight eight raises the same matrix proxy to `2^67.43`, far
past that budget. The weight-seven opportunity depends on returning many
verified, rank-increasing decompositions from each ordinary query.

The exact parent is Q1413's cofactor-four projected W≤6 base on
`EC1N131Ckb1h6816f880945e`: B=6,559,634,788 actual usable points,
K=25,036,774 folded columns, enumerated-set SHA-256
`e5f66c3944069924b9af7b8c22887e216702c8ac11a3a2ad072437e7d81ecb3b`.
Q1447 uses `isogeny: "none"` and remains a design proposal with
`candidate_id: null` and `run_id: null`. W7/W8 point sets and digests have
not been enumerated.

## Geometry sample and conditional base counts

For nonzero x on `y²+xy=x³+1`, rationality is equivalent to
`Tr(x+1/x)=0`, since `Tr(1/x²)=Tr(1/x)`. The sampled normal-basis masks
have fixed weight, so their x trace is the weight parity. The sampler drew
distinct cyclic Frobenius orbits uniformly within each new stratum and
tested rationality with the exact N131 field inverse and trace. It checked
64 masks per stratum against actual `pointFromX` lifts. Thirty-two rational
points per stratum survived cofactor-four projection as distinct nonidentity
projected x orbits; four per stratum passed an explicit subgroup-order check.

| New stratum | Distinct sampled x orbits | Rational | Rational fraction | Per-stratum Wilson 95% interval |
| ---: | ---: | ---: | ---: | ---: |
| W7 | 32,768 | 16,383 | 0.49997 | 0.49456–0.50538 |
| W8 | 8,192 | 4,088 | 0.49902 | 0.48820–0.50985 |

Extrapolating each stratum adds two signed point lifts per rational x mask,
assuming no unobserved identity projections or projected-orbit collisions.
The W7 estimate is **B=118,153,819,312** and **K=450,968,776**; the
componentwise Wilson interval gives K=446,357,042–455,580,515. The W8
cumulative estimate is B=1,844,590,711,506 and K=7,040,422,563. These
are conditional estimates, not actual factor-base counts or IC candidate
identities. The sample seed, stream hashes, exact source hashes, control
counts and all model inputs are in [measurement.json](measurement.json).

## Work screen in named units

The query-supply column counts all unordered four-point multisets divided
by the nonidentity subgroup size; it is a uniform-target upper mean, not
observed yield. The 95%-rank query floors use Markov and optimistically
assume every returned relation adds rank. The one-output floor additionally
caps each query at one returned relation. The matrix column is the explicitly
declared `4K²` scalar sparse-LA operation proxy. Pair actions use Q1416's
pure quotient-pair-index law and are separate from modular operations.

| Bound | Base status | Folded K | Mean representations per uniform query | 95%-rank queries if all returned | 95%-rank queries if at most one returned | `4K²` modular proxy | Pure pair-index build states | Pure pair-index total actions |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W≤6 | exact | 25,036,774 | 0.11335 | 209,828,278 | 209,828,278 | `2^51.16` | `2^56.19` | `2^89.36` |
| W≤7 | sampled conditional | 450,968,776 | about 11,932 | 35,906 | 428,420,338 | **`2^59.50`** | `2^64.53` | `2^85.18` |
| W≤8 | sampled conditional | 7,040,422,563 | about 7.09×10⁸ | 10 | 6,688,401,435 | `2^67.43` | `2^72.46` | `2^81.22` |

After reserving the W7 matrix proxy and setting all other costs to zero,
the `2^61` ceiling per ordinary query is **`2^45.24` modular-equivalent
events if all representations are returned**, or only **`2^31.70` if the
solver returns at most one**. The first regime requires a successful run to
average roughly 12,560 useful relations per query; the compact S3 solver has no
measured ordinary-query relation yield or multi-output cost. The W7 pure
pair-index model is still **24.18 bits above `2^61`** in its own logical
action unit, despite improving 4.17 bits over W6. Its `2^64.53` index-build
states alone also exceed the action cap. It does not calibrate the compact
S3 solver.

The W7 matrix proxy spans `2^59.47`–`2^59.53` across the componentwise
sample interval, occupying 34.6%–36.0% of the abstract cap. This is a
method proxy, not a lower bound for every possible final-matrix solver.
Factor-base construction, measured relation yield and rank, target descent,
and calibrated operation conversion remain outstanding, so the complete
N131 solve exponent and challenge decision remain open.

## Next measurement

The next solver gate is **enumeration throughput**, measured on the same
ordinary N53 and N83 public points and exact bases already frozen for the
compact S3 and pair-table comparisons. On N53, the Q1301 pair-table
ordinary relation supplies a checked starting witness: continue the
target-side search to count additional independently verified distinct
relations and novel rows, charging all queries. On N83, first obtain an
ordinary relation; then measure whether one query can return multiple novel
rows. This directly tests the condition that makes W7 promising before
the much larger base is enumerated.

## Reproduce

The sampler uses pure Python field and curve code; it invokes no Sage job.
Its protocol was frozen before the sample. On the recorded sources:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_weight7_screen/screen.py --check
python3 experiments/compact-s3-m4-20261003/q20261011_weight7_screen/validate.py
```

The check regenerates both deterministic samples and every conditional
calculation, compares the curve-lift and subgroup controls, and permits only
the descriptive sampling wall times to differ. The validator independently
cross-checks W6 against Q1414's exact uniform-query bound and Q1416's
exact-base pair-index screen.
