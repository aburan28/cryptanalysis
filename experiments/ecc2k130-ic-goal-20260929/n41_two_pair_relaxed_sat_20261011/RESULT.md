# Implicit N41 two-pair target completion gate

An exact, list-free two-pair completion circuit was built from seed-sum and
product-span variables and coupled directly to each frozen target residual.
The constructed positive witness satisfies all **11,398 CNF clauses and
2,026 native-XOR rows**. Under a one-worker 45-second CryptoMiniSat limit,
both the known-positive residual and an exhaustively classified negative
residual recorded **`BOUNDED_UNKNOWN`**. This identifies Boolean search on
the implicit pair equations as the next bottleneck for this formulation.

The field is `GF(2)[t]/(t^41+t³+1)` on `y²+xy=x³+1`. The [prior exact native
panel](../n41_direct_relaxed_pair_join_20261011/RESULT.md) enumerated all
128,656 rational curve points in the relaxed pair-output set, then applied
Frobenius rotations 20 and 30. Its positive residual is
`(1385030211012,1839474220645)`; its `control_0` residual is
`(1552521799954,1663016718497)`. The first has an independently replayed
two-pair sum; the second exhausted the complete relaxed left set without a
sum. Both are public residuals for this component experiment, and no pair
witness is pinned in either solver query.

For each free pair, the new [circuit](circuit.py) represents its six-bit
nonzero seed sum `s`, eleven-bit product `p` in the `t²..t^12` span, branch
bit `epsilon`, and reciprocal output `z`. It enforces the same linearized
equation as the native enumerator,

`p*z + H((s+z)²) + epsilon = 0`,

as well as nonzero `z` and `Tr(z)=0`. An auxiliary `x` satisfies `x*z=1` and
`Tr(x+z²)=0`, precisely the rational-lift test for this curve. Frobenius
rotation is applied to each source basis before the equation. The two
reciprocal outputs then satisfy the exact half-trace S3 link with
`z_target=1/x(target)`. Since each retained output lifts with both curve
signs, this final x-coordinate link is an existential group-sum condition.
The circuit therefore describes the native relaxation without storing or
scanning its output list.

| Frozen residual | Exact native panel | SAT formula variables / AND gates | XCNF bytes | Solver status / wall | Peak sampled combined RSS |
| --- | --- | ---: | ---: | --- | ---: |
| Positive | `RELAXED_SUM_HIT`, 21,713 probes | 5,955 / 3,728 | 300,771 | `BOUNDED_UNKNOWN`, 50.141 s parent-observed solver process | 59,441,152 B |
| `control_0` | `COMPLETE_RELAXED_NO_SUM`, 128,656 probes | 5,965 / 3,728 | 302,406 | `BOUNDED_UNKNOWN`, 50.019 s parent-observed solver process | 141,524,992 B |

The [protocol](protocol.json) froze the circuit, native panel, solver binary,
flags, 45-second internal limit, 50-second parent limit, and 4 GiB combined
RSS cap before the control and queries. The [positive control](control.json)
uses the native witness only for validation: its rotated reciprocals match
the two exact curve points, and every serialized Boolean equation passes.
The unpinned [positive](positive.result.json) and [negative](control_0.result.json)
receipts preserve construction, write, solver, and post-solver phases and all
solver output. The [independent audit](audit.json) rechecks input/source
hashes, rebuilds both XCNFs byte-for-byte, checks the positive witness
binding, and confirms active search before both parent wall stops. These
local CPU intervals are exploratory stage diagnostics; `candidate_id` is
`null`.

The native list join classifies these same residuals in 11.466 and 56.517
milliseconds after its 514.778-millisecond reusable setup. Its literal
pair list cannot be transferred at N131 W18 scale. The new circuit removes
that storage requirement, but its N41 positive search and negative proof
both exceed this cap. The next method must eliminate the two free pair
equations structurally or propagate their finite seed-conditioned output
sets into the target equation before an ordinary N131 query is justified.
