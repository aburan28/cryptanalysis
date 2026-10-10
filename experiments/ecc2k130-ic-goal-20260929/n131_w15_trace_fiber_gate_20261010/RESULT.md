# Trace-zero fiber removes two impossible W15 target branches

The W15 source basis has absolute trace zero, and the reciprocal S3 addition
equation makes trace additive across a defined point sum. For the exact
signed-prefix N131 five-pair residual, this restricts the raw target fiber
from four preimages to indices **0 and 2**. Adding only the two necessary
unit clauses to the prior 97,105-variable XCNF preserves its complete
constructed witness; all **354,230 CNF clauses and 34,540 native-XOR rows**
pass. Independent installed-Sage arithmetic verifies all four preimage
projections, reciprocal traces `[0,1,0,1]`, and the trace-zero source basis.

The frozen one-worker CryptoMiniSat query on the two-branch formula stayed
active until its parent safe stop at **115.029 seconds** of construction plus
search, within the 120-second cap. It ended `CENSORED_TIME`, with 1,309
logged restarts, approximately 754,000 conflicts, and 455,278,592 bytes
sampled combined peak RSS. The [terminal audit](terminal_audit.json) checks
the source and formula hashes, complete control, Sage replay, raw solver log,
and resource record. The extracted branch restriction is exact, while the
query is still a bounded solver-stage diagnostic on a constructed control.

## Trace argument and target fiber

The curve is `EC1N131Ckb1heb5f1998f20b` on
`GF(2)[t]/(t^131+t^13+t²+t+1)`, with subgroup order
`680564733841876926932320129493409985129`. The W15 source basis is
`{t,t²,…,t¹⁵}`; [Sage replay](sage_trace_audit.json) gives trace zero for
each basis vector. Frobenius rotation preserves absolute trace. For
reciprocal x coordinates `a,b,c` of three points satisfying the S3 addition
equation, write `h=abc`. The equation used by the archived circuit is

`(a+b+c)²+h+h²=0`.

Taking the absolute trace cancels `Tr(h+h²)`, giving
`Tr(c)=Tr(a)+Tr(b)`. Consequently every defined pair and upper sum of
these source atoms has trace-zero reciprocal x. The four raw preimages of
the [signed-prefix residual target](../n131_w15_onepair_fixed_sat_gate_20261010/fivepair_input.json)
have reciprocal traces `[0,1,0,1]` in the frozen preimage order, and each
independently replays under multiplication by four to the same subgroup
target. The known constructed witness uses index 2.

The [protocol](protocol.json) froze those traces, the excluded flag wires
`152` and `154`, source and solver hashes, one worker, a 4 GiB RSS limit,
and a 120-second construction-plus-search cap before the query. The checked
[Sage runtime receipt](sage_runtime_info.json) precedes the measured run.
The [control](control_result.json) verifies the complete assignment against
the [executed XCNF](trace_fiber.xcnf.gz). The byte-level auditor confirms
that this formula is exactly the prior signed-prefix formula with clauses
`-152 0` and `-154 0` inserted before its native-XOR records and the header
count updated; the original Boolean relations and witness remain intact.

| Constructed N131 signed-prefix five-pair query | Raw target-fiber indices | CNF / XOR rows | Construction plus search | Logged restarts / last approximate conflicts | Terminal status |
| --- | --- | ---: | ---: | ---: | --- |
| [Prior exact residual](../n131_w15_onepair_fixed_sat_gate_20261010/fivepair_query_result.json) | 0, 1, 2, 3 | 354,228 / 34,540 | 115.036 s | 902 / 427K | `CENSORED_TIME` |
| [Trace-restricted residual](query_result.json) | 0, 2 | 354,230 / 34,540 | 115.029 s | 1,309 / 754K | `CENSORED_TIME` |

Both intervals include formula construction and all search in their own
frozen runs. The host lacks a CPU-isolation receipt, and both rows are
censored; restarts and conflicts are search diagnostics rather than a
speedup or relation-yield measure. The source has **B=197,292** actual
usable factor-base points and **K=16,381** signed-Frobenius columns. This
branch gate remains a proposal-stage component with `candidate_id: null`.

The next kernel should filter target-conditioned same-seed four-atom output
families before expanding source masks. The existing exact W14 degree-eight
inverse and product-space polynomial give a concrete oracle for a proposed
block output; the missing step is generating and rejecting such outputs
jointly under the five-pair target equation. An unpinned N41 public-point
relation with group and column replay is the first gate, followed by a
complete one-worker N131 work/RSS projection against the 7,914-prefix
support bound, and then the ordinary N131 target query.
