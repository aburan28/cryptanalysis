# Bounded parity witness evidence

The first frozen implementation passes all correctness, budget-prefix,
independent mathematical and artifact controls, followed by the complete
195-row diagnostic panel. Verified coverage and retained basis coefficients
are unchanged. All eight successful matrix cases select the shorter proof.
No selected timing cells were rerun.

## Complete-query observations

These CPU timings are exploratory on an unisolated Apple ARM64 host. Qualified,
aggregate and IC online speedups remain null. Values are milliseconds, median
± median absolute deviation over four observations; one preceding warmup is
excluded. An inconclusive row includes its failed matrix attempt and F4 fallback.
Both matrix arms return the same packed proof API and retain independent checks.

| Frozen case | F4 control | Minimal-row baseline | Parity candidate | Matrix outcome |
| --- | ---: | ---: | ---: | --- |
| pdp-6-seed-1 | 3.503 ± 0.064 | 2.473 ± 0.022 | 2.573 ± 0.038 | verified, same basis |
| pdp-6-seed-3 | 3.644 ± 0.182 | 3.162 ± 0.109 | 2.983 ± 0.020 | verified, same basis |
| planted-dense-mq-12 | 26.158 ± 0.293 (inconclusive) | 6.471 ± 0.073 | 3.311 ± 0.186 | verified, same basis |
| pdp-9-seed-1 | 42.078 ± 0.370 (inconclusive) | 9.020 ± 0.048 | 8.969 ± 0.226 | verified, same basis |
| pdp-9-seed-2 | 39.077 ± 0.200 (inconclusive) | 8.583 ± 0.110 | 7.961 ± 0.084 | verified, same basis |
| pdp-9-seed-3 | 46.151 ± 0.070 (inconclusive) | 9.096 ± 0.104 | 8.219 ± 0.095 | verified, same basis |
| pdp-9-seed-4 | 54.145 ± 0.044 | 7.325 ± 0.345 | 7.076 ± 0.124 | verified, same basis |
| pdp-9-seed-5 | 39.356 ± 0.420 (inconclusive) | 9.792 ± 0.209 | 9.392 ± 0.289 | verified, same basis |
| pdp-12-seed-1 | 129.517 ± 0.835 (inconclusive) | 119.363 ± 0.477 (inconclusive) | 118.936 ± 1.602 (inconclusive) | both inconclusive |
| pdp-12-seed-2 | 123.551 ± 0.210 (inconclusive) | 119.857 ± 1.236 (inconclusive) | 121.703 ± 0.347 (inconclusive) | both inconclusive |
| pdp-12-seed-3 | 135.343 ± 0.906 (inconclusive) | 128.731 ± 0.308 (inconclusive) | 129.266 ± 1.483 (inconclusive) | both inconclusive |
| pdp-12-seed-4 | 125.976 ± 0.850 (inconclusive) | 114.361 ± 0.528 (inconclusive) | 115.667 ± 0.649 (inconclusive) | both inconclusive |
| pdp-12-seed-5 | 126.859 ± 0.379 (inconclusive) | 124.970 ± 1.943 (inconclusive) | 124.702 ± 1.498 (inconclusive) | both inconclusive |

The PDP6 seed-1 median increases, and PDP9 seed 1 changes little. All five PDP12
cases remain inconclusive under the frozen limits. The mixed complete-query
results are retained even though every selected replacement has fewer nodes.
No CPU speedup ratio is promoted and no default routing policy changes.

For MQ12, the checker median is 3.359 → 0.361 ms, while native production is
2.477 → 2.580 ms. The parity transform's nested median is 0.281 ms. These
separately summarized medians need not add. For PDP9 seed 1, the checker is
0.930 → 0.433 ms and production is 3.755 → 4.135 ms, with a 0.182 ms nested
transform. This is why a much shorter witness need not produce a comparable
complete-query improvement on every workload.

## Proof size, memory and charged work

The native-free matrix/parity model reconstructs each emitted graph and every
producer/transform counter. The unchanged mathematical verifier checks the
original ideal independently. Checker work below is its recorded software
charge, not a calibrated instruction count. The dense proof-value peak covers
its metadata and owned buffers only; process RSS and transform metadata have
separate scopes.

| Case | Proof nodes, before → after | Checker charge, before → after | Dense proof-value peak bytes, before → after | Added transform charge | Transform metadata bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| pdp-9-seed-1 | 39,007 → 2,660 | 11,802,289 → 755,891 | 1,432,412 → 97,040 | 160,185 | 312,220 |
| pdp-9-seed-4 | 36,505 → 2,544 | 10,118,386 → 698,786 | 1,342,020 → 92,864 | 148,867 | 292,204 |
| planted-dense-mq-12 | 68,845 → 5,582 | 32,315,828 → 2,729,223 | 2,865,492 → 213,240 | 285,801 | 550,856 |

The transformation runs fresh for each query after ordinary pruning. Its work
and allocations are inside the original producer interval. Layout setup,
artifact serialization and optional binary-to-list proof decoding remain
separate. Full timings retain fresh coefficient descent, independent
certification, proof materialization, bounded extraction, independent
equations/curve replay and lease teardown. These planted controls do not
estimate natural relation yield or complete an unknown-target IC solve.

## Validation and custody

- Source freeze: `317284c267474becd51cf9e8aa48c66207509f53`.
- 95 bound sources, 24 optimized/UBSan libraries, eleven generated files and
  two private polynomial resources. All ten reference generated files are
  byte-identical to round106.
- Eleven unit-test groups cover exact random bases/proofs, every small work/
  node/row budget prefix, repeated/empty equations and coefficient limbs,
  large variable masks, disabled mode and exact metadata bounds, the 64-output
  bit and 66-output fallback, layout ownership, concurrent fresh coefficients,
  proof lifetime, incomplete candidates, forged witnesses and import scope.
- 78 controls: 38 algebra verifications, 34 PDP verifications, 40 inconclusive
  outcomes, 32 matrix verifications and 20 matrix fallbacks.
- 195 diagnostic rows including 39 warmups: 95 algebra verifications, 85 PDP
  verifications, 100 inconclusive outcomes, 80 matrix verifications and 50
  matrix fallbacks. No process failure occurred. All 19 distinct certificates
  pass independently. The legacy `exact_trace_pairs` field counts paired
  queries checked against their respective models, not equal proof graphs.
- 54 corrupted-artifact cases are rejected, including a self-consistent forged
  proof and changed parity metadata, node counts, selection and work.
- A valid synthetic publication record is admitted and 19 corrupted records
  are rejected. These include coherent parity-edge, metadata-byte and producer-
  work changes in both worker records and the aggregate report.

The content-addressed archive contains the complete validation, raw rows,
proofs, bound sources/native receipts, independent publication controls, logs,
summary and untimed pre-implementation discovery. See `archive.json` for its
hash and byte-for-byte verification. Archived native binaries are evidence;
remote platforms must rebuild. Synthetic publication controls do not replace
actual CI artifacts.

## Next hypothesis

Forward elimination still constructs XOR proof nodes for rows subsequently
eliminated to zero. A bounded row-local list of reducer references could defer
witness emission until a row becomes a pivot, avoiding unused graph allocation
and later pruning. That proposal must preserve the coefficient path, explicitly
account for temporary references and changed proof-node retention, check exact
witnesses and retain every exhausted/fallback attempt. It is not implemented
or measured in this round. General degree-of-regularity, a single-query GPU
win, an isolated additional-2x result and the IC/rho gate remain open.
