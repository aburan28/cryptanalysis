# Exact trace propagation on the frozen N131 W18 query

The W18 reciprocal source forces **trace zero at every pair output, middle output, and reachable raw target preimage**. Exposing those consequences to CryptoMiniSat excludes two of the four raw preimages of the frozen public point. On the same one-worker, 600-second, 4-GiB query, the trace-gated formula entered active search and ended `BOUNDED_UNKNOWN`; its known eight-point relation passed every constraint.

For the halftrace-cubic S3 link, `Tr(a+b+c)=0`. Each source W18 reciprocal has zero trace, so induction through the seven-link sum tree gives `Tr(c)=0` at every internal output and at the raw target. The [trace proof receipt](../trace_gate_result.json) checks the 18 source basis traces and all four public raw preimages: indices `0,2` have trace zero; `1,3` have trace one. The [variant circuit](run_trace.py) adds six direct trace equations and a unit constraint on the target flag that selects `z+1`. These constraints preserve every relation in the declared source law.

| Same public workload `cc09e7eb202a` | Initial cubic formula | Direct trace gate |
| --- | ---: | ---: |
| AND gates | 288,483 | 288,483 |
| Variables | 808,360 | 808,365 |
| CNF clauses | 880,023 | 880,030 |
| Native-XOR rows | 518,938 | 518,943 |
| XCNF bytes | 30,717,854 | 30,718,021 |
| Public solver status at cap | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` |
| Solver restart rows | 2,299 | 2,383 |
| Peak sampled parent-plus-solver RSS | 970,407,936 B | 937,377,792 B |

The [variant protocol](protocol.json) freezes the initial source and target hashes, trace proof, solver flags, one worker, 600-second internal cap, 615-second parent stop, and 4 GiB RSS. The [complete-assignment control](control_result.json) checks all 871,680 clauses and 518,534 native-XOR rows for the constructed relation. The [public query receipt](query_result.json) records 3.8737 seconds for construction, 0.6180 seconds to write/hash, 615.2072 seconds in the bounded solver process, and 0.0206 seconds of post-solver log capture, totaling 619.7196 seconds. The [accounting correction](accounting_correction.json) retains the original result hash and exposes that final phase as the saved clock residual. The [terminal audit](terminal_audit.json) rebuilt the exact 30,718,021-byte formula and SHA-256, checked the exclusive phase sum and log hashes, and found 2,383 active restart rows without a terminal SAT/UNSAT line. Wall intervals are exploratory on an unisolated host; the two capped outcomes are retained as censored search evidence.

The next solver change needs to propagate more than the one-bit trace condition: a target-conditioned constraint that rejects entire pair-output families before their 18-bit source masks are expanded. The frozen N41 eight-slot public relation provides a witness-free positive control for that search rule. The complete IC candidate remains unspecified with `candidate_id: null`.

Reproduce the audit with `python3.12 -B experiments/ecc2k130-ic-goal-20260929/n131_w18_cubic_s8_20261011/trace_gate_variant/verify_trace.py`.
