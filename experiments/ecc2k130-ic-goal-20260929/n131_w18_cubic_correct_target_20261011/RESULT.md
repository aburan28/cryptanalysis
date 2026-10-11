# Standard-reciprocal binding for the N131 W18 cubic public query

The eight-slot halftrace-cubic circuit now binds its final S3 output to the **standard reciprocal `1/x` of each raw preimage of the saved public point**. An independent binary-field and elliptic-curve replay verifies all four input points, their standard reciprocals, their selection by the circuit's two-bit mux, and `[4]U=Q` for each preimage. The corrected query entered active CryptoMiniSat search and recorded `BOUNDED_UNKNOWN` at the frozen 600-second solver cap; the XCNF rebuild and compressed-log audit pass.

## Exact input and circuit

The field is `GF(2)[t]/(t^131+t^13+t^2+t+1)` and the curve is `y²+xy=x³+1`, with curve ID `EC1N131Ckb1heb5f1998f20b` and odd subgroup order `680564733841876926932320129493409985129`. The one-target workload `cc09e7eb202a` supplies public point `Q=(1052727368764798954359115163823647684025,2071227447786120917960296877345506689833)`. Each saved raw preimage `U` satisfies `[4]U=Q`. Its `x` is a point coordinate; the cubic S3 chain consumes `z=1/x(U)`.

The archived preimage file calls its coordinate `reciprocal_x_z`, but its four values satisfy `(x+1)z=1`. The previous public XCNF consumed those shifted values directly. The [new frozen protocol](protocol.json) derives standard `1/x` from each saved point, verifies both field equations, and records both coordinate lists. The [independent binding audit](binding_audit.json) reimplements GF(2^131) multiplication and inversion, checks the curve equation and all four quadruplings, and verifies the four-way mux. The standard reciprocal traces are `[0,0,1,1]`.

The source policy is unchanged: `W18=span(t,...,t^18)`, eight leaves in four same-rotation pairs at rotations `(0,0,32,32,64,64,96,96)`, 131,307 rational source masks, actual factor-base size **B=1,050,456**, and **K=131,068** signed-Frobenius columns. Exact BDD membership and distinct-column constraints remain in the [circuit](circuit.py). The proposal has `candidate_id: null` while relation collection, factor-log recovery, and target descent remain unspecified.

## Frozen control and public search

| Stage | Measured result |
| --- | ---: |
| Constructed eight-slot control | All 871,674 clauses and 518,529 native-XOR rows pass |
| Corrected public formula | 811,166 variables; 290,898 AND gates; 887,268 clauses; 519,329 native-XOR rows |
| XCNF | 30,878,516 bytes; SHA-256 `db8b9056baf765cd4f10c00d8e157f9acdfd15b131700729f65a8d54235a376e` |
| Public search | `BOUNDED_UNKNOWN`; 2,352 solver restart rows; 798,244,864 B peak sampled parent-plus-solver RSS |

The [control receipt](control_result.json) is a complete Boolean assignment to a constructed eight-point relation. The [public query receipt](query_result.json) fixes one CryptoMiniSat worker, `--xor=0`, a 600-second solver cap, a 615-second parent stop, and a 4-GiB combined RSS cap. Its exclusive exploratory wall phases are 3.262602 s construction, 0.444399 s write/hash, 615.199533 s solver process, and 0.010966 s post-solver log capture, totaling **618.917500 s**. The final phase is the exact residual recorded in the [terminal audit](terminal_audit.json); it includes log capture and compression after the solver stopped. The audit rebuilt the XCNF byte-for-byte, checked the frozen source hashes, inspected solver logs, and found active search without a terminal SAT/UNSAT result. These local CPU intervals are stage diagnostics on an unisolated host.

The next exact target-side reduction is the [standard-reciprocal trace variant](../n131_w18_cubic_correct_trace_20261011/RESULT.md): every W18 source coordinate has trace zero and S3 propagates trace, so only preimages 0 and 1 can complete the eight-slot tree. Its query uses the same public point and resource cap with a one-bit selector. A useful subsequent gate must reject families of unresolved pair outputs before source-mask expansion; then ordinary-query relation yield and novel rank can be measured under a complete candidate manifest.

Reproduce input binding with `python3.12 -B experiments/ecc2k130-ic-goal-20260929/n131_w18_cubic_correct_target_20261011/verify.py`. The [runner](run.py) provides `freeze`, `control`, and `query`; [terminal_verify.py](terminal_verify.py) rebuilds the saved public formula and audits its result.
