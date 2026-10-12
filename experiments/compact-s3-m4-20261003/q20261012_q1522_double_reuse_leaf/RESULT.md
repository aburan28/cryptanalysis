# Q1522: smaller N83 projection circuits fail the pinned solver gate

Reusing the rational-lift inverse reduced the cofactor-four leaf from three
field-product circuits to two. The direct-output variant shrank Q1513's
one-link N83 chained-`S3` system from **43,566 to 36,594 variables**,
**125,716 to 105,298 CNF clauses**, and **1,247 to 1,081 native-XOR rows**
on the same ordinary inputs. This is a 16.0% variable and 16.2% CNF
reduction. The inverse-of-doubled-x variant produced 36,760 variables and
105,464 CNF clauses. The exact algebraic bridge, nonzero conditions, and
formalization status are in [FORMALIZATION.md](FORMALIZATION.md).

The smaller encodings did **not** improve the measured solver gate. Q1513's
archived pinned N83 positive control returned `SAT_VERIFIED` after 2,987
reported conflicts. Under Q1522's frozen 250,000-conflict / 12-second soft
CPU caps, each new variant returned `INDETERMINATE` at 250,001 reported
conflicts on that same pinned complement. This is a censored lower bound of
more than 83 times the baseline control's conflicts, not a completed-solve
ratio. Both ordinary selected and holdout complements were also bounded:

| Encoding | Variables / CNF / XOR | Pinned positive control | Selected ordinary | Holdout ordinary |
| --- | ---: | --- | --- | --- |
| Q1513 direct projection | 43,566 / 125,716 / 1,247 | `SAT_VERIFIED`, 2,987 conflicts | archived bounded row | archived bounded row |
| Inverse of doubled x | 36,760 / 105,464 / 1,081 | `INDETERMINATE`, 250,001 | `INDETERMINATE`, 250,002 | `CPU_CAP`, conflict total unavailable |
| Direct projected-x equation | **36,594 / 105,298 / 1,081** | `INDETERMINATE`, 250,001 | `INDETERMINATE`, 250,002 | `INDETERMINATE`, 250,001 |

All Q1522 statuses, raw stdout/stderr, child CPU, wall, and peak RSS are
retained; a capped row is not an unsatisfiability result. The host was
unisolated, so timing ratios are exploratory. The [protocols](protocol.json)
and [direct protocol](direct_protocol.json) bind source, exact Q1513 inputs,
factor-base digest, formula hashes, solver binary, limits, and run order.
The [formula build receipts](build_receipt.json),
[direct build receipts](direct_build_receipt.json), [first run](result.json),
[direct run](direct_result.json), and [validator](validate.py) preserve the
measurement and a numerical curve-doubling replay. The Q1513 pinned SAT
certificate remains the correctness reference; Q1522 did not produce a SAT
certificate for its changed formulas within the frozen caps.

The curve is `EC1N83Ckb1h876c2921cb64`, with the exact cofactor-four
weight-at-most-five base of **B=30,977,592** usable subgroup points,
**K=186,612** signed-Frobenius columns, and base digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Both configurations are `Q1522` `PDP4sat` stage variants, with null
candidate/run IDs and `isogeny: "none"`. Ordinary relation and rank counts
within these caps are zero. Cost per useful relation and the fully charged
N131 solve exponent remain unknown. The current solver should keep Q1513's
direct projection circuit while work moves to target-conditioned second-pair
selection; a future two-product circuit must first pass the pinned control.

Recheck all source, formula, raw solver, and arithmetic receipts with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1522_double_reuse_leaf/validate.py
```
