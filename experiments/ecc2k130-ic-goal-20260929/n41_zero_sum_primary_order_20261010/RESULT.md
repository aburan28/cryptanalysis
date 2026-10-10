# Primary-variable ordering on the N41 zero-sum target formula

An exact variable permutation places the eight quadratic root choices,
56 source-mask bits, and four target-fiber flags ahead of 247,935
circuit auxiliaries. A complete known assignment satisfies both the
original and permuted public formulas and both fixed-mask controls.
Under matched one-worker CryptoMiniSat options, **both fixed-mask
controls reached the 65-second wall cap** with status
`BOUNDED_UNKNOWN`. The permutation therefore did not clear the declared
gate for an unpinned public query. This proposal is `Q20261010222000`,
with `candidate_id: null` while its complete IC pipeline is unspecified.

## Exact source and transformation

The input is the frozen N41 Koblitz point
`Q=(1458168294740,1672312028033)` on
`EC1N41Ckb1h7d5e80d3c4d0`: `GF(2^41)` uses
`t^41+t^3+1`, the curve is `y²+xy=x³+1`, and the
prime subgroup order is `549756390943`. Its W7 four-rotation base has
`B=504` usable projected points and `K=57` folded columns. The
[forward-root source](../n41_n131_zero_sum_forward_20261009/RESULT.md)
binds the public formula, verified twelve-point relation, and exact
S5 target endpoint.

The [builder](build.py) applies the bijection
`new_to_old = roots || masks || flags || remaining old IDs`. It preserves
the sign of every CNF and native-XOR literal. The old and new formulas
have the same **248,003 variables** and **111,710 native XOR rows**;
the fixed-mask formula has **410,239 CNF clauses** and the public formula
has **410,183**. The [build receipt](build.json) records both formula
hashes and the 68 primary old wire IDs. A complete model from the
independently replayed source relation passes every clause and XOR row
of all four formulas after applying this permutation. The exact
[protocol](protocol.json) froze the solver binary, formulas, sources,
runtime, run order, and caps before either search.

Both runs used `--threads=1 --renumber=0 --branchstr=vmtf`, a
60-second solver limit, 65-second outer wall limit, and 4-GiB combined
RSS cap. The original and permuted fixed-mask formulas were run in the
predeclared order below. The host had no isolation receipt, so CPU wall
figures are exploratory stage diagnostics.

| Fixed-mask formula | Solver status | Solver wall | Peak sampled combined RSS | Last logged conflicts | Raw result |
| --- | --- | ---: | ---: | ---: | --- |
| Primary IDs first | `BOUNDED_UNKNOWN` | 65.123 s | 232,161,280 B | about 168,000 | [receipt](ordered_control/result.json) |
| Original IDs | `BOUNDED_UNKNOWN` | 65.078 s | 267,485,184 B | about 384,000 | [receipt](original_control/result.json) |

Both logs show active VMTF search, empty stderr, and no SAT or UNSAT
status. Conflict counts reflect solver work under a wall cap and are not
relation yield or a timing ratio. The positive model demonstrates exact
encoding support; it supplies privileged witness data. The public
formula was built and checked against that model, then its search gate
remained closed because the ordered fixed-mask control did not solve.
The [terminal verifier](verify.py) rechecks the frozen hashes, complete
positive model, matched commands, search records, and gate decision.

A checked-Sage audit launcher invocation returned exit code 2 because
the frozen copied auditor accepts `chart|control|public` while the new
mode is `ordered_control`; the [failure receipt](audit_launch_failure.json)
preserves that interface error. Neither bounded run emitted a model for
Sage to replay. The earlier source relation retains its independent
checked-Sage replay.

## Next method gate

Variable-ID order is insufficient here. The stronger algebraic lead in
the current worktree is the [same-rotation W14 pair-output inverse](../n131_w14_polynomial_pair_inverse_20261010/RESULT.md): its degree-131
product span has rank 27, and a proposed pair output faces an exact
131-by-41 consistency test before mask-pair recovery. The next
target-conditioned experiment should derive pair-output proposals from
the upper S3 target chain, apply that consistency gate before mask
expansion, and count rejected output families on an unpinned N41
control. Any N131 query then needs a frozen source-bound 600-second,
4-GiB projection and independent raw-point replay. The complete goal
continues through ordinary relation yield, novel rank, final relation
linear algebra, fresh target descent, and matched same-point rho time.
