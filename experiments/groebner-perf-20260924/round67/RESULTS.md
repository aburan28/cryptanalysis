# Producer transform: physical Apple Metal controls and exploratory timings

Source `0e2cf0ee3b06efc759830e7d0e99039b0e8207d7` passed the complete
standalone experiment on a physical Apple M4 Pro, 14 physical/logical CPU
cores, 48 GiB RAM, macOS ARM64. This is a transform-stage diagnostic. It
does not yet integrate the new kernel into complete polynomial queries.

The ordinary host was contended: the recorded load averages at the panel
boundaries were approximately 17.11, 23.37 and 26.19. There is no host-level
isolation receipt. All timings remain exploratory, `timing_eligible` is
false, and aggregate speedup remains unknown. These results do not establish
a controlled CPU/GPU crossover or justify automatic GPU dispatch.

## Exact validation

- Optimized Metal: 474 exact shape/pattern/mode controls passed.
- UBSan Metal: the same 474 controls passed.
- Optimized portable CPU/unavailable backend: 474 controls passed.
- UBSan portable CPU/unavailable backend: 474 controls passed.
- All 342 retained panel rows passed exact full-output comparison: 324
  timed observations and 18 explicitly labeled warmups, across both builds.
- The retained artifact audit verified 19 source/native/input bindings.
- Five deliberately corrupted audit records were rejected: a promoted timing
  flag, a stale source binding, a wrong copied byte count, a false summary
  median, and a changed workload manifest with its enclosing hash updated.

The controls span 1–20 fixed variables, irregular strides 2–56, sparse,
dense and zero coefficients, the full 64 MiB limit, fresh reuse, involution,
invalid modes/extents/pointers, and reset counters after failure. Small cases
are also checked against direct subset sums. Larger cases use a separate
feature-major, descending-bit oracle. UBSan covers host code; GPU correctness
comes from exact output comparisons, not from GPU sanitizer instrumentation.

One earlier build failed because the test used a C++20 structured-binding
capture under the required C++17 mode. It produced no measurements. The
test was corrected before this frozen source was built; the original failure
log is retained under `results/`.

## Transform-only panel

Optimized-build medians, in milliseconds, with 18 observations per arm and
case. All six permutations of arm order repeat three times. The GPU interval
includes full input copy, encoding, command submission and completion wait,
and full output copy. Loading/scattering the ANF, context/allocation setup,
and subsequent exact output comparison are outside every arm's interval.
The latter checks are timed separately. This is not complete-query timing.

| Frozen input | Fixed variables × feature stride | CPU | Metal stagewise | Metal tiled |
| --- | ---: | ---: | ---: | ---: |
| `n31-m3-ell6-seed101` (18 total variables) | 12 × 22 | 0.074896 | 0.158750 | 0.151813 |
| `n31-m3-ell8-seed201` (24 total variables) | 16 × 37 | 2.174063 | 1.369980 | 1.242521 |
| `n31-m3-ell9-seed201` (27 total variables) | 18 × 46 | 16.244709 | 7.701562 | 6.682604 |

The smallest case favors the CPU in these observations. The larger cases
support testing an explicit GPU integration. The largest tiled transform
dispatches 15 kernels, compared with 18 in the stagewise variant. It copies
48,234,496 bytes in and the same number out. Its nested median device time
is 4.9666 ms; copy-in and copy-out medians are 0.7728 and 0.7511 ms. Nested
or separate medians must not be summed into a new total.

Paired tiled-minus-CPU differences, in milliseconds, retain conditional
descriptive uncertainty:

| Input variables | Median paired difference | Descriptive 95% interval |
| ---: | ---: | ---: |
| 18 | +0.076667 | [+0.073104, +0.082125] |
| 24 | −0.927688 | [−0.947937, −0.908042] |
| 27 | −9.531542 | [−9.608292, −9.429793] |

These are percentile intervals from 10,000 resamples of each arm's 18 paired
differences, with deterministic seed 670051. They describe the retained
shared-host observations; they do not account for uncontrolled contention
or qualify a speedup claim. Sanitized-build results are retained as
correctness diagnostics and are excluded from this performance table.

## Integration decision

Proceed to an opt-in producer integration on a separate source snapshot:

1. Use the existing producer Metal input buffer for the transform and the
   later quadratic projection, avoiding a second full upload of the same
   current invocation's transformed coefficients.
2. Preserve the post-transform CPU symmetry guard and host proof/fallback
   paths initially. Every invocation still scatters fresh original-ANF data,
   copies back the transformed table, and receives a new independent check.
3. Bind reuse to a single invocation. Invalidate the device-table state on
   errors and configuration changes, and test stale and failed calls.
4. Compare complete query results, proof bytes, failure paths, logical
   counters and independently replayed original-ANF identities against the
   unchanged round66 checker before collecting full-query diagnostics.
5. Charge all conversion, copies, synchronization, solving and verification.
   Keep CPU defaults until a complete-query comparison and the required
   isolation evidence support a dispatch decision.

The standalone result does not predict another twofold complete-query gain.
The rest of the producer and independent checker still dominate substantial
parts of the query. No new F4/F5/F6 asymptotic result, global speed ranking,
or verified one-target IC/rho result follows from this experiment.

## Retained evidence

`results/report.json.gz` contains every raw row, source/native hash, hardware
record, load observation and failure status. The CSV, setup logs, plan,
frozen original-ANF binary inputs, native build receipt, audit, mutation
checks, and descriptive summary are also committed in `results/`.

The full local evidence, including native binaries and generated shader, is
at `/Volumes/SSD990/llm/tmp/cryptanalysis-groebner-recovery-20261004/producer-transform-kernel-v1`.
`results/retained-artifacts.json.gz` indexes every retained file by size and
SHA-256. Native binaries are not committed to Git. The dedicated CI workflow
rebuilds on Linux/macOS, records actual availability, runs portable controls
and available GPU diagnostics, audits the artifacts, and retains them for
14 days. A hosted build or an unavailable GPU is not a physical GPU validation.
