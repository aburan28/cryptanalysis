# Native-XOR matrix limits explain a W15 solver gate, but admission does not extract the control

CryptoMiniSat 5.14.7 recognizes five dense **130×3,929** Gaussian matrices in
the exact N131 W15 signed-prefix, trace-restricted five-pair XCNF. Its
default 1,000-column limit rejects all five. Raising that limit to 4,096
admits them. Raising the limits to 10,000 columns and 4,000 rows also admits
four medium matrices in later solver passes. These are source-identical
experiments on the same known-satisfiable formula and constructed residual
target. Both changed configurations stayed in active search and ended
`CENSORED_TIME` without a model under their frozen one-worker, 115-second
solver-stage caps. The [terminal audit](terminal_audit.json) verifies the
formula hash, solver binary and flags, raw logs, statuses, and resource caps.

The tested XCNF is the prior [trace-fiber formula](../n131_w15_trace_fiber_gate_20261010/trace_fiber.xcnf.gz),
SHA-256 `8bb0a8f4f473b2a44f4c4c4e660839291cd77bf30b73e83d0b81ca74a7a3ebe8`.
Its [full assignment control](../n131_w15_trace_fiber_gate_20261010/control_result.json)
passes 354,230 CNF clauses and 34,540 native-XOR rows, and its
[independent Sage audit](../n131_w15_trace_fiber_gate_20261010/sage_trace_audit.json)
verifies the target fiber and group arithmetic. The curve is
`EC1N131Ckb1heb5f1998f20b`, with **B=197,292** usable factor-base points
and **K=16,381** signed-Frobenius columns. The subgroup residual target is
`(195299749687542804345334901261125836908,
1128961186580568451488859020590389941242)`.

The installed solver's own help reports default `--maxmatrixcols=1000` and
`--maxmatrixrows=2000`. In the baseline [raw log](../n131_w15_trace_fiber_gate_20261010/solver.stdout.txt),
the five dense matrices are explicitly marked “Too many columns”; one
smaller 130-row matrix is used initially. In the
[4,096-column log](solver.stdout.txt), all five are used initially, but
later passes report zero eligible matrices because larger components exceed
the row limit. In the [10,000-column/4,000-row log](solver_rows.stdout.txt),
the later passes report four matrices. The 19,719–20,458-row component
remains excluded by the 4,000-row limit.

| Same XCNF and target | Additional solver flags | Solver-stage wall | Peak combined RSS | Last logged restart / approximate conflicts | Result |
| --- | --- | ---: | ---: | ---: | --- |
| [Default](../n131_w15_trace_fiber_gate_20261010/query_result.json) | none | 112.903 s search after 2.120 s build | 455,278,592 B | 1,309 / 754K | `CENSORED_TIME`, parent stop |
| [Dense matrices](query_result.json) | `--maxmatrixcols=4096` | 112.519 s | 415,989,760 B | 1,435 / 878K | `CENSORED_TIME`, parent stop |
| [Dense and medium matrices](query_rows_result.json) | `--maxmatrixcols=10000 --maxmatrixrows=4000` | 110.538 s | 520,404,992 B | 458 / 144K | `CENSORED_TIME`, solver `s INDETERMINATE` |

All three runs use one worker, `--xor=0` for long-XOR discovery, the same
native-XOR XCNF, RNG seed `20261010`, and `--maxtime=106`. The two new
[protocols](protocol.json) and [row-limit protocol](protocol_rows.json) froze
the changed flags and 4 GiB combined-RSS cap before each query. The
checked [Sage runtime receipt](sage_runtime_info.json) precedes the measured
runs. The row-limit case terminated internally at `s INDETERMINATE` before
the parent safe stop; its conflict count is not a fixed-work comparison.
These CPU wall intervals are stage diagnostics on a host without an isolation
receipt. Neither censored row establishes an extraction improvement, natural
relation yield, or end-to-end IC speedup.

The next kernel should change the algebraic representation: retain each
same-seed four-atom block as a target-conditioned output family and reject
incompatible seed/product families before Boolean source-mask expansion.
The existing exact degree-eight four-atom inverse supplies a correctness
oracle for proposed outputs. An unpinned N41 public-point relation with
independent group and column replay is the first promotion gate, followed
by complete N131 work/RSS projection and the ordinary N131 target query.
This solver experiment has `candidate_id: null`.
