# Exact signed-prefix reduction exposes the W15 five-pair extraction bottleneck

The N131 W15 six-pair relation can be reduced to an **exact signed first-pair
group prefix plus a five-pair residual**. The new residual circuit uses 97,105
Boolean variables, 354,228 CNF clauses, and 34,540 native-XOR rows. A complete
constructed assignment passes every row, and an independent Sage replay checks
the residual and original group sums, twelve distinct folded columns, and
both same-seed constraints. On that same frozen formula, one-worker
CryptoMiniSat remained in active search until the parent stopped it after
**115.036 seconds** of formula construction plus search, within the declared
120-second cap. The bounded query status is `CENSORED_TIME`; its raw log records
902 restarts and approximately 427,000 conflicts. The [terminal audit](fivepair_terminal_audit.json)
binds the archived formula, source hashes, raw log, and Sage control.

This is the fixed-group-prefix case required by the [W15 prefix-support
bound](../n131_w15_prefix_support_gate_20261010/RESULT.md). That calculation
requires at least **7,914 target-independent one-pair prefixes** for a
uniformly drawn target and gives an optimistic 75.815 ms per prefix under
600 seconds. The constructed-control extraction here remains censored after
115.036 seconds for one signed prefix. This prevents promotion of the present
Boolean five-pair kernel to an N131 public-target attempt under that resource
envelope; it measures solver extraction, not ordinary relation yield or an
end-to-end IC speedup.

## Frozen curve and exact reduction

The curve is `EC1N131Ckb1heb5f1998f20b` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`. The original constructed subgroup point is
`Q=(1629679763610955145604630509812393301372,
1078989174074289662503297782762444245160)`. The W15 source has **B=197,292**
actual usable factor-base points and **K=16,381** signed-Frobenius columns.
The original [six-pair control](../n131_w15_coupled_sixpair_20261010/control_result.json)
and [group lift](../n131_w15_coupled_sixpair_20261010/control_group_lift.json)
provide the twelve raw atoms.

The [reduction input](fivepair_input.json) fixes the first pair's *signed raw
group point* at
`P=(2644142941820534280472270347239695469753,
321682871178687504903307119224625355905)` with folded columns
`(7887,12331)`. Its projected point is `4P`, and the exact residual target
`Q−4P` is
`(195299749687542804345334901261125836908,
1128961186580568451488859020590389941242)`.
The [five-pair circuit](fivepair_circuit.py) removes the fixed pair, retains
the two same-seed four-atom blocks and their column exclusions, and enforces
the residual group equation. The [frozen protocol](fivepair_protocol.json)
sets one worker, a 4 GiB combined-RSS cap, and a 120-second construction-plus-search
cap with a 115-second parent safe stop. The checked [Sage runtime](sage_runtime_info.json)
was saved before measurement. The [full XCNF control](fivepair_control_result.json),
[group lift](fivepair_control_group_lift.json), and [independent Sage
replay](fivepair_sage_audit.json) establish a satisfying group-correct witness.
The [query result](fivepair_query_result.json) uses a freshly rebuilt formula
whose SHA-256 matches the [archived XCNF](fivepair_control.xcnf.gz).

| Constructed N131 W15 query | Fixed prefix information | CNF / XOR rows | Construction plus search | Peak combined RSS | Status |
| --- | --- | ---: | ---: | ---: | --- |
| [Masks only](result.json) | 30 source-mask bits; pair output free | 436,755 / 43,272 | 113.400 s | 443,416,576 B | `CENSORED_TIME` |
| [Reciprocal x](point_result.json) | masks and 131 x bits; either group sign | 436,886 / 43,272 | 120.074 s | 445,530,112 B | `CENSORED_TIME`; 0.074 s over cap |
| [Signed point](fivepair_query_result.json) | exact raw pair point and two columns | 354,228 / 34,540 | 115.036 s | 466,173,952 B | `CENSORED_TIME`; cap compliant |

The first two rows retain the six-pair circuit. The masks-only gate leaves
the first-pair output free. The reciprocal-x gate fixes its x coordinate but
admits both elliptic-curve signs, so it is a two-sign relaxation of a fixed
group point. Its [version-two audit](point_terminal_audit_v2.json) preserves
the 0.074-second cap overrun and the failure of the original strict-cap
assertion. The signed-point row changes the circuit by subtracting the
specific group point and removing the first pair. Its solver printed no SAT,
UNSAT, or model line before the parent stop; the [raw log](fivepair_solver.stdout.txt)
shows continuing restarts. None of the censored rows estimates an ordinary
relation probability. Their wall times are algorithmic diagnostics on a host
without a CPU-isolation receipt, and the rows do not support a speedup ratio.

The earlier [complete witness audit](witness_audit.json) verifies all clauses
and native-XOR rows of both six-pair pinned formulas. The first reciprocal-x
freeze preflight selected wires 185–315 before circuit construction had
allocated its private variables; it failed before a protocol or solver run.
The corrected wires are 2501–2631, and the point-pinned protocol records
them. All three measured rows preserve their frozen formulas, commands,
statuses, limits, and raw logs. This experiment remains a proposal with
`candidate_id: null`.

## Next kernel gate

The next method should eliminate whole seed and partial-output families in a
compact algebraic representation before source-mask expansion or pair
inversion. Its first gate is the same exact signed-prefix constructed
residual, with a complete witness, independent group replay, proposal count,
and an extraction cost that can be charged against the 7,914-prefix support
bound. After that, an N41 public-point gate needs unpinned ordinary
relations, all failed-oracle counts, column novelty, and an exact N131
work/RSS projection. Factor-base logs, relation rank, fresh-target recovery,
and a matched one-target rho solve are the later IC pipeline gates.
