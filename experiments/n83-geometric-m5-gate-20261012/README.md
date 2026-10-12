# Ordinary five-summand PDP on shifted N83 geometric bases

This experiment compares two independently replayed factor bases on the
same newly frozen public point. The shifted width-11 base has **1,096 folded
columns and 181,936 usable subgroup points before folding**; shifted width
12 has **2,130 columns and 353,580 usable points**. Their uniform-target
five-subset first moments are 0.687003 and 19.0465, respectively. These
counts motivate the comparison; relation yield is measured by the bounded
ordinary-target solver receipts.

The formula searches unrotated affine seed x-coordinates. Its five leaves
therefore range over 2,194 signed projected points at width 11 and 4,262
at width 12, while the reported `B` values include their independent
Frobenius rotations. The corresponding distinct five-subset first moments
for the reachable seed points are `1.7441804017878079e-10` and
`4.8354509365184165e-9`. The full-base first moments above describe the
enumerated factor bases, not this formula's search domain. The
[orbit-complete follow-up](../n83-geometric-m5-orbit-20261012/README.md)
adds an independent Frobenius selector for each leaf. Its
[exhaustive coverage receipt](../n83-geometric-m5-orbit-20261012/coverage.json)
checks all signed seed and full-orbit points against the canonical key files.

Both ordinary attempts completed their frozen 600-second wall bounds with
`external_timeout` and status `bounded_unknown`. Width 12 used 84,746
variables, 82,668 AND gates, 248,692 CNF clauses, and 1,660 native XOR
rows; width 11 had the same gate and XOR counts and five more CNF clauses.
The sampled CryptoMiniSat peaks were 491,159,552 and 452,820,992 bytes for
widths 12 and 11. Neither capped cell produced a model. The
[receipt verifier](verify.py) passed source, input, workload, raw XCNF,
solver-output, and exclusive phase checks. The [independent Sage replay](sage_relation_replay.json)
records that there was no relation to check in either cell. These bounds
do not estimate natural relation probability or establish an UNSAT result.

The raw leaf x-coordinate lies in
`gamma_82 + span(gamma_1,...,gamma_d)` in the frozen N83 normal basis. Five
such leaves feed four factored S3 links. Each formula includes all four raw
cofactor preimages of one public prime-subgroup target. CryptoMiniSat reads
the resulting native-XOR XCNF. A SAT model becomes a relation only after
the five raw points, signs, cofactor projection, exact canonical base
membership, subgroup membership, and public target sum all replay. The
independent Sage verifier repeats the group-law replay in a polynomial
field model.

[protocol.json](protocol.json) freezes the target workload `df4396f4d8fc`,
source and input hashes, width-12 then width-11 run order, one solver thread,
five million conflicts, 600 seconds per base, 4 GiB sampled child-RSS stop,
and at most three candidate models per base. The target-generation scalar
was kept in a private local fixture; the published protocol contains the
public point and a one-way scalar commitment. `run.py` reads only the public
point in the protocol. Target generation, base loading, and the
cofactor-kernel setup precede the target-dependent interval. Formula build,
all attempts, model checks, and capped failures are charged. The host is
local and unisolated, so times are exploratory.

Run from a fresh repository checkout with the checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-gate-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-gate-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-gate-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-gate-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-gate-20261012/verify.py
```

Each producer refuses to overwrite its frozen output. The source tree must
match the protocol hashes. A conflict-budget exit or wall cap is recorded as
`bounded_unknown`, not interpreted as a mathematical negative. This is a
point-decomposition stage comparison with `candidate_id: null`; a complete
single-target IC comparison additionally needs relation rank, final matrix
work, target descent, and same-point rho under a declared resource tier.
