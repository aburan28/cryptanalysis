# Normalized five-summand search at N83 widths 15 and 16

This paired experiment holds public workload `df4396f4d8fc`, solver,
resource caps, and Frobenius-normalized formula policy fixed while
comparing two independently verified
[shifted geometric bases](../n83-geometric-width15-16-20261012/README.md).
The first leaf is an affine seed, four remaining leaves select independent
Frobenius powers, and the target selector covers all 332 rotations of the
four raw cofactor preimages. The inverse rotation and exact point-group
replay map any verified relation back to the original public point.

| Width | Folded columns `K` | Actual points `B` | Five-subset first moment | AND gates | CNF clauses | Native XOR rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 15 | 16,376 | 2,718,416 | 511,643.0698604108 | 77,024 | 327,537 | 1,592 |
| 16 | 32,648 | 5,419,568 | 16,114,307.72534703 | 77,107 | 327,786 | 1,593 |

These are exact base counts and formula shapes, not relation-yield or
solver-speed measurements. Width 16 increases the combinatorial first
moment by 31.5 times while adding 83 AND gates and 249 clauses. Both
locked controls used a nonzero first-leaf Frobenius power, returned SAT,
and passed exact point replay. Independent Sage replay checks their group
relations in a separate polynomial-basis field. The generic normalization
proof and its partial curve bridge are recorded in the
[parent Lean module](../n83-geometric-m5-normalized-20261012/Normalization.lean).

The [protocol](protocol.json) freezes the same public target and one-way
scalar commitment, base files, source hashes, one CryptoMiniSat thread,
five million conflicts, 600 seconds per base, a 4 GiB sampled solver-RSS
stop, and at most three models per base. Every target-dependent attempt,
failure, solver output, formula, and exclusive phase cost is retained.
The local host is unisolated; wall times are exploratory.

Both ordinary attempts reached their respective 600-second wall caps with
`external_timeout` and stage status `bounded_unknown`. Width 15 charged
600.034 target-dependent PDP seconds with 395,706,368 bytes sampled solver
peak RSS; width 16 charged 600.071 seconds with 472,825,856 bytes. The
receipt verifier passed source, input, compressed formula, solver output,
locked controls, and exclusive phase checks for both rows. Independent
Sage relation replay passed both locked controls and retained
`no_relation_to_replay` for the capped ordinary attempts. The increased
first moments have therefore not yet translated into measured ordinary
relation yield under this solver cap.

Use the checked repository Sage launcher for local jobs:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-normalized15-16-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized15-16-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized15-16-20261012/control.py 15
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized15-16-20261012/control.py 16
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized15-16-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-normalized15-16-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-normalized15-16-20261012/verify.py
```

Producers refuse to overwrite terminal evidence. Use a disposable checkout
and the supplied protocol when rerunning the frozen public point.
