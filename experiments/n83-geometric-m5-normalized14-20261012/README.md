# Normalized five-summand search on the N83 width-14 base

This experiment compares the independently replayed
[width-14 base](../n83-geometric-width14-20261012/README.md) against the
[width-13 normalized formula](../n83-geometric-m5-normalized-20261012/README.md)
on the same public workload `df4396f4d8fc`. The width-14 base contains
**8,261 folded columns and 1,371,326 usable subgroup points** before
folding. Its distinct five-subset first moment is `16714.349889115683`,
versus `518.851369524577` at width 13. These combinatorial counts motivate
the paired ordinary-target search; they are not relation-yield measurements.

Both formulas normalize the first leaf to an affine seed, independently
select Frobenius powers for the other four leaves, and offer all 332
rotated raw target preimages. Width 14 adds only one free seed bit per leaf.
Its formula has **76,941 AND gates, 327,288 CNF clauses, 1,591 native XOR
rows, and 79,276 variables**; width 13 has 76,858 gates, 327,039 clauses,
1,590 XOR rows, and 79,187 variables. The signed base is checked against
the exact width-14 canonical key file. A locked five-point control with a
nonzero first-leaf rotation returned SAT and passed exact point replay.

The ordinary public target reached the frozen 600-second wall cap with
`external_timeout`; the stage status is `bounded_unknown`. The target-dependent
PDP interval was 600.066 seconds, including target preimage construction,
formula construction and writing, solver time, and relation checking. The
sampled solver RSS peak was 748,339,200 bytes. No verified relation row was
produced in this capped attempt. The independent Sage relation verifier and
the receipt verifier both passed; they preserve the capped ordinary status
and replay the locked control.

The proof of the generic normalization identity and its explicit
assumptions is in the parent
[Lean module](../n83-geometric-m5-normalized-20261012/Normalization.lean).
The curve-specific Lean bridge remains partial; the independent Sage
polynomial-field replay checks the executed point relations and the
normalizing Frobenius power. The width-14 geometry itself passed a separate
full-seed Sage replay.

The [protocol](protocol.json) freezes the same target point, solver,
conflict and memory limits, and 600-second wall cap as width 13. The
target-generation scalar remains private; only the public point and its
one-way commitment are in the protocol. All target-dependent attempts and
exclusive phase costs are retained. CPU wall times on the local shared host
are exploratory.

Use the checked repository Sage launcher for local runs:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-normalized14-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized14-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized14-20261012/control.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized14-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized14-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-normalized14-20261012/verify.py
```

Producers refuse to overwrite terminal evidence. To rerun the frozen public
point, use a disposable checkout and preserve the supplied protocol.
