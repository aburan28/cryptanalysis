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
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1439_fixed_leaf/verify_small_field.py
```

The commands refuse to overwrite frozen evidence. Reproduction should use a
fresh worktree, preserving this archive. The accepted launcher check stays
outside each solver-stage timer.

## Frozen result

The [archive replay](verification.json) rebuilds all four XCNFs byte for byte
and rechecks both returned relations. The [small-field check](small_field_verification.json)
exhaustively covers all triples for every nonzero-x anchor at N3 and one
anchor at N5, counting identity-intermediate and identity-target exceptions
separately. It checks 70,644 nonexceptional N5 triples against both `S3`
identities and target subtraction. These controls establish the algebraic
encoding on those cases; they do not measure ordinary relation yield.

| Cell | Solver result | Verified relations | Formula AND gates / XOR rows | Solver wall | Peak child RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 planted control | SAT | 1 | 16,854 / 530 | 2.525 s | 26.1 MB |
| N53 ordinary, seeded anchor | 60 s external timeout | 0 | 16,854 / 530 | 60.007 s | 209.9 MB |
| N83 planted control | SAT | 1 | 41,334 / 830 | 3.064 s | 37.9 MB |
| N83 ordinary, seeded anchor | 60 s external timeout | 0 | 41,334 / 830 | 60.006 s | 267.4 MB |

Both controls report 56,001 conflicts. The ordinary runs were externally
terminated before a final conflict summary, so their exact conflict counts
remain null. The logs show continuing restart progress; the receipts preserve
the complete raw output. Formula construction and target adjustment add
0.248/0.251 s at N53 and 0.051/0.050 s at N83 to the four stage cells in
the order shown. Their clocks include target-independent table construction,
so these are overcharged stage diagnostics, not a calibrated one-target IC
online comparison.

The ordinary N53 public target has some four-point decomposition, but the
frozen independent anchor is not known to occur in one. The two ordinary
timeouts cannot distinguish a missed anchor from expensive three-leaf
search. A known-witness fixed-anchor run with the other three leaves freed
would isolate that question, but it would be a witness-informed diagnostic,
never a natural-yield estimate. The complete N131 `2^x`, N83 useful-row
rate, rank gain, and single-target speedup remain unknown.

A separate **uniform-sum counting model** helps size this design. For a base
of `B` distinct subgroup-usable points in a subgroup of order `r`, one fixed
anchor has mean `C(B,3)/r` unordered three-point representations per uniform
target if triple sums behave independently and uniformly. It is not a
measured hit probability or solver complexity. The exact N53/N83 bases give
means 269.47 and 4.69. The exact N131 W≤6 base gives `2^-33.75`; the
conditional Q1437 W≤7 estimate gives `2^-21.22`, or about 2.45 million
anchors per expected hit. The W≤7 number inherits the sample's unproved
no-collision assumption. These counts make a repeated-anchor approach a
poor default for N131 unless a much cheaper target-conditioned membership
method is found; they do not establish a lower bound on every solver.

The [failed-v1 archive](failed_v1/README.md) preserves the preliminary
rows and their original hashes. That protocol omitted the anchor seed from
the workload identity and put solver caps there; the corrected protocol
was frozen and committed before the four final runs above.

The protocol's short solution-preservation sentence is read with the
relation rule above: four **distinct projected columns**. It does not
assert preservation of decompositions with an identity `B+C` intermediate;
such a pair projects to opposite points in the same folded column and cannot
be a valid four-column relation.
