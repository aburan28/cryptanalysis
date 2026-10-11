# Exact halftrace-cubic eight-slot formula on the frozen N131 public point

The N41 halftrace-cubic encoding now reaches the **full N131 W18 eight-slot public query** with exact rational-mask membership and distinct signed-Frobenius columns. Its formula has 288,483 AND gates, 808,360 variables, and 30,717,854 XCNF bytes. A constructed eight-point group relation satisfies every clause and native-XOR row, and checked Sage independently verifies all eight raw source points, their subgroup projections, and their sum. The unpinned frozen public query entered search and ended `BOUNDED_UNKNOWN` at its 600-second solver cap plus 15-second parent margin.

## Source policy and circuit

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` on `y²+xy=x³+1`, curve `EC1N131Ckb1heb5f1998f20b`, with prime subgroup order `680564733841876926932320129493409985129`. Each source reciprocal coordinate lies in `W18=span(t,…,t^18)`. Eight positions use the four same-rotation pairs `0,0,32,32,64,64,96,96`. The exact source table has **131,307 rational masks**, **B=1,050,456** distinct usable projected points across the four windows, and **K=131,068** folded columns. A reduced ordered BDD with 31,118 nodes per source selector enforces rational-mask membership. Twenty-eight mask comparisons and the 243 nontrivial same-column mask pairs enforce distinct columns across all eight positions.

For each source pair with reciprocal coordinates `a,b`, let `s=a+b`, `p=ab`, and let `c` be its proposed sum reciprocal. The circuit imposes the exact halftrace-cubic relation

`pc + H((s+c)²) + epsilon = 0`, `Tr(s+c)=0`, `epsilon in GF(2)`.

The source product has only 35 diagonal basis images before its shared Frobenius rotation. Three further halftrace-cubic S3 links join the four pair outputs into two middle sums and one raw preimage of the public target. Both selector bits for the four raw preimages are free in the initial frozen query. All pair and middle reciprocals are constrained nonzero.

The sparse reciprocal source is an **endomorphism transport** of the audited W18 base. For a rational mask `w`, choose `u` with `u²+u=w` and a curve point `P` with `x(P)=1+1/u`. Direct addition gives `x(P+πP)=1/w`, where `π` squares both coordinates. The base curve has four points over `GF(2)`, so its Frobenius satisfies `π²+π+2=0`. Consequently `(1+π)(-π)=[2]`. On the odd-order subgroup, `1+π` is invertible; it commutes with sign and Frobenius. Applying it after cofactor-four projection therefore preserves the audited base size and signed-Frobenius column equivalence classes. The independent [Sage transport audit](transport_audit_result.json) checks the coordinate identity, norm relation, subgroup transport, and eight fixture leaves on sampled W18 masks.

The [protocol](protocol.json) binds the exact source table, code and solver digests, the existing one-target public workload `cc09e7eb202a`, public point `(1052727368764798954359115163823647684025,2071227447786120917960296877345506689833)`, one worker, 120-second construction cap, 600-second solver cap, 615-second parent stop, and 4-GiB combined parent-and-solver RSS. The proposal keeps `candidate_id: null` until the relation-collection and DLP pipeline is specified and measured.

## Construction, control, and public query

| Exact stage | Result |
| --- | ---: |
| Source membership BDD | 31,118 nodes; 262,144 possible masks checked; zero disagreements |
| Nontrivial same-column mask pairs | 243 |
| Constructed relation | 805,166 variables; 285,700 AND gates; all 871,674 clauses and 518,529 XOR rows pass |
| Public formula | 808,360 variables; 288,483 AND gates; 880,023 clauses; 518,938 XOR rows; 30,717,854 bytes |
| Public query | `BOUNDED_UNKNOWN`; 2,299 solver restart rows; 970,407,936 B peak sampled combined RSS |

The [constructed control](control_result.json) uses eight exact rational W18 masks with distinct columns. Its [checked-Sage replay](sage_control_result.json), launched through the accepted repository Sage build with a saved [runtime receipt](sage_runtime_info.json), checks each source reciprocal and subgroup projection, all pair and middle group sums, and the cofactor-four image of the raw target. The separate [source audit](audit_result.json) compares the BDD against the full 18-bit mask domain and independently recomputes the constructed group witness.

The [public query receipt](query_result.json) records 3.2687 seconds of construction, 0.0501 seconds to write and hash the formula, 615.0632 seconds in the bounded solver process, and 0.0105 seconds of post-solver log capture, totaling 618.3925 seconds. The [accounting correction](accounting_correction.json) preserves the original result hash and derives the log-capture phase as the exact residual of the saved process clock; no solver or total interval was changed. These are exploratory wall intervals on an unisolated host. The [terminal audit](terminal_audit.json) rebuilt the exact formula and SHA-256, checked the frozen input lock and exclusive phase sum, and inspected the compressed solver logs. It found active search and no terminal SAT/UNSAT line before the parent stop.

## Target-side trace gate

Every W18 basis element has absolute trace zero. The S3 identity forces `Tr(c)=Tr(a)+Tr(b)` at each sum link, so every pair output, middle output, and reachable raw target reciprocal has trace zero. The [exact trace receipt](trace_gate_result.json) checks the four preimages of the same public point: indices **0 and 2** have trace zero; indices **1 and 3** have trace one. A separate frozen variant under [trace_gate_variant](trace_gate_variant) exposes these implied trace equations and excludes the two trace-one preimages in SAT. Its control and public-query receipts are kept separate from the initial run.

The [trace-gated result](trace_gate_variant/RESULT.md) adds five native-XOR rows and seven clauses to the public formula while retaining 288,483 AND gates. Its complete-assignment control passes, and its public solver also records `BOUNDED_UNKNOWN` at the 600-second cap. Both full formulas and logs rebuild to their frozen hashes. The target-side trace gate is exact pruning, but this one-bit condition alone did not resolve the public query within the declared cap.

The next algorithmic gate is a public-target constraint that rejects whole families of pair-output assignments before source-mask expansion. The N41 eight-slot public point has an independently verified unpinned indexed relation, and the N41 twelve-slot halftrace-cubic formula supplies an exact public-point circuit control; a matched eight-slot algebraic search on that point would test whether the new constraint improves witness-free solving before another N131 promotion. A verified ordinary N131 row would lead to relation-yield and rank measurements, then factor-log recovery and the required same-point single-target comparison.

Reproduce the source and query audit with `python3.12 -B experiments/ecc2k130-ic-goal-20260929/n131_w18_cubic_s8_20261011/verify.py`. The [runner](run.py) provides `freeze`, `control`, and `query` modes; the [circuit](circuit.py) contains the exact source and sum-tree equations.
