# Fixed relative Frobenius powers on the N83 width-16 base

This stage experiment searches the independently checked width-16 shifted
geometric base on the same public workload `df4396f4d8fc` as the
[free-power width-16 search](../n83-geometric-m5-normalized15-16-20261012/README.md).
The base has 32,648 folded columns and **5,419,568 usable subgroup points**
before sign and Frobenius folding. The first leaf is an affine seed. The other
four leaf x values use fixed relative Frobenius powers `1, 7, 23, 41`;
all 332 rotations of the four raw target preimages remain available.

The fixed-power ordinary formula has 54,545 AND gates, 191,375 CNF clauses,
1,434 native XOR rows, and 56,072 variables. The corresponding free-power
width-16 formula has 77,107 AND gates, 327,786 clauses, 1,593 XOR rows,
and 79,454 variables. Freezing the powers reduces the encoded search domain;
it does not alter the factor base or the public target. Any returned model
must pass the exact base-membership, four-cofactor, and group-sum replay.

A locked five-point relation using nonzero first-leaf Frobenius power 17
returned SAT in 0.094 solver seconds and passed exact point replay. Its
relative powers are exactly `0, 1, 7, 23, 41`. The generic normalization
identity, assumptions, and current curve-specific Lean proof boundary are
recorded in the [parent module](../n83-geometric-m5-normalized-20261012/Normalization.lean).
The width-16 base has a separate full-seed Sage replay. The ordinary-target
result and independent Sage relation replay are recorded in this directory.

The ordinary public target reached the frozen 600-second wall cap with
`external_timeout` and stage status `bounded_unknown`. Its target-dependent
PDP interval was 600.046 seconds and sampled solver RSS peaked at
522,436,608 bytes. The receipt verifier passed source, input, XCNF, solver
output, control, and exclusive phase checks. Independent Sage replay passed
the locked normalized control and recorded `no_relation_to_replay` for this
capped ordinary attempt. An [aligned-power follow-up](../n83-geometric-m5-zeropowers16-20261012/README.md)
sets all five relative Frobenius powers to zero on the same base and point.

The [protocol](protocol.json) freezes the public point, base key digest,
source and solver hashes, one CryptoMiniSat thread, five million conflicts,
600-second wall cap, 4 GiB sampled solver RSS stop, and at most 64 models.
The target-generation scalar remains private; the protocol contains its
one-way commitment. This run overlaps the free-power width 15/16 pair on
the local unisolated host, so CPU wall times are exploratory.

Use the checked repository Sage launcher for local jobs:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-fixedpowers16-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-fixedpowers16-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-fixedpowers16-20261012/control.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-fixedpowers16-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-fixedpowers16-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-fixedpowers16-20261012/verify.py
```

Producers refuse to overwrite terminal evidence. Reproduce in a fresh
experiment directory with the supplied frozen public protocol.
