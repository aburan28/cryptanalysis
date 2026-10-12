# Exact cutset replay for the width-25 S3 chains

Conditioning one high summand bit in the four-summand chain and two in the
five-summand chain reduced each 25-variable middle link to the grouped-factor
kernel's 24-variable limit. The exact branch union completed every GF(2^9),
seven-bit-summand target abscissa in both optimized and UBSan builds. The
independent curve-sum comparator agreed with every branch status, and every
returned witness satisfied the original ANF equations and curve sum.

The frozen source was commit `43da432981e2a07d94c244064a4125ff56e34f92`.
The validator recorded 2,048 complete target queries and 6,144 completed
native branch queries: four cases (two summand counts by two builds), each
with 512 targets. The journal contains one control row, four setup rows,
2,048 target rows, and 6,144 branch rows. All 64 random conditioning controls,
the `x+1` witness-restoration control, the dynamic-equation scope rejection,
and the current 64-variable ABI cap control passed.

| Summands | Build | Branches per target | Finite reachable target abscissae | Branch SAT / total | Max static factor states per branch | Max static elimination states per branch | Median complete target interval |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | optimized | 2 | 254 / 512 | 508 / 1,024 | 25,167,296 | 50,329,602 | 5.44 ms |
| 4 | UBSan | 2 | 254 / 512 | 508 / 1,024 | 25,167,296 | 50,329,602 | 13.28 ms |
| 5 | optimized | 4 | 254 / 512 | 1,016 / 2,048 | 41,945,088 | 83,883,012 | 30.09 ms |
| 5 | UBSan | 4 | 254 / 512 | 1,016 / 2,048 | 41,945,088 | 83,883,012 | 64.07 ms |

The complete target interval starts before target-equation generation and
ends after all branch solves and witness checks. Static layout construction
and independent curve enumeration are outside it. Timings above are local
diagnostics on an unisolated macOS ARM64 host; they are neither a matched
comparison with another kernel nor an isolated-host speedup. The 78-variable
six-summand geometry requires a wider ABI or another representation before
the same branch method can be applied there.

The compressed [report](evidence/report.json.gz) has SHA-256
`42b76e111716fa4d48acbb5e644ab780b743cdb0f5f1bc46c97672b129b6cd38`.
The compressed [branch journal](evidence/journal.jsonl.gz) has SHA-256
`fa6fd828ee669dd4de1fe43f035e0e1c6472f817cf2d804e4ffe3f6cb480c2d5`.
The report includes source and binary hashes, exact target sets, setup
counters, all branch statuses, and original-equation and point replay results.
