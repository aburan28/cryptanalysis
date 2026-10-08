# IC idea falsifiers: G1–G4, A1–A2, N1

This directory implements bounded, reproducible stage probes for the seven
ideas in the 2026-10-07 shortlist. Every receipt has `candidate_id: null`:
none specifies and measures a complete factor-base-to-DLP pipeline. These
results cannot be inserted as `IC1` one-target speedups. CPU wall times here
are exploratory because this host has no isolated benchmark receipt.

The code is split into [Boolean algebra and sparse matrix primitives](boolean_core.py),
[Sage probes](sage_probes.py), and the [frozen N41 matrix census](g3_n41_sparse.py).
The latter imports the existing N41 S6 equation builder without changing it.
All new Sage invocations use the repository's checked launcher. The saved
[runtime receipt](results/sage_runtime_info.json) was captured before the
measurements.

## What each probe actually decides

| Idea | Implemented gate | What remains outside this gate |
| --- | --- | --- |
| G1 | Build N31 m=2 and m=3 Boolean S3/S4 systems on 16 planted targets, freeze generator degree slots, capture a Macaulay elimination trace, replay it, compare exact echelon rows, and charge matrix construction on both paths. | A complete F4 symbolic trace and natural-query PDP throughput. |
| G2 | Verify S3 Frobenius equivariance on toy fields, diagonalize cyclic convolution by a field DFT, and count rational character blocks of a degree-two monomial module. | The barrel-system Macaulay operator, blockwise F4 basis equality, and an isolated speed comparison. |
| G3 | Stream every degree-four sparse Macaulay row from the frozen N41 S6 ANF, counting nonzeros and active columns under explicit row, column, and RSS caps. | A solving-degree proof, rectangular sparse preconditioning, block Wiedemann implementation, and target recovery. |
| G4 | Compare N19 m=3 mixed-field and Boolean variable/equation counts, run bounded Sage mixed/Boolean Gröbner and Boolean msolve F4 controls, and enumerate field-rational versus algebraic-closure intermediates. | A matched F4 kernel on both encodings and verified complete PDP throughput. |
| A1 | Enumerate all norm-≤16 elements of `Z[τ]` up to sign, fold their subgroup scalars by existing sign/Frobenius symmetry, and materialize a point-prefix closure on the retained N53 base. | A new base with 600 effective columns, natural relation probes, weighted-rank growth, memory-matched collection, and final LA. |
| A2 | Enumerate N23 cyclotomic weight-two/three and normal-basis weight-two/three x families; match whole **usable** Frobenius orbits by actual `B` and folded columns; compare exact m=2/m=3 coverage on 16 paired subgroup points. Check the claimed `x^263=1` membership equation. | F4/WDSat solving degree and bounded ordinary-query solve time. |
| N1 | Map `F₂[Z/47]` onto `GF(2^23)` through a primitive 47th root and test whether 256 planted S3 identities lift to exact group-algebra identities under the declared polynomial section. | Other sections or a lifting algorithm that solves the 24-bit kernel constraints. |

For A2 and N1, planted witnesses establish correctness or a structural
failure; they are not natural relation-yield estimates. A2's 16 uniform
subgroup target points are the coverage sample, with both bases tested on
the same points.

## Replay

