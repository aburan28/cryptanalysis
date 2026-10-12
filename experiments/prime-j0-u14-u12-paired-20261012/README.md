# Paired U14 and split-terminal U12 scalar formats

The 4,096 frozen scalar inputs give a direct operation-count comparison of two
64 MiB complete scalar-multiplication formats. `compare.py` reconstructs both
representatives and records one row per scalar in `paired.jsonl`. It binds the
input, verification, and comparison sources by SHA-256 in `comparison.json`.
All 4,096 inputs select the same lattice representative in both formats.

| Format | Retained table | Terms | Mixed additions | Projective merges | Unit rotations | Tau maps | Declared point-work proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| U14 sector digit, one bucket | 64,314,112 B | 57,344 | 53,248 | 0 | 8,167 | 0 | 593,895 |
| U12 split terminal, three buckets | 67,108,816 B | 54,528 | 46,083 | 4,349 | 14,756 | 4,350 | 609,671 |

The inherited point-work proxy favors U14 by 15,776 units on this panel.
U14 is lower on 1,547 scalar rows, U12 on 927, and 1,622 tie. That proxy
uses one common mixed-addition weight despite different native formulas:
the current U14 evaluator uses Jacobian mixed addition (8 field multiplies,
3 squares), whereas U12 uses XYZZ mixed addition (8 multiplies, 2 squares).
It therefore cannot rank the native executables by time.

## Candidate: U14 recoding with a single XYZZ accumulator

The U14 table and its sector-digit choices can feed the existing XYZZ mixed
addition and Solinas unit-rotation formulas. This keeps U14's 64,314,112-byte
table and one-bucket path while removing one square from each current U14
mixed addition. It also avoids U12's projective bucket merges and tau maps.

Using the source formulas on the recorded nonexceptional paths, the static
limb-product model is:

| Evaluator | Generic field M+S | Solinas rotations | Modeled limb products |
| --- | ---: | ---: | ---: |
| Current U14 Jacobian | `11 * 53,248 + 8,167` | 0 | 21,380,220 |
| Current U12 XYZZ | `10 * 46,083 + 14 * 4,349 + 9 * 4,350` | 14,756 | 20,530,564 |
| Proposed U14 XYZZ | `10 * 53,248` | 8,167 | 19,357,121 |

The model assigns 36 limb products to a generic 256-bit field multiply or
square and 23 to a Solinas rotation. It excludes scalar recoding, point-table
construction, final inversion/conversion, memory behavior, and exceptional
group paths. These counts are a design screen, not native instrumentation or
wall-time measurements. The next gate is native implementation, full point
replay, then a paired run on a host that passes the isolated-benchmark preflight.

Reproduce the comparison from this checkout with
`python3 experiments/prime-j0-u14-u12-paired-20261012/compare.py --help`.
The script validates every frozen source and input digest before producing
the two result files.
