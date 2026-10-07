# Proof-value lifetime results

Last-use reclamation lowers simultaneous proof-term storage on successful
certificates while preserving their bases, proofs and underlying arithmetic.
Logical planning work is charged separately. The full frozen panel accepts the
same inputs under all three tested policies; difficult dense-MQ cells remain
inconclusive. Timing is mixed and noisy, so no qualified speedup or default
promotion is claimed.

The numerical source is `d31974ea26f35c2d9cea2494de255a31bc315dc3`.
The CI/audit source `690eb6b6993617e47fed39ef1452baae83b8373a` changes only
`audit.py` and `test_artifact.py`, adding independent exact lifetime reconstruction
and two additional corruption cases. All 42 source snapshots are retained;
generated native sources are identical across the two validations. Original
controls and diagnostics also pass the strengthened audit. No diagnostic panel
was repeated after the audit change.

## Logical storage and resource semantics

These exact term counts are independent of the exploratory wall times. They
exclude original equations, basis storage, allocator buckets, reduction scratch,
and the array of node objects. The recorded metadata is an additional four-byte
use counter for every proof node. They must not be described as process RSS.

| Successful input 0 | Producer | Cumulative proof terms | Peak live proof terms | Use-count bytes |
| --- | --- | ---: | ---: | ---: |
| triangular-64 | F4 | 5152 | 158 | 8320 |
| triangular-64 | Macaulay | 248 | 156 | 508 |
| pair-products-21 | F4 | 77 | 39 | 164 |
| pair-products-21 | Macaulay | 57 | 31 | 124 |
| random-8-budget-control | F4 | 56653 | 1813 | 12012 |

Every successful release-mode call ends with zero retained live values, after
checking its outputs. Peak live terms include a newly built result before its
parent values are released. Intermediate arithmetic allocates that result before
checking its size, so this is not an allocation-preflight or process-memory cap.
The cumulative counter keeps its original meaning in every mode.

An explicit 64-variable control contains 1025 nodes (1024 identity multiplications) and
materializes 65600 terms cumulatively. Its peak live demand is 128 terms.
`release-live` verifies it at a 128-term limit; baseline and cumulative-release
correctly exhaust that cumulative limit. This demonstrates a changed resource
policy on an easy redundant proof, not a high-regularity solve or speedup at an
equivalent limit. Shared children, duplicate XOR operands, unused nodes and pinned
output references are separately checked by a Python lifetime simulator.

## Complete-query observations

The 14 families contain 28 fresh systems. Eight arms compare F4 and reused
Macaulay under baseline, cumulative-release and live-release, plus the existing
bounded signature and evaluation comparators. Every algebra arm uses
completion-first certification. Two warmup orders precede eight balanced
observation orders. Layout/packing setup stays outside the algebra interval;
producer work, all checking/fallback and basis/proof export stay inside it.

Median ± median absolute deviation, milliseconds, of eight observations on the
shared Apple host. Host-wide isolation is unverified. The table intentionally
retains both apparent improvements and regressions. All qualified/aggregate/
online speedups remain null.

| Input 0 / producer | Baseline | Release, cumulative limit | Release, live limit | Outcome |
| --- | ---: | ---: | ---: | --- |
| triangular-64 / F4 | 3.0814 ± 0.7943 | 3.6240 ± 1.1825 | 3.1552 ± 0.8150 | Verified |
| triangular-64 / Macaulay | 0.2465 ± 0.0579 | 0.1897 ± 0.0288 | 0.1576 ± 0.0141 | Verified |
| pair-products-21 / F4 | 0.0613 ± 0.0014 | 0.0591 ± 0.0017 | 0.0639 ± 0.0035 | Verified |
| pair-products-21 / Macaulay | 0.0801 ± 0.0019 | 0.0761 ± 0.0020 | 0.0789 ± 0.0026 | Verified |
| random-8 / F4 | 14.5957 ± 2.1398 | 10.8103 ± 1.3681 | 10.2242 ± 1.1801 | Verified |
| dense-MQ-16 / Macaulay | 27.3266 ± 3.3944 | 32.3213 ± 6.5600 | 27.6054 ± 4.6180 | Inconclusive |

Early dense-MQ rejections perform no derivation replay, so liveness has no storage
benefit on that path. Its timing variation does not establish an algorithmic gain.
Successful F4 and Macaulay arithmetic counters match baseline after subtracting
the explicit `nodes + outputs` planning charge. Deallocation and reference-count
bookkeeping cost wall time and are not calibrated hardware-operation estimates.
All 224 input/arm cells and their observations remain in `results/summary.json`.

The control panel has 448 calls: 316 verified, 44 unsupported and 88 other
unsuccessful. The diagnostic panel has 2240 calls (448 warmups, 1792 observations):
1580 verified, 220 unsupported and 440 other unsuccessful. All three matrix arms
accept the same 20 of 28 unique inputs directly. Audits require exact producer
traces and successful arithmetic parity across 224/1120 control/diagnostic pairs,
and independently check 168/840 accepted lifetimes. Fifty-nine distinct
mathematical outputs pass the independent algebraic/oracle checks.

## Validation and publication

Fifteen optimized/UBSan groups pass, including exact instrumented-baseline
behavior, all small work boundaries, live/cumulative retention thresholds,
independent lifetime simulation, malformed unused nodes and output references,
96 concurrent checker calls, and the nine inherited Macaulay groups under both
release policies (192 small full-multiplier comparisons and 96 threaded calls).
The initial development run passed. The frozen v1 validation passed all controls,
30 artifact corruptions and the single diagnostic panel. The v2 audit-only
validation passed the same controls and 32 artifact corruptions, including
understated peak memory. Twelve synthetic publication corruptions are also
rejected; synthetic controls are not evidence of hosted CI.

The old sequential publishers stopped at their observation bound. PR345 later
merged on an advanced base, so its original tested-tree receipt cannot simply be
reused. Rounds92–94 have no runtime dependency on the pending GPU rounds70–90:
they are being published together directly against the current base. Every bound
source is checked byte-for-byte after this publication transfer. The PR must pass
full CI and six source-bound push/PR workflow audits (twelve platform artifacts)
before the authorized merge. Older round92/93 documents retain their historical
queue plan; this paragraph supersedes that plan for these three rounds.
