# W16 signed-prefix circuit validates, then reaches the bounded search cap

The W16 residual circuit accepts a complete twelve-point N131 group witness:
all **528,425 CNF clauses** and **34,600 native-XOR rows** pass, and the
five-pair lift closes the exact signed residual. The same frozen formula,
queried without pinning the remaining ten masks, reached `CENSORED_TIME` after
**115.070 seconds** of construction and search under a 120-second cap.
The [terminal audit](terminal_audit.json) binds the control, byte-identical
query formula, source hashes, solver log, 120 active-search restart lines,
and resource limits.

This uses curve `EC1N131Ckb1heb5f1998f20b`, the [audited W16 source](../n131_w16_w18_sixpair_width_gate_20261010/RESULT.md)
with **B=393,552** actual projected points and **K=32,675** folded columns,
and the archived signed first pair with columns `(7887,12331)`. The exact
residual point is
`(195299749687542804345334901261125836908,
1128961186580568451488859020590389941242)`. The original W15 witness
is contained in W16. The [W16 circuit](fivepair_circuit.py) expands each
remaining mask to 16 bits, preserves the two same-seed blocks and all
distinct-column constraints, and applies the reciprocal-S3 joins to the
four raw preimages of that residual point.

| Stage | Wall time | Peak combined RSS | Result |
| --- | ---: | ---: | --- |
| [Complete formula and group control](fivepair_control_result.json) | 113.308 s including 38.961 s construction | — | `PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL` |
| [Unpinned residual query](query_v2_result.json) | 30.451 s construction + 84.561 s search = 115.070 s | 355,811,328 B | `CENSORED_TIME` |

The query ran one CryptoMiniSat worker with native XOR, a 4-GiB combined-RSS
cap, and a 115-second safe stop. The solver was terminated at the safe stop;
the raw log contains active restarts and no SAT, UNSAT, or model line. The
[versioned query protocol](query_v2_protocol.json) binds the runner, solver,
source, archived formula, exact residual, flags, and caps. The checked
[Sage runtime receipt](sage_runtime_info.json) was saved before the run.
The first W16 runner inherited a 10-second formula-construction preflight
from W15. Because its validated W16 control took 38.961 seconds to build,
the query used the frozen [version-two runner](query_v2.py) with a 60-second
preflight while retaining the 120-second total cap. Its rebuilt XCNF SHA-256
matches the complete control formula.

W16's exact source bound requires at least **32 first-pair prefixes** for a
half-union ceiling under a uniform target, or at most **18.75 seconds per
prefix** under 600 seconds. Rebuilding this target-dependent formula alone
took 30.451 seconds for one prefix, before the censored search. This rules
out the current per-prefix rebuild as a 600-second procedure for that
32-prefix gate; construction reuse or a target-coupled partial-sum inverse
is the next algorithmic step. The query is a constructed correctness and
extraction control, so its status does not estimate ordinary relation yield.
Timing remains exploratory on the unisolated host. `candidate_id` remains
null until a complete method and target-recovery path are specified.
