# N131 weight-seven frontier: supply improves while matrix work rises

Q20261010190000 sampled 250,000 distinct normal-x weight-seven supports
on `EC1N131Ckb1h6816f880945e`. **125,405 lifted to curve points**
(rate 0.50162; Wilson 95% interval 0.49966–0.50358). A separate replay
regenerated every support, classification, and the sample digest, checked
64 direct curve lifts, and independently recomputed the screen rows: `PASS`.

Extending Q1413's exact weight≤6 base under the explicit assumptions that
the sampled rationality rate transfers to all weight-seven supports and
cofactor projection creates no new collisions gives **B≈118.52 billion**
usable points and **K≈452.37 million** signed/Frobenius-folded columns.
The sampling interval translates to B≈118.08–118.96 billion and
K≈450.71–454.04 million; it does not cover projection collisions or model
error. This remains a Q proposal with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`.

| Normal-x bound | Base source | log₂ B | log₂ K | log₂ mean four-point representations per uniform target | log₂ query count if all models are used | log₂ query count if one novel row is returned per query | log₂ `4K²` touches | log₂ `8K²` touches |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ≤5 | exact Q1413 | 28.21 | 20.17 | −20.76 | ≥40.93 | ≥20.17 | 42.35 | 43.35 |
| ≤6 | exact Q1413 | 32.61 | 24.58 | −3.14 | ≥27.72 | ≥24.58 | 51.16 | 52.16 |
| ≤7 | sampled conditional | 36.79 | 28.75 | +13.56 | ≥15.19 | ≥28.75 | 59.51 | 60.51 |
| ≤8 | half-rational extrapolation | 40.75 | 32.72 | +29.41 | ≥3.32 | ≥32.72 | 67.43 | 68.43 |

The all-model column is the exact four-point-multiset supply count divided
by the subgroup target count, then by K; it is a **necessary** uniform-query
bound only when a collector can enumerate and verify every useful model.
The one-row column assumes at most one novel rank row is returned per query
and no pre-supplied rows. Under that collector law, weight seven needs at
least `2^28.75` queries, compared with `2^27.72` for weight six, even though
its relation density is much higher. Its zero-other-cost per-query ceiling
under an abstract `2^61` total is `2^32.25`, about 1.03 bits tighter than
weight six's `2^33.28`.

The final two columns are **matrix-entry touch models**, one or two sparse
Wiedemann-length passes through four entries per row. They are not a hard
lower bound across matrix algorithms and are not calibrated field-operation
counts. At weight seven they lie at `2^59.51`–`2^60.51` touches; weight eight
reaches `2^67.43`–`2^68.43`. A four-entry-per-row weight-seven matrix would
also require roughly 7.24 GB just for 32-bit column indices, before rows,
coefficients, vectors, and solver workspace. These models identify weight
seven as the only larger-base case worth a rank-yield test, with little
matrix margin under a naive implementation.

**Next experiment:** on frozen ordinary N53 and N83 queries, measure verified
decompositions returned *per query* and their incremental rank for a
weight-increased base. Charge the full enumeration search, failed attempts,
relation verification, and duplicate rows. A weight-seven N131 route needs
multiple useful rows per query or a per-query solver saving greater than
about 1.03 bits just to offset the one-row query-count increase; final
matrix and setup costs must then be added. The complete-solve `2^x` remains
unresolved until those stage rates and common operation calibration exist.
