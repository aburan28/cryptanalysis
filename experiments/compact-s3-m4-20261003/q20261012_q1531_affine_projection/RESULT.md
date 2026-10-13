# Q1531: exact affine projection removes 830 N83 solver variables

Gaussian elimination of variables absent from every nonlinear monomial
reduces the frozen compact S3 ordinary formulas from **1,437 to 1,225
variables at N53** and from **2,315 to 1,485 at N83**. It removes 212 and
830 affine pivots respectively while preserving all quadratic and higher
monomials. The N53 pinned solver model lifts through the saved basis,
satisfies both ANF files, reconstructs the Q1528 gate variables, and passes
the original XCNF and four-point group verification.

The five measured cells use the same DPLL-ANF binary, options, exact
curve/factor-base inputs, and 90-second wall boundary as Q1528. The curves
are `EC1N53Ckb1hf77aab617904` and `EC1N83Ckb1h876c2921cb64`.
The N53 W≤3 base has actual `B=24,062`, folded `K=227`, digest
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`;
the N83 W≤5 base has actual `B=30,977,592`, folded `K=186,612`, digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
This is proposal `Q1531`, stage `PDP4sat`, with null candidate/run IDs and
`isogeny: "none"`.

| Exact input | Q1528 vars / equations | Q1531 vars / equations | Q1531 status | Child CPU s | Peak RSS MiB | Periodic conflicts reached (lower bound) |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| N53 pinned control | 1,437 / 7,188 | **1,225 / 6,976** | `SAT_VERIFIED` | 0.09 | 6.78 | final 6,904 |
| N53 ordinary | 1,437 / 7,082 | **1,225 / 6,870** | `WALL_CAP` | 74.27 | 8.59 | ≥3,460,000 |
| N83 pinned control | 2,315 / 3,376 | **1,485 / 2,546** | `WALL_CAP` | 60.66 | 8.42 | ≥7,180,000 |
| N83 ordinary selected | 2,315 / 3,210 | **1,485 / 2,380** | `WALL_CAP` | 48.19 | 18.66 | ≥850,000 |
| N83 ordinary holdout | 2,315 / 3,210 | **1,485 / 2,380** | `WALL_CAP` | 59.13 | 18.88 | ≥850,000 |

Q1528's N53 ordinary run reached at least 1,230,000 periodic conflicts
under its 90-second cap; Q1531 reached at least 3,460,000. The N83
selected and holdout periodic bounds are unchanged at 850,000. Conflict
counts describe search progress, not verified relations or a CPU speedup.
All four capped cells retain their stdout, stderr, status, CPU, wall, and
memory receipts. CPU and wall comparisons remain exploratory without a
host isolation record. The requested child CPU limit was not enforced on
this Darwin host; the outer wall cap was effective.

## Exact transformation

[`project.py`](project.py) parses each native ANF row, normalizes signed
linear literals, and identifies variables that occur only linearly.
Gaussian row operations pivot on 212 N53 or 830 N83 such variables.
Substitution changes only the linear part of every polynomial; the
nonlinear monomial tokens remain verbatim. Residual linear equations are
retained. The saved pivot basis lifts a reduced assignment in reverse
order, after which the original Q1528 verifier checks every gate,
summation-polynomial constraint, curve point, and group relation.

The [Lean proof map](FORMALIZATION.md) checks one existential affine pivot,
signed-literal normalization, and XOR row replacement. The DIMACS parser
and curve/group bridge remain executable checks. The [validator](validate.py)
regenerates every projected ANF byte from the frozen Q1528 files, checks
formula/basis/source hashes and all five receipts, and round-trips the
independent pinned model. It passes.

## Work boundary and next search

The four non-pinned cells ended at their recorded wall caps. Cost per useful
ordinary relation, rank novelty, and a complete N131 `2^x` solve projection
remain unset for this solver. Q1530's separate conditional pair-index
frontier is `2^85.190199` pair additions at its best matrix-eligible cell;
ANF variable removal does not alter that different algorithm's cost.

The next solver hyperparameter search should vary **affine pivot order and
substitution sparsity** on these same five inputs. The N53 ordinary cell's
higher conflict throughput shows that projection changes the search, while
its cap makes solving impact unresolved. Keep the pinned model replay and
the original XCNF/group check as gates for every variant; promote a variant
only on verified ordinary relations or a controlled reduction in complete
PDP work.

## Reproduction

The [protocol](protocol.json) fixes all formula, basis, converter, runner,
and solver hashes before the measured panel. Run:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1531_affine_projection/validate.py
cd experiments/compact-s3-m4-20261003/q20261012_q1531_affine_projection/lean && lean AffineProjection.lean
```
