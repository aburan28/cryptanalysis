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

## Follow-up implementation and results (2026-10-08)

The follow-up code adds [target-independent Macaulay layout replay, a cyclic
barrel row test, a mixed-field rationality gate, multiplier rank algebra,
cyclotomic selector enumeration, and a CRT lift](followup_probes.py), plus an
[actual N41 matrix-free operator](followup_g3.py), [N23 multiplier geometry
control](a1_geometry_followup.py), and [N53 600-column closure](a1_n53_k600_followup.py).
The [validator](validate_followup.py) checks final-source hashes and the
cross-receipt invariants. The [checked Sage runtime receipt](results/sage_runtime_info_followup.json)
was saved before the runs. These remain stage experiments with `candidate_id:
null`; no complete pipeline, one-target online time, or paired rho speedup was
measured. All local CPU timings are exploratory because the host was not
isolated.

| Lead | Final follow-up evidence | Decision at this stage |
| --- | --- | --- |
| G1 | [Layout replay](results/g1_template_followup_final.json) reproduces all fresh Macaulay rows on 16 N31 planted targets for each of m=2 and m=3. The 31-row matrices have 22 and 466 columns. First-target pivot schedules match only 1/16 and 2/16 targets. | Target-independent row and column layout is reusable, as the existing Macaulay cache already allows. This captured elimination schedule does not transfer; a genuine F4 symbolic trace and 10–100× gain remain untested. |
| G2 | [Cyclic barrel rows](results/g2_barrel_followup_final.json) at N19 and N23 rotate exactly in normal-basis coordinates, with 7,943 and 13,755 active monomials. Binary row ranks 19 and 23 equal the numbers of nonzero DFT characters. One-hot target constraints are cyclic. | The row-module symmetry is real. No degree-expanded Macaulay block reduction, F4 basis, or blockwise speedup has been demonstrated. |
| G3 | [Complete N41 S6 degree-four census](results/g3_full_rows_followup.json): 2,017,933 rows, 100,315,659 ambient squarefree columns, 247,444,987 nonzeros, median and p95 five nonzeros/row, maximum 22,299. Eight-byte sparse column indices alone require at least 1.98 GB if materialized. A [72-row operator control](results/g3_operator_followup.json) passes the `A`/`Aᵀ` bilinear identity on 190,408 actual nonzeros. | The sparse representation is implementable by streaming, but no block Wiedemann solve or solving-degree certificate exists. If degree five were needed, the same construction has 4,394,565,333 ambient columns and 116,332,393 rows before reduction. |
| G4 | [Twelve N19 m=3 planted target cells](results/g4_frobenius_followup_final.json), each with all 64 leaf assignments: 48 algebraic-closure common-root hits become 40 finite-field hits. Both `z^(2^19)+z` and the quadratic trace criterion agree with direct field-root enumeration; eight false positives are removed. | A mixed-field intermediate needs a finite-field rationality gate. Its cost in a matched mixed-field F4 solve remains unknown. Planted cells are correctness controls, not natural yield. |
| A1 | [N53 scan extension](results/a1_n53_k600_followup_final.json) uses the frozen 244-column geometry from a separate N53 artifact, extends its x-scan to 1,191, and reaches **600 seed folded columns / 63,600 usable points**. The ten norm-≤16 classes produce 6,000 folded columns / 636,000 geometric points with 6,000 representative scalar images and no folded-column collisions. The [rank transport control](results/a1_rank_followup_final.json) shows that multiplier copies add no independent equations after known log identities are imposed. In a paired [N23 one-seed-orbit toy](results/a1_geometry_n23_followup_final_v2.json), 46 to 460 usable points at one independent log column changes exact m=3 coverage from 0/16 to 13/16; Wilson 95% intervals are 0–0.19 and 0.57–0.93. | The proposed 19 independent classes and 361× linear-algebra reduction are not supported. Geometric coverage at fixed log dimension is promising; N53 natural-query PDP yield, relation rank, memory, and target recovery are unmeasured. The older 220-column retained base and this frozen 244-column geometry are different factor-base policies. |
| A2 | [Exact N23 sparse-sum encoding](results/a2_encoding_followup_final.json) maps all 1,081 weight-two and 16,215 weight-three supports to 17,296 distinct x values without collisions; no value satisfies `x^47=1` or `x^263=1`. | Support selectors give an exact membership encoding, but it uses 47 selector bits per leaf at N23. The proposed root-power degree-four membership equation is invalid; F4/WDSat solving degree remains unknown. |
| N1 | [CRT lift](results/n1_crt_followup_final.json) produces exact group-algebra S3 identities for all 256 planted field identities, whereas the prior polynomial section produces 0/256. The CRT idempotent has weight 24; mean total support weight of three lifts rises from 34.9 to 70.6. | The original zero-lift falsifier applies only to its declared sparse section. Exact lifting is always possible for these true identities, but this construction is dense and does not give an additive-combinatoric decomposition method. |

The A1 N53 extension changes the factor base and therefore cannot inherit the
candidate ID or measured costs of the frozen source. The closure point count
is geometric; its 6,000 orbit columns are tied by known multiplier log
identities to 600 seed log variables. Uniformly multiplying a relation then
scales its coefficient row after those identities are substituted, so it does
not by itself raise relation-matrix rank. A larger base can still improve PDP
coverage, as the N23 paired target control shows. The N53 K=600 natural
relation probe and rank gate in the original proposal remain open.

To replay the final checks from the repository root, use the checked launcher
for every Sage command:

```sh
./sage --runtime-info > /tmp/ic_ideas_sage_runtime_replay.json
./sage -python -m unittest discover -s experiments/ic-ideas-20261007 -p 'test_*.py'
python3 experiments/ic-ideas-20261007/validate_followup.py
```

The final receipts were written with explicit `--output` paths by the runners,
which refuse to overwrite them. Earlier `*followup.json` and
`a1_geometry_n23_followup_final.json` files are retained development receipts;
the table links the final-source receipts used by the validator.
