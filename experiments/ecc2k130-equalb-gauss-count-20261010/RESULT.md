# Two Gaussian matrices reduce sampled RSS in both equal-B source formulas

On the frozen ECC2K-130 ordinary public query zero, lowering
CryptoMiniSat's selected Gaussian matrices from five to two reduced sampled
peak RSS in **both** preregistered repetitions of both exact six-summand
formulas. Normal4 two/five ratios were 0.695306 and 0.473021; W24 ratios
were 0.613987 and 0.524714. All eight solver cells recovered their
configured number of matrices, entered live search, and reached the
70-second external guard with `BOUNDED_UNKNOWN`. The archived XCNFs, input,
binary, flags, stdout/stderr, and process receipts pass independent audits.

## Frozen source and measured cells

The source curve is `EC1N131Ckb1h136f03e58c98` over the polynomial-basis
field `GF(2^131)` modulo `t^131+t^13+t^2+t+1`; the prime subgroup order is
`680564733841876926932320129493409985129`. Each policy has
`B=11,743,888` distinct subgroup-usable base points. Both formulas use the
same frozen ordinary Q0 point, four exact raw target lifts, six summands,
balanced S3 tree, and native-XOR representation. The normal4-counter raw
formula SHA-256 is `21b4c7c292fd1441f127428927fb6cf6c51849e279d97e72adbbd95343048d79`;
the W24-balanced raw formula SHA-256 is
`f71601554772d6805b364638bc25fce1a23c96b0df65f4b9fd8a2dedd5f45e3a`.

| Run | Formula | Matrices | Wall s | Peak sampled RSS MiB | Recovered matrices | Live restart rows | Printed elimination activity |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- |
| R1 | normal4 | 5 | 70.243 | 1,007.672 | `[5]` | 183 | summary absent |
| R1 | normal4 | 2 | 70.186 | 700.641 | `[2]` | 182 | summary absent |
| R1 | W24 | 2 | 70.117 | 516.344 | `[2,2]` | 200 | `1709`, `100K` calls |
| R1 | W24 | 5 | 70.077 | 840.969 | `[5]` | 174 | summary absent |
| R2 | normal4 | 5 | 70.169 | 886.688 | `[5]` | 134 | summary absent |
| R2 | normal4 | 2 | 70.177 | 419.422 | `[2]` | 117 | summary absent |
| R2 | W24 | 2 | 70.056 | 403.062 | `[2]` | 111 | summary absent |
| R2 | W24 | 5 | 70.252 | 768.156 | `[5]` | 119 | summary absent |

Every cell printed a selected 8,262-by-13,084 matrix. The R1 W24/two
transcript also printed nonzero Gaussian elimination calls, establishing
activity for that formula. The other seven cells were externally killed
before such a summary; their elimination-call activity is **unknown**. This
is why the full [repeat gate](REPEAT.md), which requires observed activity
for each two-matrix formula, remains unresolved despite both memory ratios
passing in both repetitions. A selected matrix and live restart rows alone
are insufficient evidence of actual elimination calls.

The [R1 audit](runs/R1/audit.json) and [R2 audit](runs/R2/audit.json)
independently recompute compressed/raw formula hashes, transcript hashes,
solver flags and source identity, matrix counts and dimensions, restart
rows, process guards, and status. `PASS_EVIDENCE_BINDING` means those records
are internally consistent; it does not mean a relation was found. The
[manifest](manifest.json) and `manifest.py --verify` bind the evidence files
and exact audit/runner sources. R1's initial local audit conflated a missing
solver summary with zero elimination calls; the corrected archived audit
records `null`, with raw transcripts unchanged. R2 was frozen in `REPEAT.md`
and pushed before that repetition began.

## Decision and next experiment

The observed sampled-memory reduction supports a longer, separately frozen
**single-Q0 normal4/two** run with the same XCNF and pinned binary. Extend
the external guard enough to obtain a solver summary or a verified relation,
while preserving a complete five-matrix control and the 4-GiB cap. The
held-out 16/256-query prefixes stay unopened until a relation-producing PDP
policy is independently replayed or a further policy change is justified.
No verified relation or novel matrix row was emitted by these eight cells;
the final relation matrix, target descent, and same-point rho comparison
remain future pipeline stages. `candidate_id` remains `null`.

The one-thread solver used `--maxtime=60`, a 70-second external wall guard,
and a sampled 4-GiB RSS guard. Formula decompression and hash checks preceded
each solver interval. The host has no CPU-isolation receipt, so elapsed-time
and RSS comparisons are exploratory stage measurements. The numerator and
denominator of each RSS ratio are the paired cells in the same repetition;
neither timing nor memory here is a one-target online IC speedup.
