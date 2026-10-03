# Round 58 validation and diagnostic samples

The column-index representation passes the frozen correctness comparison.
Across 23 inputs, three representations and optimized/UBSan builds, all 138
records match round 56's `chain_filter` result, proof, integer producer and
checker counters, and pivot-selection statistics exactly. There are 60 verified
bases and 78 inconclusive work-budget results. The separate Python checker
replays all ten successful input certificates. The artifact audit checks 86
source, generated-file and binary bindings.

Five test groups additionally cover 128 random ideals, empty/unit ideals,
Boolean multiplication collisions, masks through 64 variables, all work budgets
from 0 through 512, proof-node and matrix-row limits, batch widths, both indexed
and fallback branches, and fresh calls from four threads. These pass in locally
rebuilt optimized and UBSan modes on physical Apple M4 Pro ARM64. Linux x86-64
and hosted macOS ARM64 validation are configured in the new CI workflow and
remain unverified until their actual artifacts pass independent replay.

The motivating samples use the unchanged round 56 `chain_filter` binaries.
Each sample attaches only to a bounded worker launched by the retained script.
Each worker starts with a byte-for-byte proof comparison, then checks each fresh
solve against the frozen basis and integer trace. All 794 repeated solves match.
The three dense controls exhaust their fixed work budget; they are not solves.

| Algebra input | Stack samples | In matrix reduction | In normalization | Completed fresh attempts |
| --- | ---: | ---: | ---: | ---: |
| Random, 8 variables | 6,375 | 4,176 | 983 | 212 |
| Dense planted MQ, 12 variables | 6,420 | 5,563 | 701 | 74 |
| Dense planted MQ, 16 variables | 6,333 | 3,180 | 3,007 | 288 |
| Dense planted MQ, 21 variables | 6,415 | 4,149 | 2,180 | 220 |

The table classifies each sample by its deepest recognized native frame.
Independent checking, chain handling and other frames account for the remainder.
Sampling occurred on a busy host. These are stack distributions, not measured
CPU-time fractions, query latencies, or evidence of speedup. They change which
code is worth testing: the large logical normalization charges did not imply
that normalization dominated the physical execution to the same extent.

The retained `sampling-evidence.json.gz` contains the sampling script, raw stack
reports, worker results, command lines and hash receipts. The local native
validation and build receipts are retained separately. Binaries stay outside
Git and are rebuilt by CI.

No eligible complete-query timing exists for this representation yet. The next
experiment must freeze a paired comparison with round 56 `chain_filter`, include
column conversion and independent checking in the query interval, preserve
failed attempts, and apply the existing host-load admission rule. No automatic
dispatch, GPU crossover, IC speedup, F5 speedup or asymptotic claim follows from
this correctness result.
