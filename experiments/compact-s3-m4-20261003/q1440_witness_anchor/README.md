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
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1440_witness_anchor/verify_known_witness.py
```

The commands refuse to overwrite frozen evidence. Use a fresh worktree for
reproduction. The Sage runtime check is outside the stage timer.

## Frozen result

The [archive replay](verification.json) rebuilds all four XCNFs byte for
byte. The separate [known-witness replay](known_witness_verification.json)
loads each Q1439 control SAT model and checks that it satisfies **both**
Q1440 formulas at that degree, including the selector-pinned formula. The
same model independently replays to the public point with four distinct
projected columns. Thus all four Q1440 cells are demonstrably satisfiable;
none relies only on a statistical representation assumption.

| Cell | Solver result | Exact conflicts reported | Verified relations | Solver wall | Peak child RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 known anchor, choice pinned | conflict cap | 1,000,001 | 0 | 39.373 s | 161.8 MB |
| N53 known anchor, choice free | conflict cap | 1,000,002 | 0 | 56.832 s | 201.3 MB |
| N83 known anchor, choice pinned | 60 s external timeout | null | 0 | 60.006 s | 198.3 MB |
| N83 known anchor, choice free | 60 s external timeout | null | 0 | 60.005 s | 274.8 MB |

The N83 child was terminated before a final conflict summary; the raw logs
retain progress, but the exact conflict counts stay null. Formula construction
and target preparation take about 0.25 s at N53 and 0.05 s at N83 per cell.
These times include target-independent multiplication-table construction and
are unisolated stage diagnostics, not one-target IC online speed measurements.
The formulas have 16,854/41,334 AND gates and 530/830 XOR rows at N53/N83.

This closes the specific Q1439 ambiguity: one anchor is guaranteed to occur
in a relation, yet the unpinned three-leaf SAT search still fails within its
bounded run. It does not prove an asymptotic lower bound or exclude a
different three-sum algorithm. The N83 target is planted and the N53 anchor
is witness-informed, so no ordinary N83 useful-row yield, rank gain, or
complete N131 `2^x` can be inferred. Further selector-only SAT variations
should give way to a method that obtains a target-conditioned sparse-pair
witness before enumerating full pair assignments.
