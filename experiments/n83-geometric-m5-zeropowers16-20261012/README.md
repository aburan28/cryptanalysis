# Frobenius-aligned five-summand search on the N83 width-16 base

This experiment aligns the five affine-seed leaves to the same Frobenius
power. Normalizing the first leaf makes every relative power zero. The
target selector still includes all 332 rotations of the four raw cofactor
preimages. It uses the same public point `df4396f4d8fc` and independently
checked shifted width-16 base as the
[fixed-power parent](../n83-geometric-m5-fixedpowers16-20261012/README.md):
32,648 folded columns and **5,419,568 usable subgroup points** before
sign and Frobenius folding.

The aligned ordinary formula has 52,719 AND gates, 185,960 CNF clauses,
1,393 native XOR rows, and 54,268 variables. The parent with relative
powers `0, 1, 7, 23, 41` has 54,545 gates, 191,375 clauses, 1,434 XOR
rows, and 56,072 variables. Alignment lets constant and zero product
coordinates propagate through the S₃ chain. This is a smaller search slice
of the same factor base; every returned model is subject to exact
point, subgroup, base-membership, sign, and public-sum replay.

A locked relation with original Frobenius power 17 on all five leaves
returned SAT and passed exact point replay. The resulting normalized
relative powers are all zero. The ordinary public target uses the same
formula construction without pinned leaves or intermediate values.

The ordinary attempt reached its frozen 600-second wall cap with
`external_timeout` and stage status `bounded_unknown`. It charged 600.007
target-dependent PDP seconds and sampled a 399,409,152-byte solver RSS
peak. The receipt verifier passed the source, input, formula, solver output,
locked control, and exclusive phase checks. Independent Sage replay passed
the locked control and recorded `no_relation_to_replay` for the capped
ordinary attempt. Formula reduction has therefore not yet produced a
measured ordinary relation on this point under the stated cap.

The [protocol](protocol.json) binds the parent result, public target, base,
source and solver hashes, one CryptoMiniSat thread, five million conflicts,
600-second wall cap, 4 GiB sampled solver RSS stop, and at most 64 models.
The target-generation scalar remains private; only its one-way commitment
is retained. CPU times on this shared host are exploratory. The generic
normalization proof and partial curve-specific Lean bridge are in the
[parent theorem module](../n83-geometric-m5-normalized-20261012/Normalization.lean).

Use the checked repository Sage launcher for local jobs:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-zeropowers16-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-zeropowers16-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-zeropowers16-20261012/control.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-zeropowers16-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-zeropowers16-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-zeropowers16-20261012/verify.py
```

Producers refuse to overwrite terminal evidence. Reproduce in a fresh
experiment directory with the supplied frozen public protocol.
