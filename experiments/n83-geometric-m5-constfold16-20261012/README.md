# Constant-folded S₃ products on the N83 width-16 base

The aligned width-16 five-summand formula contains many field-product
coordinates that are identically zero or equal to one existing literal.
This variant propagates those constants and singleton XOR rows before
encoding later S₃ products. It keeps the [aligned parent](../n83-geometric-m5-zeropowers16-20261012/README.md)
public point `df4396f4d8fc`, 5,419,568-point base, five summands,
all-zero relative Frobenius powers, 332 target choices, solver, and
600-second ordinary-target cap.

The ordinary formula has 47,241 AND gates, 169,460 CNF clauses, 1,391
native XOR rows, and 48,722 variables. The parent has 52,719 gates,
185,960 clauses, 1,393 XOR rows, and 54,268 variables. The construction
uses exact XOR parity cancellation: an empty row becomes a constant, a
singleton row becomes its literal, and larger rows retain a native XOR
constraint. The usual locked relation and independent Sage replay check
the resulting point-decomposition semantics.

The ordinary public target exhausted the five-million-conflict limit:
CryptoMiniSat reported 5,000,001 conflicts and `s INDETERMINATE` after
584.742 solver seconds. The target-dependent PDP interval was 587.273
seconds, with a sampled solver RSS peak of 1,597,718,528 bytes. The
inherited solver wrapper records exit code 15 as `solver_failure`; its raw
stdout and return code identify a conflict-cap stop, and the stage status
is `bounded_unknown`. The locked control returned SAT and passed exact
point replay. Independent Sage replay and the receipt verifier pass for
the frozen artifacts.

Target-independent base lookup loads the complete
[checked canonical-x cache](../n83-orbit-key-x-20261012/README.md),
whose key order and digest are bound in the [protocol](protocol.json).
The protocol also binds the parent result, source and solver hashes, one
CryptoMiniSat thread, five million conflicts, 4 GiB sampled solver RSS
stop, and at most 64 models. The public workload retains only a one-way
commitment to the private target-generation scalar. Local CPU times are
exploratory.

Use the checked repository Sage launcher for local jobs:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-constfold16-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-constfold16-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-constfold16-20261012/control.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-constfold16-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-constfold16-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-constfold16-20261012/verify.py
```

Producers refuse to overwrite terminal evidence. Reproduce with a fresh
directory and the supplied frozen public protocol.
