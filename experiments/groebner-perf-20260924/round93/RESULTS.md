# Completion-first certification results

The new ordering rejects incomplete 12/16-variable Macaulay candidates without
replaying or retaining their derivation values. The same candidates are accepted
under both schedules, with identical bases, proofs and successful-check counters.
All hard dense-MQ complete calls remain inconclusive under the frozen producer
limits. This is an improvement in failed-attempt cost, not a successful solve or
an asymptotic algorithm improvement. Default dispatch remains legacy.

Numerical source: `e6174c3047302f7399e0f5fa2696b68a494a1839`. The single frozen
validation builds ten optimized/UBSan libraries with 38 bound source files. It
compares unchanged round62 F4 and round92 Macaulay producers, using the unchanged
round11 checker or its generated reordered counterpart. Source generation is
hash-pinned and changes only obligation scheduling, phase bookkeeping and its
explicit schedule argument. Native sources remain frozen after observation.

## Outcomes and exact invariants

There are 14 families, 28 fresh inputs and six arms: legacy/completion-first F4,
legacy/completion-first reused Macaulay, interpreted F5B and native evaluation.
The matrix multiplier bound is one for nonlinear systems and zero for linear
systems. Layout preparation and packed fixture construction are outside the
complete algebra interval; fresh coefficients, all attempts/checks/fallbacks and
basis/proof export are inside it.

The control panel records 336 complete calls over optimized and UBSan builds:
232 verify, 44 are explicitly unsupported and 60 are otherwise unsuccessful.
Both matrix schedules accept the same 20 of 28 unique inputs directly. Six
remaining matrix proposals reject before derivation under the new schedule:
the two random-eight controls and four dense 12/16-variable controls. The two
21-variable dense candidates exhaust producer work before verification begins.
All eight fallback inputs and their costs remain recorded.

The diagnostic panel records 1344 calls: 336 warmups and 1008 observations in six
balanced orders. It contains 928 verified, 176 unsupported and 240 other
unsuccessful records. Audits require identical producer traces, answers and proofs
for all 112 control pairs and 448 diagnostic pairs. Successful checker counters
also match exactly in 84 control and 336 diagnostic pairs. Fifty-nine distinct
mathematical outputs pass independent native-free algebraic/oracle checks.

## Exploratory complete-call observations

Median ± median absolute deviation of six observations, milliseconds, on the
shared Apple host. These are descriptive timings without host-wide isolation;
all qualified, aggregate and online speedup fields remain null. The table includes
failed attempts and fallback, and does not measure a curve query or target DLP.

| Macaulay input | Legacy checking | Completion first | Complete-call outcome |
| --- | ---: | ---: | --- |
| triangular-64, input 0 | 0.1803 ± 0.0070 | 0.1650 ± 0.0129 | Verified |
| pair-products-21, input 0 | 0.0711 ± 0.0021 | 0.0698 ± 0.0030 | Verified |
| random-8, input 0 | 9.0341 ± 0.2514 | 9.2154 ± 0.3686 | Verified after fresh F4 fallback |
| dense-MQ-12, input 0 | 19.7541 ± 0.2975 | 5.5744 ± 0.1831 | Inconclusive after fallback |
| dense-MQ-12, input 1 | 20.0196 ± 0.3576 | 5.3398 ± 0.2529 | Inconclusive after fallback |
| dense-MQ-16, input 0 | 84.9464 ± 1.0261 | 22.3737 ± 0.0931 | Inconclusive after fallback |
| dense-MQ-16, input 1 | 84.8397 ± 1.1707 | 22.3316 ± 0.5421 | Inconclusive after fallback |
| dense-MQ-21, input 0 | 4.4429 ± 0.0751 | 4.3421 ± 0.0742 | Producer budget exhausted |

The optimization does not improve every observed call. The successful random-eight
fallback cell is slightly slower locally, and its F4 baseline is also slightly
slower under the new schedule. These variations stay in the evidence. Fresh F4's
successful 64-variable control has unchanged 27117 checker-work units and 2080
proof nodes; the reused matrix has unchanged 15351 units and 127 nodes.

For dense-MQ-12 input 0, proof-first checking performs 870680 logical work units
and replays 3836 nodes before finding a nonzero critical-pair remainder. The new
schedule finds that same obstruction after 372417 units and zero proof nodes.
For dense-MQ-16 input 0, the legacy path instead exhausts its retention budget
at 1999996 retained terms and 8892 replayed nodes (2866539 work units). The new
path mathematically rejects the basis at 3089760 work units with no proof replay.
Thus the 16-variable counter increases even though local elapsed time falls:
logical units are not interchangeable hardware-cost estimates. Its fallback
receives less remaining checker work, still within the original shared budget.

Separate tests independently confirm all four dense 12/16 candidates fail the
exhaustive zero-set/staircase criterion. The 16-variable change therefore yields
a definite mathematical rejection where the old order reported retention
exhaustion. It does not produce a valid basis for those inputs. The bounded
native evaluation comparator continues to solve the 12/16-variable controls;
21-variable dense MQ remains outside evaluation's declared bound and unsolved
by the tested algebraic arms. See [results/summary.json](results/summary.json)
for every arm/input cell and its raw observations.

## Validation and retained failures

Fifteen optimized/UBSan test groups pass. They cover exact original-order behavior,
accepted counter parity, every small checker-work boundary, retention thresholds,
malformed derivations after algebraic checks succeed, field/reverse/minimality
counterexamples, direct ABI corruption/recovery, 96 concurrent checker calls,
64-variable boundaries, the eight dense-candidate checks across two builds, and
all nine prior Macaulay integration groups (including 48 threaded calls and
96 exhaustive full-multiplier small-ring comparisons).

Twenty-six corrupt retained artifacts and 25 synthetic publication predicates
are rejected. These tests include omitted completion counters, changed producer
traces, forged schedules and invented early proof replay. Accepted outputs pass
an independent Python derivation/Buchberger checker; applicable small rings also
pass the independent exhaustive oracle. Artifact audits do not execute retained
native binaries.

The first development build failed after native compilation because a build-script
edit accidentally used a tuple as a file path when writing the F5B comparator.
Its failed source and log are retained. The corrected development build passed
14 groups; the frozen build adds the dense-candidate group and passes all 15.
No diagnostic observations ran before the final frozen validation. No observed
sample was replaced.

The PR coordinator waits for round92's verified merge, then requires full CI,
source-bound Linux/macOS push/PR artifact audits and unchanged tested base/head/tree
before merging. Hosted CI for this round and its merge remain pending. The local
results do not establish platform speedups or satisfy the original full-query gate.
