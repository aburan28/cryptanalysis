# Orbit-complete N83 five-summand point decomposition

This experiment gives every leaf of the balanced S3 formula an independent
83-way Frobenius selector. A leaf can now reach any signed point in the
shifted width-13 factor base after the exact cofactor projection. The base
contains **4,125 folded columns and 684,750 subgroup points** before
folding. The formula accepts all four raw cofactor preimages of the same
previously unseen public point used in the [seed-only comparison](../n83-geometric-m5-compact-20261012/README.md).

The seed-only width-13 formula can reach 8,252 signed projected points. Its
distinct five-subset uniform-target first moment is
`1.3172215159550674e-7`, whereas the full orbit base's corresponding
first moment is `518.8513695245769`. These are combinatorial diagnostics,
not observed relation rates. The new leaf selectors cover the full base:
each rational shifted-affine x seed has two point signs, and the 83
Frobenius powers are available independently on each leaf. The exact
point-group replay checks every SAT model against the stored base keys and
public target. An independent Sage polynomial-field replay checks any
relation, including its membership in the rotated seed domain.
The [exhaustive coverage receipt](coverage.json) separately enumerates
seed-only and complete signed Frobenius sets for widths 11 through 13 and
checks the canonical key files and exact first moments.

The locked correctness control uses five distinct shifted seeds with
independent Frobenius powers `0, 1, 7, 23, 41`. CryptoMiniSat returned SAT,
and exact point replay verified the five-point relation. Its formula,
solver output, and replay are retained in `locked_control.*`; the Sage
verifier also checks that control in a separate field representation.

The [protocol](protocol.json) freezes width 13, the target workload
`df4396f4d8fc`, one CryptoMiniSat thread, five million conflicts, a
600-second wall bound, a 4 GiB sampled solver-RSS stop, and at most three
candidate models. Results and phase costs are in `width13_ordinary.json`;
`run_summary.json` binds the result hash. This is a bounded
point-decomposition stage. CPU wall times on the shared local host are
exploratory.

The ordinary-target cell reached the wall cap with `external_timeout` and
`bounded_unknown`. Its formula has 85,226 variables, 82,668 AND gates,
334,247 CNF clauses, and 1,660 native XOR rows. Sampled solver peak RSS
was 1,028,718,592 bytes. The receipt verifier passed source, input,
coverage, control, XCNF, output, and phase checks. Independent Sage replay
passed the locked rotated control and recorded `no_relation_to_replay` for
the ordinary target. The larger reachable base therefore remains a live
decomposition candidate whose solver search needs further work.

Run from a fresh checkout with the checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-orbit-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-orbit-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-orbit-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-orbit-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-orbit-20261012/verify.py
```

Each producer refuses to overwrite terminal evidence. A cap exit remains
`bounded_unknown`; any reported relation must pass the exact base,
subgroup, public-sum, and independent Sage checks.
