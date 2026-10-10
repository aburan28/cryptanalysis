# Trace parity is an exact binary propagation rule for W15 partial sums

On the exact N131 polynomial basis, **`Tr(x)=x₀⊕x₁₂₉`**. Every reciprocal
coordinate of the six pair sums and four upper partial sums in the W15
six-pair circuit has trace zero. Exposing these ten necessary equalities
adds **20 binary CNF clauses** to the eight-seed, two-branch public formula.
The complete constructed witness satisfies all **436,771 CNF clauses and
43,272 native-XOR rows**. The frozen published-point CryptoMiniSat query
remained in active search until `CENSORED_TIME` at **592.046 s** of formula
construction plus search under the one-worker, 600 s, 4 GiB gate. The
[terminal audit](terminal_audit.json) shows that the archived formula
differs from the previous eight-seed public formula only by those 20
clauses and its header count.

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The W15 source
has **B=197,292** subgroup-usable points and **K=16,381** signed-Frobenius
columns. The frozen seed family is `13,680–13,687`, with the same exact
source-density upper bound of **8.3540070920** twelve-point tuples per
uniformly selected subgroup target before cross-pair column filtering.
Only raw target preimages 0 and 2 have the necessary trace-zero reciprocal.
The [protocol](protocol.json) freezes these inputs, source and solver hashes,
and resource limits; the [checked Sage runtime](sage_runtime_info.json)
precedes measurement.

For one source pair with seed sum `s`, pair-output reciprocal `c`, and
source product `p`, the exact equation is
`s²+c²+pc+(pc)²=0`. Taking absolute trace gives
`Tr(c)=Tr(s)=0`, because the W15 basis has trace zero. Each upper S3
equation has the form `(a+b+c)²+h+h²=0`; taking trace gives
`Tr(c)=Tr(a)+Tr(b)`. Hence all ten intermediate reciprocals have trace
zero. The independent [Sage trace audit](trace_proof.json) checks the
field-basis trace support is exactly `{0,129}` and confirms all ten
constructed reciprocal coordinates obey the equality. The full
[constructed assignment check](control.json) verifies the added clauses
within the complete native-XOR formula.

| Published-point stage | Frozen result |
| --- | ---: |
| Target-dependent formula construction | 2.130 s |
| Solver search | 589.916 s |
| Construction plus search | 592.046 s |
| Sampled peak combined RSS | 791,642,112 B |
| Last logged approximate conflicts / restarts | 3.536 million / 3,060 |
| Terminal status / solver stop | `CENSORED_TIME` / `SOLVER_WALL_CAP` |
| SAT or UNSAT line / model lines | none / 0 |

The [result](result.json), [formula](system.xcnf.gz), [solver log](solver.stdout.txt),
and [byte-level auditor](audit.py) retain the complete measured stage.
The public XCNF has **121,794 variables, 436,771 CNF clauses, and 43,279
native-XOR rows**. The prior 436,751 CNF clauses and all native-XOR rows
match byte for byte. This proposal remains `candidate_id: null`: the
bounded query yielded no relation row or useful rank. These wall and
conflict observations are exploratory on a host without an isolation
receipt; they establish a sound constraint, not a controlled speedup.

The next algorithmic gate changes the expensive pair encoding itself:
for a fixed seed `s`, source product `p=w(w+s)` is linear in the source
mask. Its 14-dimensional image permits the two constrained pairs to
use 15 source-bit coordinates instead of the generic 29 product coordinates.
