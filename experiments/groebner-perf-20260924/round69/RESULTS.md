# Independent multiplier GPU experiment: exact controls and stage diagnostics

The frozen source `9ec73576b00ef56c2e2b405069f28d9fab6ef293` passed the
complete experiment on 2026-10-04 on physical Apple M4 Pro hardware, 14 CPU
cores, ARM64, 48 GiB RAM. The experiment is standalone. No complete-query
checker or automatic dispatch default has changed.

## Exact validation

| Check | Result |
| --- | --- |
| Optimized physical Metal controls | 557 cells pass |
| UBSan physical Metal controls | 557 cells pass |
| Optimized portable/unavailable controls | 556 cells pass |
| UBSan portable/unavailable controls | 556 cells pass |
| Counted GPU output comparisons across the two Metal builds | 4,360 pass |
| Balanced stage observations, both builds, including warmups | All 342 pass |
| Frozen source/input bindings against Git blobs | 21 pass |
| Independent original-ANF/table/full-proof/basis replays | All 3 pass |
| Deliberately corrupted audit records | All 5 rejected |

The control cells include every residual dimension 1–10 and equation widths
1, 31, 32, 33, 63, 64, 65, 127 and 128. Exact comparisons cover every
materialized degree-zero through degree-three identity coefficient, valid
nonlinear products, dense cross-limb cancellation, a cubic-only error, mixed
valid/invalid batches, 4,096-record atomic-reduction controls, fresh repeated
calls, failures followed by recovery, and concurrent callers. The exact
64 MiB coefficient-table boundary is exercised. UBSan covers host code;
GPU arithmetic is checked by exact output comparisons.

The independent artifact audit reconstructs the full coefficient table from
the original ANF by direct superset expansion, distinct from the diagnostic's
subset transform. It checks every table coefficient, all full-proof records,
partial-certificate ranks, remaining assignments and the exact reduced Boolean
bases. The three inputs each retain their six independently recovered roots.
No retained native binary is loaded by this audit.

Audit corruption controls reject a promoted timing flag, stale source binding,
false median, changed upload count with a matching rewritten CSV hash, and a
changed workload with an updated enclosing plan hash. The unfrozen preliminary
controls are indexed separately. The fixture manifest was explicitly added
despite the repository's broad JSON ignore rule before the frozen build/run.

## Exploratory identity-stage panel

These are complete calls to the standalone identity-stage API, not complete
polynomial queries. The interval includes input validation, fresh full-table,
proof and index uploads, result initialization, encoding, submission and wait,
readback, and result accounting. The CPU comparator adapts the existing
factored/local evaluator to return the same first-failure mask for every
record. All arms process the entire selected record set.

Original-ANF reconstruction, symmetry/proof selection, context/pipeline setup
and separate exact comparisons are outside this interval. Native setup and
oracle time are retained in each stderr record. Offline Python fixture
construction is preserved by source and input hashes; it has no separate
timing receipt in this stage panel. Full-query integration must charge all
target-dependent preparation through final verification.

Optimized medians in milliseconds, with 18 observations per arm plus one
separately retained warmup. All six arm-order permutations repeat three times.

| Frozen input | Checked multiplier records | CPU factored/local | Metal per record | Metal per coefficient |
| --- | ---: | ---: | ---: | ---: |
| `n31-m3-ell6-seed101` | 0 | 0.000083 | 0.000084 | 0.000084 |
| `n31-m3-ell8-seed201` | 992 | 0.381146 | 0.618416 | 0.347667 |
| `n31-m3-ell9-seed201` | 37,768 | 15.846334 | 3.224708 | 3.875000 |

The empty case measures API overhead and issues no GPU work or copies. It
offers no substantive opportunity for this optimization. The per-record GPU
layout regresses on the medium case. On the largest case, it is the stronger
candidate despite exposing fewer GPU threads than the per-coefficient layout.
The experiment establishes these observations, not a general routing rule.

For the largest per-record GPU arm, each call uploads 51,407,008 bytes,
including the entire 48,234,496-byte independent coefficient table. Nested
medians are 0.1377 ms for validation, 0.8397 ms for copy-in, 2.2005 ms for
submission/wait, and 0.0026 ms for copy-out. Device time is nested within the
wait interval and has a 1.7875 ms median. Do not add nested or separately
summarized medians into a new total. `workspace_bytes` counts allocated Metal
buffer payloads, including the materialized-output buffer retained after
correctness setup; CPU zero means no Metal buffers, not zero CPU memory.

The per-record GPU-minus-CPU paired differences are:

| Checked records | Median difference (ms) | Conditional descriptive 95% interval (ms) |
| ---: | ---: | ---: |
| 992 | +0.236666 | [+0.216146, +0.465375] |
| 37,768 | −12.808729 | [−13.191251, −12.558938] |

The intervals use 10,000 paired percentile resamples, seed 690068. All paired
differences, including the per-coefficient and empty-input arms, are retained.
They describe uncertainty conditional on this sample and do not model
uncontrolled host effects. One-minute load was 11.326 at the sampled panel
boundaries. There is no host-isolation receipt: `timing_eligible` is false and
aggregate speedup remains unknown. Sanitized timings are retained for
correctness diagnostics and excluded from this table.

## Integration decision and remaining gates

Proceed to an explicit full-checker integration on a new source snapshot.
Retain original-ANF coefficient reconstruction, proof validation, symmetry
checks, constant checks, partial rank checks, residual enumeration and exact
basis checks. Start with the measured fresh-upload path; then evaluate reuse
of the independent checker's own transformed device buffer behind invocation
generation and ownership checks. Producer coefficients and elimination state
must never become independent verification evidence.

Integration must distinguish actual GPU work from the sequential checker's
first-failure prefix, preserve failure metadata, support serial/prepared/
overlapped checking, and pass malformed-proof and original-ANF audits. Only
then collect matched complete-query diagnostics with every copy, conversion,
wait and independent check charged. Keep CPU defaults until the full-operation
and isolation gates are met. The stage reduction is not a demonstrated
twofold full-query improvement, a new asymptotic F4/F5/F6 result, a global
speed ranking, or a verified one-target IC/rho result.

## Evidence

`results/` contains raw panel rows, run order, source/native receipts,
hardware metadata, exact-control logs, original-ANF audit, corruption tests,
conditional uncertainty and an artifact index. Full compressed proof fixtures
and their manifest are committed under `fixtures/`. Native binaries and
reconstructed table files remain in the hash-indexed local evidence at
`/Volumes/SSD990/llm/tmp/cryptanalysis-groebner-recovery-20261004/independent-multiplier-kernel-v1`.
Linux/macOS CI rebuilds native code independently, records actual backend
availability, regenerates and audits the same evidence, and retains artifacts
for 14 days. Compilation or an unavailable GPU is not physical GPU validation.
