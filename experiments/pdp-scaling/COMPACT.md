# Compact admissibility and the frozen-corpus milestones

This follow-up tests exact subgroup membership constraints that do not enumerate
the `2^l` payload domain. Both implementations are bounded to odd `n<=19` and
`l<=8`. They use the existing toy polynomial-basis factor space and three-summand
PDP verifier. This measures SAT-based decomposition, not a Gröbner improvement
or a full discrete-log computation.

## Exact membership constraint

For the benchmark curve `E0: y^2+xy=x^3+1` over an odd-degree binary field, let
`Tr` be absolute trace and `H` half-trace. A nonzero coordinate `x` lifts to
the odd-order subgroup precisely when, with `t=1/x`,

```text
x*t = 1
Tr(x) = 0
Tr(t) = 0
Tr(x * H(t^2)) = 0.
```

Here is the derivation used in this experiment; no novelty claim is made.
Rational lifting requires `Tr(x+t^2)=Tr(x)+Tr(t)=0`. If `Tr(x)=0`, set
`lambda=H(x)` and `y=x*H(x+t^2)`. A half `Q` of `P=(x,y)` has coordinate
`q` satisfying `q^2=y+(lambda+1)*x`; conversely these equations construct a
rational half. Thus `P` belongs to `2E` iff `Tr(x)=0`. It belongs to `4E` iff
its half also has `Tr(q)=0`. By linearity of `H`,

```text
Tr(q) = Tr(q^2)
      = Tr(x*H(x+t^2) + x*H(x) + x)
      = Tr(x*H(t^2)).
```

Changing either lifting sign or the choice of `lambda` adds `x` inside this
trace, so it does not change the test. In these odd-degree fields the curve
order is `4*r` with odd `r`; `4E` is its odd-order subgroup. For the measured
rungs, `r` is prime. Coordinate zero is excluded by the inherited nonzero
payload constraints.

