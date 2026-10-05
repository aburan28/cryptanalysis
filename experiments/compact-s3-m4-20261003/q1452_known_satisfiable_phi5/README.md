# Q1452: unpinned phi5 search on a known-satisfiable N53 slice

Q1452 changes only the selected raw target preimage in Q1451's compact
five-input phi circuit: index 201 instead of index 0 for the same archived
ordinary N53 public target. The curve, W≤4 factor base, actual usable
point count, folded columns, workload ID, CryptoMiniSat binary, Gaussian
settings, and 60-second nominal solver cap are frozen in the
[protocol](protocol.json). This is a `PDP4phi5` stage proposal with
`candidate_id: null` and `isogeny: "none"`.

The [control](controls.json) proves that this exact slice contains a
four-point relation. Its fully pinned formula has the same XCNF hash as
Q1451's archived N53 control, whose solver model passed exact group
replay. The ordinary Q1452 formula leaves all four x and phi values
unknown; none of the witness leaf values is supplied to the solver.

| Ordinary N53 measurement | Value |
| --- | ---: |
| Public-target raw preimage index | 201 of 428 |
| AND gates / CNF clauses / native XOR rows | 47,700 / 145,227 / 2,067 |
| Active Gaussian matrices | 5 |
| Last partial restart conflict count | about 369K |
| Solver process wall time | 65.009 s, external timeout |
| Solver child user + system CPU | 49.127 s + 1.364 s |
| Target-dependent stage wall time | 65.263 s |
| Peak child RSS | 139,378,688 bytes |
| Returned models / verified relations | 0 / 0 |

The [archive audit](verification.json) rebuilds the exact XCNF, checks
source hashes and solver settings, verifies the compressed input and raw
output hashes, and would replay every returned model. The frozen protocol
recheck covers input hashes. The run is censored: its last restart line is
rounded partial progress, not an exact final operation count. Although a
solution exists in this slice, Q1452 did not measure its recovery cost.
It gives no ordinary relation yield, novel rank, N53-to-N83 growth rate,
or complete N131 `2^x`. The challenge gate remains closed.

This result closes constant-target substitution alone as a 60-second
ordinary N53 solver under these settings. The next method needs a
solution-preserving field-level propagation or elimination rule that
constrains multiple sparse leaves before general SAT branching. A
longer run of the same circuit could measure a larger censored budget,
but would not by itself change the search algorithm.
