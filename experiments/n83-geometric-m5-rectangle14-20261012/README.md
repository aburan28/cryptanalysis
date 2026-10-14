# Normalized five-summand stage on the N83 rectangle width-14 base

The [certified rectangle base](../n83-geometric-rectangle14-20261012/README.md)
contains **8,532 signed-Frobenius columns** and **1,416,312 usable
subgroup points**. At the same 16,384 affine `x` candidates as the prior
shifted width-14 base, it adds 271 columns. The exact full-base
five-subset first moment rises from 16,714.349889 to 19,641.774144
(17.51%). This experiment wires that basis into the same normalized
five-summand method on frozen public workload `df4396f4d8fc`.

The first raw leaf is normalized to an affine seed; four others choose
independent Frobenius powers. All 332 rotations of the four raw
cofactor preimages are available to the target selector. The two extra
basis vectors are disjoint two-bit normal-basis vectors. The affine
offset overlaps one bit of each, so some first-leaf coordinates are
negated seed literals. The generalized leaf map handles those literals
without new nonlinear gates in the map itself. The ordinary formula
has 77,107 AND gates, 327,786 CNF clauses, 1,593 XOR rows, and 79,444
variables; the prior shifted width-14 formula has 76,941 AND gates,
327,288 CNF clauses, 1,591 XOR rows, and 79,276 variables. The 166
additional AND gates and 498 additional clauses are charged to the
rectangle formula.

| Same frozen public point, 600-second cap | Shifted width 14 | Rectangle width 14 |
| --- | ---: | ---: |
| Folded columns `K` | 8,261 | **8,532** |
| Full-base five-subset first moment | 16,714.350 | **19,641.774** |
| AND gates | 76,941 | 77,107 |
| CNF clauses | 327,288 | 327,786 |
| Ordinary stage status | `bounded_unknown` | `bounded_unknown` |
| Solver terminal status | `external_timeout` | `external_timeout` |
| Target-dependent PDP interval, shared host | 600.066 s | 600.116 s |
| Sampled solver RSS peak | 748,339,200 B | 475,512,832 B |

The ordinary rectangle run charged **600.116 seconds** to the target
PDP interval: 0.336 seconds for target preimages, 0.470 seconds for
formula construction, 0.435 seconds for writing, 598.713 seconds for
the solver, and 0.161 seconds of measured residual overhead. The
solver returned no model by the cap. The raw XCNF and solver stdout
are preserved. Shared-host wall and RSS differences are exploratory
stage diagnostics.

The [protocol](protocol.json) freezes the same public point, CryptoMiniSat
binary, 5,000,000-conflict limit, 4 GiB sampled solver-RSS stop, and
600-second target-dependent wall cap as the prior normalized width-14
arm. It pins the rectangle key and basis manifest hashes and all
algorithm-affecting sources. A [full domain check](domain_check.json)
visits all 16,384 affine seeds and 5,312 rotated seed samples. The
[locked control](locked_control.json) uses all four cosets and a nonzero
normalizing Frobenius power; SAT, exact point replay, and the independent
polynomial-field Sage replay passed.

The first locked control found SAT but its imported model decoder read
negated seed literals as unset bits. The [original attempt](attempt1/FAILURE.md)
preserves its protocol, source, raw XCNF, solver output, and failed
receipt. The corrected runner expands signed literal truth values
before replay. This is an implementation correctness improvement for
affine bases whose offset overlaps their variable coordinates.

The [ordinary-query result](width14_ordinary.json) and exclusive phase
costs retain this capped attempt. The next solver experiment should
change the search method or query structure and measure verified
ordinary relations and novel rank on this exact base. `candidate_id`
remains null pending the complete pipeline and one-target online
comparison.

Run the checked local Sage launcher from the repository root in a fresh
copy of this directory. Producers refuse to overwrite frozen receipts:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-rectangle14-20261012/sage_runtime_info.json
python3 experiments/n83-geometric-m5-rectangle14-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-rectangle14-20261012/domain_check.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-rectangle14-20261012/control.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-rectangle14-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-rectangle14-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-rectangle14-20261012/verify.py
```

The normalization identity and assumptions are checked in the earlier
[Lean module](../n83-geometric-m5-normalized-20261012/Normalization.lean).
The new affine basis and finite census have their own partial
formalization and independent Sage replay in the rectangle-base
experiment. The independent relation replay checks executed group sums,
subgroup projection, and normalization in a polynomial field.