The standard half-trace and point-halving background is described by Oliveira,
Lopez, Aranha and Rodriguez-Henriquez,
[Lambda coordinates for binary elliptic curves, CHES 2013](https://www.iacr.org/archive/ches2013/80860113/80860113.pdf).
The specialized constraint and its tests are given here explicitly.

`CompactTemplate` introduces `n` inverse-witness bits per factor. The inverse
equations and the last trace are quadratic in the primary coordinate/inverse
bits; the other two traces are linear. `PowerCompactTemplate` instead computes
the inverse with an addition chain for `A_k=x^(2^k-1)`, followed by squaring
`A_(n-1)`. Squaring, Frobenius, trace and half-trace are binary linear maps;
field multiplications become AND/XOR gates. Construction has polynomial size
and performs no factor-payload enumeration. This says nothing by itself about
SAT search complexity: the expanded inverse can still be difficult to solve.

The selected candidate is `PowerCompactTemplate` with direct S4 and two guessed
payload bits. Development pilots on the pre-existing seed 17 corpus compared
inverse-witness and deterministic-inverse variants and both encodings. The
inverse-witness variant timed out on most pilot targets. The new 100-target
corpus was frozen before those pilots; no configuration was selected from its
holdout outcomes. The witness variant remains as a correctness/control option.

## Frozen protocol

`results/compact_corpus_100.json` contains 100 distinct target sign-orbits at
`n=13,l=6`, seed `20260926`, with 50 development and 50 holdout targets. Its
SHA-256 is
`2ccc317a6ca2bcacbac5c15dbbfd3aaafe5875af98579c9886e2627bd5233184`.
Targets are sampled blindly from the order-2003 subgroup, without planting a
decomposition or selecting for its existence. Both frozen phase patterns,
`(0,0,0)` and `(0,1,2)`, are measured. They reuse the same 100 target points;
200 phase-target attempts are not 200 distinct targets.

The three contenders are the existing explicit-domain S3 chain, explicit-domain
S4, and compact S4. All use two guessed payload bits and one second of wall time
per query, including all guesses and final point verification. Explicit-domain
S4 is the matched admissibility control; the chain records the prior approach.
No default solver behavior is changed.

Each campaign constructs a new field, curve, template and solver. The global
field-modulus cache is cleared first. Solver state is reused within a split,
then reset before the holdout; loading both solvers is charged. Cold setup
reports field/rank initialization, circuit/domain construction and solver loads.
Total CPU additionally includes failed searches, sign/lift/subgroup verification,
matrix-rank work and loop overhead. Interpreter/import startup is excluded.
The budget checks use actual query wall time, including any solver timeout
overshoot; one-second limits are not treated as a hard process kill.

Corpus generation and the independent point-enumeration oracle are experimental
instrumentation, excluded from PDP cost. Oracle CPU is recorded separately and
oracle outputs never become solver clauses or inputs. Every returned SAT point
sum is independently verified. A returned UNSAT must match the oracle; timeout
is unresolved, never UNSAT. Cold template construction is separated from the
per-query threshold but included in total cost.

The preselected four-size ladder is `(n,l)=(7,4),(9,5),(13,6),(19,8)`, with 12
fresh sign-orbit targets at each rung, seed `808013+n`, phases `(0,1,2)`, and
matched explicit-domain/compact S4. These rungs have prime subgroup orders
`29,127,2003,130873`. Degree 17 was rejected before timing because its subgroup
order is composite; rank arithmetic modulo a composite would be invalid here.
Jobs run sequentially in a fixed shuffled order. This first run has one timing
observation per job; it is not an uncertainty estimate or an exponent fit.

## Independent-row accounting

For each verified decomposition, factor points are folded into their
sign/Frobenius orbits. The Frobenius eigenvalue is obtained from
`lambda^2+lambda+2=0 (mod r)` and checked against an actual point. Each factor
is expressed as its scalar coefficient times a canonical orbit representative.
Repeated columns are combined and sparse Gaussian elimination modulo prime `r`
counts independent coefficient rows. Rank persists across development and
holdout, so a repeated direction cannot be counted again after the solver reset.

No fresh per-target column is inserted: that would make independence automatic.
The reported cost is **charged total PDP CPU divided by factor-base row rank**.
All failed, negative and dependent attempts remain in its numerator. A zero-rank
campaign reports `null`, never zero cost. Raw rows include canonical points and
coefficients so the accounting is inspectable.

This is a matrix-progress diagnostic. It does not solve a DLP, measure final
sparse-linear-algebra cost, or establish a relation-collection exponent. The
target scalar bookkeeping and final solve needed for that broader comparison
are outside this experiment. Very small admissible domains and changes in
factor-base dimension also prevent an asymptotic inference from four rungs.

## Reproduce and inspect

```sh
cd experiments/pdp-scaling
python3 -m pip install pycryptosat==5.16.0
python3 -m unittest -v test_compact_admissibility.py test_compact_milestones.py
python3 compact_milestones.py --out /tmp/compact_milestones.json
python3 compact_summary.py /tmp/compact_milestones.json
```

The runner refuses to overwrite its result file and checkpoints completed jobs.
It records corpus/source hashes, versions, witnesses, oracle verdicts, actual
wall times, rank rows, setup costs and all timeouts. A partial checkpoint has
`complete=false`.

Eight tests pass: exhaustive predicate comparisons at degrees 5, 7 and 13;
deterministic circuit/inverse checks on every payload of the tested spaces;
both compact solvers throughout the small subgroup, including reversed signs;
absence of curve-point enumeration in construction; corpus identity and
subgroup validation; orbit coefficient reconstruction on all four rungs;
dependent sign/Frobenius rows; and rejection of composite-order rank arithmetic.

Measured results and milestone decisions are recorded in
[results/compact_summary.md](results/compact_summary.md), with raw data in
[results/compact_milestones.json](results/compact_milestones.json).
