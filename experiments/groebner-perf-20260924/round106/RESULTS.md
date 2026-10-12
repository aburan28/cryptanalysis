# Minimal-row back substitution: frozen evidence

The optimized and UBSan controls and the complete diagnostic panel pass
independent algebra, exact producer-model, ownership and artifact audits.
The retained bases and verified coverage are unchanged. The candidate removes
most backward row XORs on these controls, while forward elimination remains.
All wall times below are exploratory on an unisolated Apple ARM64 host;
qualified, aggregate and IC online speedups are null.

## Complete-query diagnostic observations

Milliseconds, median ± median absolute deviation, four observations per cell.
One preceding warmup is excluded. F4 uses the unchanged quotient checker; both
matrix arms use the same checker and packed proof-output API. An inconclusive
cell's time includes its failed matrix attempt and F4 fallback.

| Frozen case | F4 control | All-pivot matrix | Minimal-row matrix | Matrix outcome |
| --- | ---: | ---: | ---: | --- |
| pdp-6-seed-1 | 3.798 ± 0.091 | 2.624 ± 0.045 | 2.547 ± 0.018 | verified, same basis |
| pdp-6-seed-3 | 3.404 ± 0.055 | 3.118 ± 0.089 | 3.108 ± 0.153 | verified, same basis |
| planted-dense-mq-12 | 26.616 ± 0.271 (inconclusive) | 7.534 ± 0.192 | 6.255 ± 0.112 | verified, same basis |
| pdp-9-seed-1 | 43.087 ± 0.746 (inconclusive) | 10.650 ± 0.103 | 9.633 ± 0.232 | verified, same basis |
| pdp-9-seed-2 | 39.773 ± 0.235 (inconclusive) | 9.162 ± 0.543 | 8.362 ± 0.131 | verified, same basis |
| pdp-9-seed-3 | 46.197 ± 0.256 (inconclusive) | 9.894 ± 0.088 | 8.864 ± 0.075 | verified, same basis |
| pdp-9-seed-4 | 55.176 ± 0.413 | 8.418 ± 0.213 | 7.557 ± 0.171 | verified, same basis |
| pdp-9-seed-5 | 40.291 ± 0.173 (inconclusive) | 11.216 ± 0.141 | 10.055 ± 0.138 | verified, same basis |
| pdp-12-seed-1 | 130.762 ± 0.321 (inconclusive) | 118.822 ± 0.320 (inconclusive) | 119.746 ± 0.429 (inconclusive) | both inconclusive |
| pdp-12-seed-2 | 123.326 ± 0.738 (inconclusive) | 120.170 ± 0.736 (inconclusive) | 119.212 ± 0.620 (inconclusive) | both inconclusive |
| pdp-12-seed-3 | 134.507 ± 0.741 (inconclusive) | 128.063 ± 0.837 (inconclusive) | 129.047 ± 0.633 (inconclusive) | both inconclusive |
| pdp-12-seed-4 | 128.191 ± 1.330 (inconclusive) | 117.781 ± 1.148 (inconclusive) | 119.792 ± 1.597 (inconclusive) | both inconclusive |
| pdp-12-seed-5 | 126.675 ± 1.344 (inconclusive) | 125.035 ± 0.854 (inconclusive) | 124.470 ± 0.304 (inconclusive) | both inconclusive |

No process failures occurred. All five 12-variable PDP cases remain inconclusive
under the frozen limits. The 6-variable controls show little complete-query
change despite reduced matrix work. Query times retain coefficient descent,
production, independent certification, materialization, bounded extraction,
independent equation/curve replay and lease teardown. Layout setup, artifact
serialization and optional binary-to-list proof decoding stay separately
reported. These planted controls do not estimate natural relation yield.

## Exact algorithmic diagnostics

The independent integer-row model reproduces the basis, proof graph and every
producer counter. Backward XORs do not represent complete-query operations.
The extra selection-flag initialization is included in charged producer work.

| Case | Forward XORs, both | Backward XORs, reference → candidate | Producer work, reference → candidate | Output proof nodes, reference → candidate |
| --- | ---: | ---: | ---: | ---: |
| pdp-9-seed-1 | 219,245 | 46,801 → 22 | 2,216,014 → 1,865,973 | 41,502 → 39,007 |
| pdp-9-seed-4 | 172,370 | 43,104 → 19 | 1,765,398 → 1,432,482 | 39,409 → 36,505 |
| planted-dense-mq-12 | 102,100 | 70,396 → 30 | 1,880,935 → 1,081,642 | 68,845 → 68,845 |

For the MQ12 algebra control, median native production was 3.515 → 2.076 ms,
while the unchanged checker was 3.378 → 3.510 ms. Its output proof still has
68,845 nodes. On PDP9 seed 1, native production was 5.090 → 4.072 ms and the
checker was 0.946 → 1.017 ms. These mixed phase observations are retained;
we do not infer checker regressions or promote speedup ratios from this host.

## Validation and source custody

- 88 bound source files; 22 fresh optimized/UBSan libraries; ten generated
  sources and two private polynomial resources. All nine reference generated
  files are byte-identical to round105.
- Eight unit-test groups cover exact random outputs/derivations; every small
  work, node and row budget prefix; empty/constant/repeated equations and
  coefficient limbs; 64-variable masks and word boundaries; layout ownership;
  fresh coefficients, concurrent callers and proof lifetime; incomplete
  candidate rejection; and import isolation.
- 78 controls: 38 algebra verifications, 34 PDP verifications, 40 inconclusive
  outcomes, 32 matrix verifications and 20 matrix fallbacks.
- 195 diagnostic rows, including 39 warmups: 95 algebra verifications,
  85 PDP verifications, 100 inconclusive outcomes, 80 matrix verifications and
  50 matrix fallbacks. All 19 distinct mathematical certificates pass.
- 49 altered-artifact cases are rejected, including a self-consistent forged
  proof and changed producer counters. The inherited `exact_trace_pairs`
  audit field counts matrix pairs replayed against their respective exact
  models; it does not assert equal backward traces between algorithms.
- A valid synthetic publication receipt is admitted and 17 corrupted versions
  are rejected, including coherent producer-work and quotient-map mutations
  made in both worker records and the aggregate report. Synthetic controls
  do not substitute for actual remote CI artifacts.

The first freeze, `21243d3b404c6536c32308414dfd3b4ad041c9a3`, passed build,
unit tests, all controls and the independent control audit, then the artifact
harness failed to hard-link across filesystems. Its evidence is retained.
Freeze `cc6d9864ef92d027aab9d55579b7ed2d3da64a6a` changes only that temporary
directory placement. The complete validation restarted under this freeze;
no diagnostic timing had run in the first attempt and no selected timing cells
were rerun. The numerical kernel is identical in both freezes.

The content-addressed archive retains both validation attempts, full raw rows,
proofs, source/native receipts, logs and the independent publication-control
receipt. See `archive.json` for its hash and exact-byte verification. Archived
binaries are evidence only; portability requires a fresh build on each host.

## Next bounded hypothesis

For these Macaulay producers, every multiplication leaf names an original
input equation and one layout multiplier. A potential next experiment can
propagate output parity masks backward through XOR nodes, then emit short
parity sums of those original multiples. It must charge the entire transform,
cap output count and metadata, preserve a fallback, and independently certify
its regenerated graph. This is an unimplemented proposal, not a measured gain
or a new general Gröbner algorithm. Forward elimination is the next matrix
kernel target after proof costs are measured again. GPU routing stays opt-in
until a matched complete single-query run, including conversion and transfer,
shows a benefit on physical hardware.
