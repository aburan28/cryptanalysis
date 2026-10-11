# Exact trace pruning of the corrected N131 public query

The standard-reciprocal N131 W18 circuit now restricts its raw public-target preimage selector from four points to the **two trace-zero points**, with no loss under the declared W18 source law. The public formula shrinks by 2,666 AND gates, 3,081 variables, 7,998 clauses, 414 native-XOR rows, and 176,774 XCNF bytes relative to the [corrected four-preimage circuit](../n131_w18_cubic_correct_target_20261011/RESULT.md). Its constructed eight-slot assignment passes every clause and XOR row. The frozen public query entered active search and recorded `BOUNDED_UNKNOWN` at the 600-second solver cap.

## Sound target pruning

The exact field is `GF(2)[t]/(t^131+t^13+t^2+t+1)` on `y²+xy=x³+1`, curve `EC1N131Ckb1heb5f1998f20b`. The same one-target workload `cc09e7eb202a` supplies public point `Q=(1052727368764798954359115163823647684025,2071227447786120917960296877345506689833)`. The source uses eight reciprocal-coordinate leaves in `W18=span(t,...,t^18)` at rotations `(0,0,32,32,64,64,96,96)`, with actual factor-base size **B=1,050,456** and **K=131,068** folded columns.

Every W18 basis vector has absolute trace zero, and Frobenius rotation preserves trace. Each exact S3 sum link obeys `Tr(c)=Tr(a)+Tr(b)`, so every internal output and the raw target preimage have trace zero. The four point-derived **standard** reciprocals `1/x` have traces `[0,0,1,1]`; only indices **0 and 1** can satisfy this eight-slot tree. The [frozen protocol](protocol.json) records all four point coordinates and standard reciprocals, the trace partition, and the two included indices. The [independent binding audit](binding_audit.json) rechecks the field traces, curve equation, `[4]U=Q` for each preimage, selected reciprocals, and one-bit mux. The [circuit](circuit.py) has one public target flag and a two-value selector, so the trace-one alternatives are absent from the formula by construction.

## Matched formula and capped query

| Public formula item | Four preimages | Two trace-zero preimages | Reduction |
| --- | ---: | ---: | ---: |
| AND gates | 290,898 | **288,232** | 2,666 |
| Variables | 811,166 | **808,085** | 3,081 |
| CNF clauses | 887,268 | **879,270** | 7,998 |
| Native-XOR rows | 519,329 | **518,915** | 414 |
| XCNF bytes | 30,878,516 | **30,701,742** | 176,774 |
| Public query at cap | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` | — |

Both runs used one CryptoMiniSat worker, `--xor=0`, a 600-second solver cap, a 615-second parent stop, and a 4-GiB combined RSS cap on the same public point. The [two-preimage query receipt](query_result.json) records 18.760601 s construction, 0.295614 s write/hash, 615.086182 s solver process, and 0.005494 s post-solver log capture, totaling **634.147891 s**. The final phase is the exact residual recorded in the [terminal audit](terminal_audit.json). The audit reproduced the 30,701,742-byte XCNF and SHA-256 `b51f1b661a42c50b2cc768ed26d9d4f343cf24c23dcbb19b6c11d00628fd380c`, verified the source and compressed-log hashes, and found 1,324 solver restart rows without a terminal SAT/UNSAT result. Peak sampled parent-plus-solver RSS was 728,055,808 B. Wall times, restart counts, and RSS are exploratory local diagnostics; the exact formula-size reductions are the controlled outcome of this stage.

The trace predicate is now exhausted for this source policy. The next gate is a target-coupled constraint on **two unresolved pair outputs** that rejects whole first-pair families before completing a third pair. Test its soundness against the 12-row exact N41 public fiber, measure family rejection and charged cost against the indexed join, and only then freeze an ordinary N131 query. This circuit stage retains `candidate_id: null` until a complete relation and DLP pipeline is specified.

Reproduce the independent trace and point audit with `python3.12 -B experiments/ecc2k130-ic-goal-20260929/n131_w18_cubic_correct_trace_20261011/verify.py`. The [runner](run.py) provides `freeze`, `control`, and `query`; [terminal_verify.py](terminal_verify.py) rebuilds and audits the public XCNF.