From the repository root:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/ic-ideas-20261007/results/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python -m unittest discover -s experiments/ic-ideas-20261007 -p 'test_*.py'
/Volumes/SSD990/cryptanalysis/sage -python experiments/ic-ideas-20261007/sage_probes.py g1 --output /tmp/g1-replay.json --targets 16
/Volumes/SSD990/cryptanalysis/sage -python experiments/ic-ideas-20261007/sage_probes.py g2 --output /tmp/g2-replay.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/ic-ideas-20261007/g3_n41_sparse.py --output /tmp/g3-replay.json --max-rows 2100000 --skip-distinct-columns --max-rss-bytes 3500000000
/Volumes/SSD990/cryptanalysis/sage -python experiments/ic-ideas-20261007/sage_probes.py g4 --output /tmp/g4-replay.json --targets 8 --solve-seconds 15 --boolean-sage-seconds 15 --boolean-f4-seconds 20
/Volumes/SSD990/cryptanalysis/sage -python experiments/ic-ideas-20261007/sage_probes.py a1 --output /tmp/a1-replay.json --k 600
/Volumes/SSD990/cryptanalysis/sage -python experiments/ic-ideas-20261007/sage_probes.py a2 --output /tmp/a2-replay.json --targets 16
/Volumes/SSD990/cryptanalysis/sage -python experiments/ic-ideas-20261007/sage_probes.py n1 --output /tmp/n1-replay.json --targets 256
```

The A1 `--k` option currently counts a prefix of **points**, not folded
columns. The retained N53 base has 220 folded columns in total, so its
`--k 600` check is not the proposed K=600 relation-collection test. Every
receipt records its exact point and folded-column counts. Output paths must
be new: runners refuse to overwrite prior receipts.

## Findings and receipts

| Idea | Current evidence | Decision at this gate |
| --- | --- | --- |
| G1 | [Final 16-target receipt](results/g1_final.json): with fixed generator slots, exact echelon replay matched only 1/16 N31 m=2 targets and 2/16 m=3 targets. | The captured Macaulay trace fails the stated all-target basis-equality gate. The charged timing ratio on only two matching cases is not a speedup result. |
| G2 | [Final symmetry receipt](results/g2_final_current.json): sampled S3 equivariance and toy DFT checks pass. Rational character block counts are 2 at n=19, 3 at n=23, and 2 at n=131; the degree-two full-coordinate modules have 1,654, 2,416, and 77,422 columns respectively. | Structural route remains open. The actual barrel Macaulay operator and its F4 cost have not been measured. |
| G3 | [Bounded matrix receipt](results/g3_degree4_complete.json): 2,008,919/2,017,933 N41 S6 rows, 65,376,467 nonzeros, at least 12,008,153 distinct active columns, p95 5 and max 14,995 nonzeros/row, 1.43 GB peak RSS. The 12-million-column cap stopped 9,014 rows short of completion. [Current-source smoke](results/g3_smoke_current.json) and [interrupted full-run record](results/g3_all_rows_interrupted.json) are retained. | Sparse support avoids the impossible dense representation for the observed prefix, but full active-column count, solving degree, and block Wiedemann completion remain unknown. |
| G4 | [Final N19 receipt](results/g4_final_current.json): 7 mixed-field variables versus 25 Boolean variables; 5 of 64 leaf assignments have a field-rational intermediate, while 7 have an algebraic-closure intermediate. Mixed Sage Gröbner completed; Boolean msolve F4 completed. | An unconstrained mixed intermediate changes the solution set. The two runtimes use different engines on a contended host and do not establish an F4 gain. |
| A1 | [Final N53 closure receipt](results/a1_final.json): 21 multipliers up to sign at norm ≤16 collapse to 10 classes after existing sign/Frobenius folding. A 600-point prefix has 6 folded columns; its closure has 60, from 60 representative image operations. | The claimed 19-fold independent multiplier gain is unavailable on this subgroup under the existing folding. The proposed K=600 relation/rank test remains unrun. |
| A2 | [Final matched N23 receipt](results/a2_final.json): both bases have 230 usable points and five folded columns. On the same 16 subgroup points, three-summand coverage was 8/16 for cyclotomic weight-three and 11/16 for normal weight-two; Wilson 95% intervals are 0.28–0.72 and 0.44–0.86. None of the 1,081 weight-two sums satisfy the n=23 analogue `x^47=1`; none of those or the 16,215 weight-three sums satisfy `x^263=1`. | No coverage advantage is established. The proposed root-of-unity equation does not encode membership in the sparse-sum family. |
| N1 | [Final 256-sample receipt](results/n1_final_current_retry.json): all projected planted S3 identities are valid, and 0/256 lift to exact identities in `F₂[Z/47]` under the declared 23-dimensional section. | This direct section fails its stated cheap falsifier. Other sections or a kernel-solving lift are separate proposals. |

The G3 bounded receipt was produced by an earlier revision of the same row
builder; it retains that source hash. The current source uses a cheaper row
order and exact singleton-row shortcut. Repeated complete passes were
interrupted under shared-host contention, so the 9,014 unprocessed rows and
full active-column count are explicitly unknown. The Boolean sparse matrix
primitives have no block Wiedemann solver, and G2 has no transformed F4
backend. These are implementation boundaries, not inferred negative speedup
results.

The final G1, G2, G4, A1, A2, and N1 receipts all hash the same current
`sage_probes.py` source. Historical development receipts, censored runs, and
solver inputs remain in `results/`; use the linked final receipts for the
findings above. The one-target IC online and paired rho metrics remain
unknown for every idea.
