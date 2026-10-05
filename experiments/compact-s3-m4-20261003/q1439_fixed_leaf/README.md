# Q1439: fixed-leaf compact four-summand stage

This proposal tests a target-conditioned reduction on the exact Q1438 bases. It
keeps one usable raw point `A` fixed, independent of the ordinary public
target. For every raw cofactor preimage `T` of the public point and both signs
of `A`, it computes `U = T - sign(A)`. It then searches for three sparse raw
points `B,C,D` using two factored `S3` links:

```text
S3(x(B), x(C), x(M)) = 0
S3(x(M), x(D), x(U)) = 0
```

No `S5` is expanded. The raw-to-subgroup projection and all signs are replayed
with the curve group law before any result counts as a relation. Projected
signed-Frobenius columns must be distinct. The fixed-anchor reduction is exact
for four-point solutions containing that anchor and having a nonidentity
adjusted target. The frozen inputs have zero identity adjustments. For a valid
relation with distinct projected columns, the `B+C` intermediate cannot be
the identity. The test does **not** claim to search all possible first leaves;
coverage from sampling many anchors and its cost remain unmeasured.

This is stage proposal `Q1439`, not an `IC1` pipeline: `candidate_id` is null,
`isogeny` is `"none"`, and the complete N131 work exponent is null. The exact
factor-base counts and digests remain those of Q1438. N53 uses
`EC1N53Ckb1hf77aab617904`, W≤4, B=324,042, K=3,057,
`9e12afb51aaf2bbf47640554ce88b3653903375c33489ce8b1e07abe6a649cae`.
N83 uses `EC1N83Ckb1h876c2921cb64`, W≤6, B=408,131,750, K=2,458,625,
`c1ee6d1064935976fc0d3e479f895fe4832722b5991ba148a6d6cb003b76330d`.
Both curves use the `b=1` Koblitz model, but the exact field and subgroup
records are in the linked Q1438 protocol; the short curve tags are hints.

The [frozen protocol](protocol.json) binds the source, dependencies, binary,
checked Sage runtime, exact input receipts, anchor seeds and points, target
adjustments, formula sizes, caps, and four run IDs. The ordinary anchors are
the first usable exact-weight masks from independent fixed PRNG streams. The
control anchors are archived witness leaves and are explicitly pinned. The
ordinary cells have no witness pins. The archived N53 ordinary public target
is known representable on an older base, but that fact is not used to choose
the ordinary anchor. The N83 ordinary target is distinct from its planted
control target.

Run order is N53 control, N53 ordinary, N83 control, N83 ordinary. Each
ordinary query has a one-million-conflict and 60-second child cap. Controls
have a 200,000-conflict and 30-second child cap. Every censored row is kept.
The stage wall includes target adjustment, formula construction, solver
process launch, and returned-model replay; it is exploratory because this
host has no isolation receipt. SAT conflicts and formula sizes are stage
operation proxies, not calibrated field-operation counts. No single-target
IC speedup, useful-row yield, or complete N131 `2^x` follows from a timeout
or a planted control.

Reproduction, in a fresh checkout with no prior Q1439 outputs:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1439_fixed_leaf/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1439_fixed_leaf/experiment.py freeze
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1439_fixed_leaf/experiment.py run --degree 53 --cell control
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1439_fixed_leaf/experiment.py run --degree 53 --cell ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1439_fixed_leaf/experiment.py run --degree 83 --cell control
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1439_fixed_leaf/experiment.py run --degree 83 --cell ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1439_fixed_leaf/experiment.py verify --emit
```

The commands refuse to overwrite frozen evidence. Reproduction should use a
fresh worktree, preserving this archive. The accepted launcher check stays
outside each solver-stage timer.
