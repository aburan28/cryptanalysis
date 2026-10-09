# Wider exact F6 separator boundary

The exact target-affine separator completed seven wider S3-chain geometries,
including a 60-variable, six-summand case. Across optimized and UBSan native
builds, all 7,168 matched target pairs and 14,336 arm executions agreed with
independently enumerated curve sums. Every satisfiable arm supplied a witness
that passed both the original ANF equations and curve-point replay. The
four frozen rejection controls preserved their expected width or state cap.

The driver source was frozen at commit
`3e8283eac6752cd62af15e69ec37a5929a754cb0`. Its source receipt checked
85 executed or experiment Python/C++/header files byte-for-byte against that
commit and checked both native binary receipts. The complete local output is
retained as [report.json.gz](evidence/report.json.gz) and
[journal.jsonl.gz](evidence/journal.jsonl.gz); the journal has one row per
native arm. The uncompressed journal SHA-256 is
`b948854070e411bbe4dcc3cbdbda4d6b00e489ad84b95c20d74ceac7e990c324`.
The compressed report SHA-256 is
`34c87c345403bc3cc6a7dce440b401a2710324e4c1c346a022ddc9fcce3bfb39`;
the compressed journal SHA-256 is
`f94a984fc93347e4f596627e10e5ca955d772a908bc3c4401241687a5507e8ed`.

| Summands | Coordinate bits | Total variables | Max bag | Terminal bits | Base points | Reachable target abscissae | Static factor states | Elimination states | Result |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 4 | 4 | 34 | 22 | 13 | 11 | 215 | 38,700,096 | 8,648,704 | PASS |
| 5 | 4 | 47 | 22 | 13 | 11 | 254 | 76,449,360 | 17,036,288 | PASS |
| 6 | 4 | 60 | 22 | 13 | 11 | 254 | 114,198,624 | 25,423,872 | PASS |
| 4 | 5 | 38 | 23 | 14 | 23 | 254 | 80,217,216 | 17,823,744 | PASS |
| 5 | 5 | 52 | 23 | 14 | 23 | 254 | 155,715,232 | 34,599,936 | PASS |
| 3 | 6 | 27 | 21 | 15 | 57 | 254 | 18,875,072 | 4,193,280 | PASS |
| 3 | 7 | 30 | 23 | 16 | 131 | 254 | 75,498,368 | 16,776,192 | PASS |

Each row covers all 512 target abscissae with both compact and bitplane arms
on each native build. There were 1,739 satisfiable and 1,845 unsatisfiable
target pairs per build; the two arms had matching status counts. The four
controls returned `(4,4,21) -> width-cap`, `(5,5,22) -> width-cap`,
`(4,6,24) -> state-cap`, and `(4,7,24) -> width-cap` for
`(summands, coordinate bits, max bag)` at the same 200,000,000-state limit.
The non-affine target control also differed from its affine reconstruction at
target 3, as required.

These observations locate the next structural bottleneck: at fixed field and
summand-coordinate width, the tested additional chain factors increase total
static construction work while the target boundary remains 13 or 14 bits;
at coordinate width 6 and four summands, the 200-million-state setup cap
becomes active. The next exact experiment should change elimination order or
factor representation at that boundary and replay these same target sets and
cap controls. An asymptotic F6 result would require a proved bound for a
specified family and counterexamples outside its hypotheses. The CPU times
recorded in the report are exploratory because this run lacks the isolated
host receipt; `timing_eligible=false` and `qualified_speedup=null` are retained
in the artifact.
