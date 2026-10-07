# Frozen leased-Macaulay results

The compact adapter is correct on the frozen panel and expands completion at the fixed producer budget. It is not ready to replace F4 for speed: the larger matrix proofs substantially increase independent verification time. The default producer is unchanged.

Source snapshot: `d238cd41ebed06f34d9d3c72c08396769dba3a84`. These are local macOS ARM64, CPU-only diagnostics without a host-isolation receipt. Every speedup field remains null. Planted PDP controls do not measure natural relation yield.

## Complete-query observations

Median ± median absolute deviation in milliseconds; four observations per arm, one excluded warmup. Every query includes fresh coefficient descent, independent certification, materialized proof, bounded extraction, independent equations/curve replay and lease teardown. Symbolic setup is outside the reused arms. The fresh degree-two arm is an explicit setup-inside-query ablation.

| Frozen control | Original F4 | Reused degree two | Reused degree three | Outcome |
| --- | ---: | ---: | ---: | --- |
| pdp-6-seed-1 | 4.289 ± 0.027 | 3.466 ± 0.149 | 3.434 ± 0.066 | solved; solved; solved |
| pdp-6-seed-3 | 4.118 ± 0.141 | 4.094 ± 0.062 | 4.081 ± 0.102 | solved; solved; solved |
| planted-dense-mq-12 | 25.986 ± 0.201 | 521.729 ± 4.832 | 52.768 ± 0.218 | inconclusive; gb; inconclusive |
| pdp-9-seed-1 | 42.224 ± 0.507 | 287.799 ± 0.943 | 394.711 ± 0.347 | inconclusive; solved; solved |
| pdp-9-seed-2 | 39.666 ± 0.256 | 304.395 ± 4.223 | 384.072 ± 1.993 | inconclusive; solved; solved |
| pdp-9-seed-3 | 45.075 ± 0.458 | 304.833 ± 1.931 | 402.855 ± 0.584 | inconclusive; solved; solved |
| pdp-9-seed-4 | 82.997 ± 0.032 | 271.464 ± 0.536 | 344.291 ± 0.657 | solved; solved; solved |
| pdp-9-seed-5 | 40.342 ± 0.146 | 310.170 ± 12.168 | 440.093 ± 11.040 | inconclusive; solved; solved |
| pdp-12-seed-1 | 129.741 ± 0.035 | 120.913 ± 1.264 | 130.059 ± 1.373 | inconclusive; inconclusive; inconclusive |
| pdp-12-seed-2 | 124.309 ± 1.173 | 121.057 ± 0.859 | 126.289 ± 1.110 | inconclusive; inconclusive; inconclusive |
| pdp-12-seed-3 | 136.234 ± 0.452 | 129.846 ± 0.574 | 135.658 ± 0.411 | inconclusive; inconclusive; inconclusive |
| pdp-12-seed-4 | 125.341 ± 0.962 | 119.401 ± 3.318 | 126.474 ± 0.370 | inconclusive; inconclusive; inconclusive |
| pdp-12-seed-5 | 127.709 ± 0.180 | 124.163 ± 1.525 | 127.867 ± 1.033 | inconclusive; inconclusive; inconclusive |

`inconclusive` timings stop at the fixed work limit and are not successful solve times. Their shorter duration does not make them faster solvers. Degree-three twelve-variable PDP attempts hit the predeclared matrix row limit; their fully charged fallback remains inconclusive. All statuses and individual observations are retained in the archive.

## Where the time moved

For the completed nine-variable seed-four control, original F4 took 82.997 ± 0.032 ms per complete query. The reused degree-two path took 271.464 ± 0.536 ms. Native producer medians were 47.786 and 4.118 ms, respectively, while independent checker medians were 28.137 and 253.528 ms. These stage medians are diagnostic and need not sum exactly to the median complete query.

The F4 proof uses 1,408,433 checker work units; the degree-two matrix proof uses 10,193,643. Producer work counters are 75,513,824 and 1,765,398, but count different algorithmic operations and are not an instruction-count speedup. This result directs the next experiment toward reducing independent proof-replay cost, rather than selecting an algorithm on producer time alone.

The degree-two path certifies all five nine-variable planted PDP controls and the dense twelve-variable MQ control. F4 certifies one of those five PDP controls and remains inconclusive on MQ at 80 million work units. All five twelve-variable PDP controls remain inconclusive in every arm.

## Validation

Optimized and UBSan controls: 104 calls, 52 certified algebra results, 48 equation/curve-verified PDP results, 52 inconclusive results, and no external process failures.

Diagnostics including warmups: 260 calls, 130 certified algebra results, 120 verified PDP results, 130 inconclusive results, and no external process failures. There are 18 distinct independently audited mathematical certificates.

Eight unit-test groups cover dense-reference equivalence, input permutation, malformed C inputs, coefficient limbs, 32/64-variable masks, small budget boundaries, failed matrix certification and fallback, lease invalidation, changed target coefficients, concurrent calls, proof artifacts and process deadlines. Thirty-two evidence mutations are rejected. Fifteen synthetic publication-admission mutations are rejected; those controls are not real remote-CI receipts.

The first validation attempt stopped before building because the frozen panel JSON had not been staged in the sparse checkout. Its failure is retained. The corrected source freeze completed the full predeclared panel without numerical reruns or tuning.

## Next experiment

Keep this path opt-in. Test a bounded dense representation for independent proof-DAG values on small Boolean rings, preserving an independently implemented sparse fallback, exact ideal-equality and Boolean completion checks, work limits and live-memory accounting. Pair it on the full completed nine-variable control and the newly completed matrix cases. A lower producer time is not an acceptance gate; complete independently verified query time is.

The archive also retains complete build/source hashes, native binaries, frozen inputs, raw worker records, proof blobs, failed-attempt accounting, independent audits and all observation orders. No F6 asymptotic improvement or generic GPU speedup is claimed.
