# Q1437: N131 weight-seven factor-base frontier

This is a frozen geometry and cost-model screen for a possible four-summand
normal-basis factor base on the exact curve `EC1N131Ckb1h6816f880945e`.
It extends Q1413's exact W≤6 projected base by sampling *distinct* W7
Frobenius x-orbits. Every W7 orbit has 131 elements because the field degree
is prime and a weight-seven mask is nonconstant. Sampling a uniform raw
weight-seven mask and rejecting an already seen orbit therefore samples
uniformly among the W7 orbits. The [protocol](protocol.json) fixes the seed,
100,000-orbit panel, dependencies, and accepted Sage runtime before execution.

## Frozen result

The [sample](sample.json) classified 100,000 distinct W7 x-orbits in 8.25 s
of exploratory local wall time. Exactly 50,213 were rational; all 50,213
had nonidentity cofactor-four projections, and none of their projected
signed-Frobenius keys collided *within the sample*. The [independent Sage
replay](verification.json) checked 32 archived masks against point lifting,
fourfold group multiplication, and the N131 subgroup order; all passed.

| W≤7 conditional quantity | Estimate | 95% sample-rate endpoints |
| --- | ---: | ---: |
| Rationality rate on W7 x-orbits | 0.50213 | 0.49903–0.50523 |
| Usable points `B` **if projection is collision-free** | 118.64 billion | 117.94–119.33 billion |
| Folded columns `K` **under the same assumption** | 452.81 million | 450.17–455.45 million |
| Mean distinct four-point subsets per uniform target | 12,128 | 11,848–12,413 |
| Optimistic `4K²` matrix proxy, log₂ logical row actions | 59.509 | 59.492–59.525 |

The matrix proxy sits only 1.49 bits below the `2^61` target in its own
logical-action unit. It therefore needs calibrated modular arithmetic and
the other phases before any total comparison. A pure quotient-pair index
would have about `131K² ≈ 2^64.54` pair states under this conditional K,
so the larger base does not rescue that construction.

The screen measures the rate of rational sparse x-orbits and records
nonidentity cofactor-four projections and collisions *within the sample*.
Its conditional W≤7 point and folded-column estimates add a projected new
weight-seven orbit for each rational orbit to Q1413's exact W≤6 base. That
addition assumes no unsampled projection collisions, including across the
weight-six boundary. The 95% Wilson interval describes the sampling rate;
it is not an exact factor-base count or a hard mathematical bound.

The matrix number `4K²` is an intentionally optimistic sparse-matvec proxy:
four nonzeros per row and K iterations, counted in logical row actions. It
does not charge modular arithmetic, rank overhead, collection, point
decomposition, construction, descent, or verification. The mean number of
unordered distinct four-point subsets per uniform target is a counting
average conditional on the estimated B. It does not imply a probability of
at least one representation or an efficient method to find one.

This remains proposal `Q1437`, with `candidate_id: null`,
`isogeny: "none"`, and actual W≤7 `B`, `K`, and enumerated-set digest null.
It is not a new `IC1` candidate, ordinary-query measurement, complete
degree-131 `2^x`, or challenge gate. The archived control verifier replays
sampled classifications with Sage's independent curve group law.

Reproduce using the repository's checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1437_weight7_frontier/sage_runtime_info.json
python3 experiments/compact-s3-m4-20261003/q1437_weight7_frontier/freeze_protocol.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1437_weight7_frontier/screen.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1437_weight7_frontier/verify.py --emit
```

The sampler and verifier refuse to overwrite archived outputs. Reproducing
in an existing checkout should remove only copied outputs in a separate
scratch checkout; preserve the original evidence.
