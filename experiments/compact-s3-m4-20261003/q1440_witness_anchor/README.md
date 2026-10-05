# Q1440: witness-anchor three-leaf search gate

Q1439's independent ordinary anchor may have no representation on its public
target. Q1440 isolates that ambiguity by using the archived first leaf of a
*known* four-point relation while leaving the other three sparse leaves free.
It reuses Q1439's exact N53 W≤4 and N83 W≤6 bases, cofactor-preimage
adjustment, and two factored `S3` links. `S5` is never expanded.

N53 uses the same archived ordinary public target as Q1439; the known
relation supplies the anchor, so this is **witness-informed** and cannot be
counted as natural relation yield. N83 uses the archived planted public target
and its witness anchor, which is also a diagnostic only. Each degree has two
cells: `choice_pinned` fixes the adjusted-target selector from the archived
witness while leaving all three leaves free; `choice_free` leaves the selector
and all three leaves free. Both cells are known satisfiable before running.
The Q1439 controls already showed SAT when those three leaves were pinned.

The [frozen protocol](protocol.json) binds the exact curve, field, subgroup,
base B/K/digest, target and witness receipts, adjusted-target set, formula
SHA-256, source, checked Sage runtime, CryptoMiniSat binary, workload IDs,
and 60-second/one-million-conflict caps. This remains a `Q` proposal with
`candidate_id: null` and `isogeny: "none"`; the N131 complete solve exponent
and cost per useful row stay null. A SAT result is independently replayed
against the public subgroup point and distinct signed-Frobenius columns.
CPU walls on this host are exploratory.

Use the repository's checked Sage launcher for every run:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1440_witness_anchor/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1440_witness_anchor/experiment.py freeze
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1440_witness_anchor/experiment.py run --degree 53 --cell choice_pinned
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1440_witness_anchor/experiment.py run --degree 53 --cell choice_free
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1440_witness_anchor/experiment.py run --degree 83 --cell choice_pinned
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1440_witness_anchor/experiment.py run --degree 83 --cell choice_free
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1440_witness_anchor/experiment.py verify --emit
```

The commands refuse to overwrite frozen evidence. Use a fresh worktree for
reproduction. The Sage runtime check is outside the stage timer.
