# Q1437: N131 weight-seven factor-base frontier

This is a frozen geometry and cost-model screen for a possible four-summand
normal-basis factor base on the exact curve `EC1N131Ckb1h6816f880945e`.
It extends Q1413's exact W≤6 projected base by sampling *distinct* W7
Frobenius x-orbits. Every W7 orbit has 131 elements because the field degree
is prime and a weight-seven mask is nonconstant. Sampling a uniform raw
weight-seven mask and rejecting an already seen orbit therefore samples
uniformly among the W7 orbits. The [protocol](protocol.json) fixes the seed,
100,000-orbit panel, dependencies, and accepted Sage runtime before execution.

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
