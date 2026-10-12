# Constant raw target in the N83 width-16 S₃ search

This variant keeps four free Frobenius-power selectors over the complete
5,419,568-point shifted width-16 base, but fixes the S₃ chain's target to
raw cofactor preimage zero with no target rotation. It uses the same public
point `df4396f4d8fc` as the
[free-power parent](../n83-geometric-m5-normalized15-16-20261012/README.md).
It also propagates zero and singleton field-product coordinates as in the
[constant-folded variant](../n83-geometric-m5-constfold16-20261012/README.md).
Any returned relation is checked against the exact full base and original
public point; this formula searches one deterministic target slice.

The ordinary formula has 63,329 AND gates, 258,716 CNF clauses, 1,593
native XOR rows, and 65,584 variables. The free-power, 332-choice parent
has 77,107 gates and 327,786 clauses. Freezing the target removes its
large selector and propagates its 83 constant x bits through the last
S₃ link. The [checked canonical-x cache](../n83-orbit-key-x-20261012/README.md)
loads target-independent base membership without repeated point
reconstruction.

The [protocol](protocol.json) binds the public target, exact base and cache,
source and solver hashes, one CryptoMiniSat thread, five million conflicts,
600-second wall cap, 4 GiB sampled solver RSS stop, and at most 64 models.
The raw target preimage is chosen by the frozen cofactor-coset ordering,
independent of the private target-generation scalar. Local CPU times are
exploratory. The locked control pins a constructed relation and fixes its
own raw target choice so that the constant-target encoding and full group
replay are both checked.

The ordinary public target reached the 600-second wall cap with
`external_timeout` and stage status `bounded_unknown`. Its target-dependent
PDP interval was 600.027 seconds, and sampled solver RSS peaked at
306,757,632 bytes. The locked control returned SAT on a nonzero target
rotation and passed exact point replay. The receipt verifier and independent
Sage relation replay pass. The smaller target formula has not yet produced
a measured ordinary relation under this cap.

Use the checked repository Sage launcher for local jobs:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-fixedtarget16-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-fixedtarget16-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-fixedtarget16-20261012/control.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-fixedtarget16-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-fixedtarget16-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-fixedtarget16-20261012/verify.py
```

Producers refuse to overwrite terminal evidence. Reproduce with a fresh
directory and the supplied frozen public protocol.
