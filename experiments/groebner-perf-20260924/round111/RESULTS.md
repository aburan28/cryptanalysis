# Results and next steps

Local API validation used source `7deb8ba7` with the existing source-matched optimized and UBSan round108/110 builds. All seven API test groups, 26 complete-query records and twelve artifact mutation controls passed. The independent native-free audit matched every returned proof, basis and deterministic work counter to the frozen round110 reference: 20 algebra certifications, 18 curve replays and six inconclusive records. No numerical worker failed. Ten synthetic CI publication-envelope corruption controls also passed; those controls do not constitute a real CI run.

The initial validation (`leased-seeded-validation-v1`, source `bafabc1b`) remains a failed audit record. Its 26 numerical workers completed, but the comparator incorrectly demanded equality of elapsed-time fields. The corrected comparator excludes only those elapsed-time fields and checks all deterministic certificate counters. The successful follow-up is `leased-seeded-validation-v2`.

Profiling froze source `e73a5b8c052bda618d4415141d742ac18f93992b`: 26 warmups and 104 observations, four pairs per case in AB/BA/BA/AB order. All 130 records matched the independently audited reference; 100 were algebra-certified, 90 replayed on the curve, and 30 remained inconclusive. All rows are retained. Native kernels and the query implementation were unchanged between validation and profiling.

CPU-only exploratory medians ± median absolute deviation (milliseconds; four observations per interface):

| Frozen case | Round110 diagnostic controller | Leased query API | Algebra outcome |
|---|---:|---:|---|
| pdp-6-seed-1 | 1.499 ± 0.034 | 2.555 ± 0.099 | certified |
| pdp-6-seed-3 | 1.800 ± 0.009 | 3.056 ± 0.031 | certified |
| planted-dense-mq-12 | 3.661 ± 0.207 | 2.424 ± 0.052 | certified |
| pdp-9-seed-1 | 7.480 ± 0.186 | 8.428 ± 0.309 | certified |
| pdp-9-seed-2 | 6.493 ± 0.183 | 7.266 ± 0.115 | certified |
| pdp-9-seed-3 | 6.956 ± 0.345 | 7.852 ± 0.148 | certified |
| pdp-9-seed-4 | 5.488 ± 0.200 | 6.112 ± 0.029 | certified |
| pdp-9-seed-5 | 7.240 ± 0.160 | 8.712 ± 0.120 | certified |
| pdp-12-seed-1 | 124.346 ± 1.515 | 126.167 ± 0.361 | inconclusive |
| pdp-12-seed-2 | 126.165 ± 0.478 | 126.990 ± 0.850 | inconclusive |
| pdp-12-seed-3 | 118.084 ± 17.568 | 75.328 ± 0.728 | certified |
| pdp-12-seed-4 | 110.669 ± 15.965 | 70.414 ± 0.328 | certified |
| pdp-12-seed-5 | 129.441 ± 0.882 | 129.924 ± 0.587 | inconclusive |

These interfaces intentionally differ: the diagnostic controller exports Python proof and continuation graphs, whereas the API returns owned binary proof bytes. The API adapter also performs an additional independent current-equation/curve replay. Small-case regressions are retained and are not evidence of a native-kernel regression. No host-level CPU isolation receipt was available, so every qualified speedup and aggregate speedup remains unknown/null. Do not combine these numbers with earlier 18-variable verifier timings or promote a cross-round ratio.

On `pdp-12-seed-3` and `pdp-12-seed-4`, phase medians inside the API were:

| Exclusive phase | Seed 3 (ms) | Seed 4 (ms) |
|---|---:|---:|
| Matrix producer | 19.874 | 19.563 |
| Native continuation, including F4 and composition | 36.849 | 30.596 |
| Independent native verification | 11.189 | 12.125 |
| Owned proof copy | 0.138 | 0.189 |

Per-call phase values sum exactly to that call’s API wall time; medians of different phases need not sum to the median wall time. Complete-query timing additionally includes fresh coefficient descent, extraction, equation checks, both curve replays and lease teardown. The three inconclusive hard cases spent roughly 105–108 ms in fresh F4 after the matrix attempt exhausted its budget.

Next steps, in order:

1. Test parity compression before the redundant matrix proof-pruning passes. Three hard cases currently discard their matrix result at the parity-work cap. Preserving those candidates may enable seeded completion. This is an unimplemented hypothesis; preserve every failed attempt and prove the compressed proof is smaller than the ordinary retained proof.
2. Split native continuation timing into input preparation, F4 and composition before choosing the next kernel change. Keep the full-query boundary and existing deterministic work accounting.
3. Repeat an agreed API comparison on the isolated Linux benchmark service, with frozen sources, paired inputs and all required host receipts. This is required before a controlled CPU speedup claim.
4. Revisit single-query GPU execution after the matrix boundary is stable. Include transfers, conversion, launch and synchronization; keep the CPU route until a verified full query wins.
5. Keep structural F6 hypotheses separate from engineering improvements. None of this work establishes a new asymptotic algorithm or the world’s fastest implementation.

The content-addressed `results.tar.gz` preserves both local validation runs, the paired profiling records, source/build receipts and raw binaries, native-free audits, publication controls, and the archiving recipe. `archive.json` binds the archive digest and verifies lossless reconstruction.
