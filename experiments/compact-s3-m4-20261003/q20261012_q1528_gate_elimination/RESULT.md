# Q1528: eliminate all shared AND variables from the exact S3 handoffs

Direct substitution of shared AND outputs into the ANF XOR rows reduces the
frozen **N53** handoffs from 4,246 to **1,437 variables** and the frozen
**N83** handoffs from 43,566 to **2,315 variables**. The ordinary N83
formula falls from Q1527's 44,461 equations to **3,210 equations** while
retaining 95,201 quadratic-monomial occurrences. On the pinned N83 input,
observed peak RSS falls from Q1527's 50.5 MiB to **8.2 MiB**. The pinned
N53 solver model reconstructs all 2,809 removed gates and satisfies every
original XCNF row and the curve group relation. The unpinned N53 positive,
ordinary N53, pinned N83, and two ordinary N83 cells each reached the
frozen 90-second wall cap.

| Exact input | Q1527 variables / equations | Q1528 variables / equations | Q1528 status | Child user CPU s | Exploratory wall s | Peak RSS MiB | Conflict evidence |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| N53 pinned positive | 4,246 / 9,997 | **1,437 / 7,188** | `SAT_VERIFIED` | 0.111 | 0.33 | 7.14 | final 6,904 |
| N53 unpinned positive | 4,246 / 9,891 | **1,437 / 7,082** | `WALL_CAP` | 38.87 | 90.08 | 8.47 | periodic ≥480,000 |
| N53 ordinary | 4,246 / 9,891 | **1,437 / 7,082** | `WALL_CAP` | 68.81 | 90.10 | 8.05 | periodic ≥1,230,000 |
| N83 pinned positive | 43,566 / 44,627 | **2,315 / 3,376** | `WALL_CAP` | 71.91 | 90.10 | 8.19 | periodic ≥9,050,000 |
| N83 ordinary selected | 43,566 / 44,461 | **2,315 / 3,210** | `WALL_CAP` | 53.21 | 90.09 | 18.80 | periodic ≥850,000 |
| N83 ordinary holdout | 43,566 / 44,461 | **2,315 / 3,210** | `WALL_CAP` | 58.23 | 90.06 | 17.98 | periodic ≥850,000 |

The comparison uses the same six frozen Q1519 XCNF inputs, DPLL-ANF
binary, watched-term flags, and outer wall boundary as Q1527. The
requested 30-second CPU limit and child 30/35-second RLIMIT were not
enforced on this Darwin host; the 90-second wall cap was effective. The
host has no isolation receipt, so CPU and wall ratios are exploratory.
The memory values are observed per-child peaks, and periodic conflict
numbers are lower bounds for capped rows rather than final totals.

## Exact circuit transformation

[eliminate.py](eliminate.py) regenerates and SHA-checks each original
XCNF, identifies every three-clause AND definition, and asserts that
no AND output feeds another AND gate or a retained clause. It replaces
every XOR-row occurrence of that output with its signed quadratic
monomial, removes the definition, and deterministically renumbers the
remaining variables. It eliminates **2,809** gate outputs at N53 and
**41,251** at N83. A positive solver assignment is mapped back to the
original variable numbers; all gate outputs are recomputed before the
original Boolean, S3, curve-point, and group-sum checks run. The frozen
factor-base records supply the subgroup-usable point sets.

The three Lean-checked declarations in [FORMALIZATION.md](FORMALIZATION.md)
prove the local gate identity, elimination under an arbitrary surrounding
condition, and XOR substitution. The [validator](validate.py) independently
compares every archived converted clause and XOR row with the original
under four assignments, regenerates all six formula archives, checks
source/binary/receipt hashes, and replays the pinned positive model.
The final Lean build has no reported axioms; two failed draft builds are
retained with their diagnostics.

The N53 curve is `EC1N53Ckb1hf77aab617904`, with **B=24,062** usable
points, **K=227** folded columns, packed orbit-key SHA-256
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`,
and independently enumerated signed-point SHA-256
`356ebb34476f44b89d376e04fe4b03570a0a4cf3dfe0cd722309d7ea083ccc18`.
The N83 curve is `EC1N83Ckb1h876c2921cb64`, with
**B=30,977,592**, **K=186,612**, and point-file SHA-256
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
This is proposal `Q1528`, a `PDP4sat` stage result with null candidate
and run IDs and `isogeny: "none"`.

The [protocol](protocol.json) froze the solver, source and transformed
input hashes, order, and limits before the measured panel. All six
compressed formulas, [raw receipts](runs), [analysis](analysis.json),
and pre-protocol [smoke logs](smoke/README.md) are archived. The N83
20-second smoke cap is a separate censored observation.

## Degree-131 work boundary

The three ordinary Q1528 cells yielded zero verified relations and zero
novel rows within their caps. Cost per useful relation is censored. The
exact circuit and memory reductions do not supply a field-operation
cost for a completed ordinary decomposition. Q1505's separate conditional
N131 complete-scan relation-supply model remains `2^123.289` batch
multiplication calls; Q1526's separate conditional W≤7 pair-index model
is `2^86.185` pair-add attempts. These models use different algorithms
and units. Factor-base preparation, final relation-matrix work, target
descent, and replay are not jointly charged for a single N131 candidate;
the fully charged solve exponent remains unset. This result does not
pass the challenge gate.

The next solver experiment should attack target-conditioned second-pair
selection or add algebraic reasoning to the compact quadratic system.
Eliminating all gate auxiliaries has changed the representation and
memory use substantially; the capped ordinary searches show that this
alone does not deliver relation yield on the frozen panel.

Recheck the evidence with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1528_gate_elimination/validate.py
cd experiments/compact-s3-m4-20261003/q20261012_q1528_gate_elimination/lean && lean Eliminate.lean
```
