# Reusable W16 source circuit reduces per-prefix formula construction

The W16 five-pair residual circuit now separates **509,251 CNF clauses and
30,629 native-XOR rows** into one reusable source core. A signed first-pair
prefix and its target residual add the remaining **19,174 clauses and 3,971
XOR rows**. The complete cached formula accepts the archived twelve-point
group witness and passes every one of its 528,425 clauses and 34,600 XOR
rows. Target-specific completion took 1.208 seconds in that control and
1.555 seconds in the bounded query, versus 30.451 seconds for construction
of the earlier monolithic W16 query on this exploratory host. The split
moves the large source build into precomputation; it does not yet improve
the observed solver outcome.

The [bounded query](query_result.json) reached `CENSORED_TIME` at
**115.044 seconds** under the frozen one-worker, 120-second total and
4-GiB combined-RSS caps. Its raw solver log confirms native-XOR parsing
but contains no restart, SAT, UNSAT, or model line. The
[terminal audit](terminal_audit.json) binds the cached core, complete XCNF
control, byte-identical query formula, raw log, hashes, and caps. Since
branch search is unobserved in this log, the 112.523-second solver interval
is a censored solver subprocess interval, not a measured search effort.

This is proposal `Q20261010120500` on
`EC1N131Ckb1heb5f1998f20b`, with `candidate_id: null`. The same-rotation
W16 policy has [B=393,552 usable points and K=32,675 folded columns](../n131_w16_w18_sixpair_width_gate_20261010/RESULT.md).
The [frozen constructed residual](../n131_w16_fivepair_sat_gate_20261010/fivepair_input.json)
uses first-pair columns `(7887,12331)` and subgroup point
`(195299749687542804345334901261125836908,
1128961186580568451488859020590389941242)`. The first pair is fixed as
an exact signed group point; the remaining ten masks are free in the query.

The [core builder](core.py) retains source-mask rationality, ten-way
distinct folded columns, two equal-seed pair blocks, five bilinear pair
equations, and three upper reciprocal-S3 joins. The
[target suffix](core.py) inserts the two fixed-column exclusions and the
last S3 link to one of four raw preimages of the residual point. The
[core receipt](core_result.json) records 53.984 seconds to build and
78.248 seconds to build and archive a 6,216,569-byte compressed circuit.
That is target-independent work. The checked
[Sage runtime](sage_runtime_info.json) and [base protocol](protocol.json)
were saved before the core build; the [query protocol](query_protocol.json)
was frozen after the full witness control passed. The
[protocol generator](freeze_query.py) reproduces the latter byte for byte
with `python3 -B freeze_query.py --verify`.

| Query phase | Recorded wall time |
| --- | ---: |
| Cache load and source setup, outside the target interval | 5.439 s |
| Target raw preimages | 0.208 s |
| Target S3 suffix and prefix exclusions | 1.555 s |
| Formula write | 0.471 s |
| Solver subprocess, including parsing and any internal work | 112.523 s |
| Other charged overhead | 0.287 s |
| **Charged target-dependent total** | **115.044 s** |

The [full XCNF and group control](control_result.json) used the same
formula digest as the query. The [offline audit](terminal_audit.py)
recounts every CNF and native-XOR line, decompresses and hashes the formula,
checks source and run receipts, and balances the exclusive charged phases.
The query's sampled combined peak was **364,822,528 bytes**. CPU wall
times remain diagnostic because this host has no isolation receipt.

W16's exact support ceiling requires at least 32 target-independent
first-pair prefixes for a 50% union-bound ceiling, implying an optimistic
18.75-second average prefix budget under 600 seconds. The cached
target-dependent construction fits that arithmetic requirement, but the
censored solver interval dominates it. The next gate is a solver policy or
target-coupled partial-sum inverse that yields a complete unpinned group
relation within the frozen cap, with a log proving the search stage began.
Only then can ordinary-query yield and novel rank be measured on the N131
point.
