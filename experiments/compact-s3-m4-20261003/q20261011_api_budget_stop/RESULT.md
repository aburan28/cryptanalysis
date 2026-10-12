# Q1443: equal counted-work budget separates early-support caps at N53

A counted field API-entry stop now bounds compact chained-S3 search after
each target-coset root query and propagator batch. At a frozen budget of
500,000 entries per ordinary attempt, early-support cap **1** completed
**3,110 distinct final-link checks** on the N53 point; cap **8** completed
797. Their actual charges were 500,068 and 500,074 entries, yielding a
**3.90 times** final-check improvement at essentially equal counted field
work. N83 remained nearly tied: 2,733 versus 2,708 checks at 500,136 and
500,096 entries. Every row stopped with `api_budget_hit: true`, status
`BOUNDED_UNKNOWN`, and no wall or conflict cap hit.

The frozen curves are `EC1N53Ckb1hf77aab617904` (actual usable factor
base B=24,062, folded K=227, enumerated-set digest
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`)
and `EC1N83Ckb1h876c2921cb64` (B=30,977,592, folded K=186,612,
digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`).
Each uses the previously frozen ordinary public point and
`isogeny: "none"`. `Q1443` is a PDP-stage proposal; `candidate_id` and
`run_id` remain null.

## Work boundary and measured comparison

The new executable counts every public `CountedOnb` method entry during
`solver.solve()`. It checks the total after each target-coset S3 root query
and each external-propagator batch. If the requested budget is crossed,
CaDiCaL is terminated and records `api_budget_hit`. A partial target-coset
root enumeration is discarded without adding a clause or recording a
completed final-link check. The largest observed overshoot was **136
entries**, or 0.0272% of the 500,000-entry budget. The field method vector,
native SAT propagations/decisions, conflicts, CPU and process wall time,
peak RSS, stopping flags, source/binary hashes, and raw logs are in
`measurements.json`.

The only varied search parameter is the early-support cap. Both settings
use the same executable, target point, seed, `seededpos` leaf order,
`satpivot` pair roots, `selector` support, `eager` leaf checks, 5,000
conflicts, and a 180-second wall safety cap. Fresh solver processes share
no learned clauses.

| Field | Early cap | Completed final-link checks | Exact target S3 matches | Counted API entries | Budget overshoot | Final checks per million entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | **1** | **3,110** | 0 | 500,068 | 68 | **6,219** |
| N53 | 8 | 797 | 0 | 500,074 | 74 | 1,594 |
| N83 | 1 | 2,733 | 0 | 500,136 | 136 | 5,465 |
| N83 | 8 | 2,708 | 0 | 500,096 | 96 | 5,415 |

The N53 gain is in complete *rejected* final-link tests per counted field
entry. It is a point-decomposition search improvement, not a successful
decomposition cost or a CPU speedup. Native SAT work and field operations
inside one public method are not converted to the API-entry unit. The
operation vectors and wall times should be kept separate until an
end-to-end accounting unit is calibrated.

## Verification and cumulative one-target charge

Two locked N53/N83 controls with budget disabled produced S3 models that
passed independent three-link evaluation. `validate.py` passed all source,
binary, input and raw-log hashes, operation-vector sums, stop flags,
overshoot limits, cumulative charges, and 32 independent rejected-leaf
trace calculations. `validation.json` records `PASS`.

The cumulative one-target ledger includes every archived Q1437-Q1442
attempt, the four Q1443 ordinary attempts, and **49,328** entries from two
unfrozen N53 budget-stop diagnostics before this runner was frozen. The
first diagnostic's source snapshot was not retained, so those entries are
charged but excluded from the frozen comparison. Totals are **22,649,459**
counted entries (\(2^{24.43}\)) at N53 and **7,546,552**
(\(2^{22.85}\)) at N83. The bounded ordinary attempts have no exact
target S3 match, so successful-query work, verified relation yield and
novel rank remain unmeasured.

The exact N131 W<=6 uniform-query supply bound permits less than
\(2^{33.36}\) abstract work units per ordinary query under a \(2^{61}\)
total cap when other costs are zero. Counted API entries are a different
software event unit. A fully charged N131 \(2^x\) projection and numerical
gap to the challenge remain null.

## Next experiment

Allocate a larger frozen API budget to cap 1 on the known-satisfiable N53
ordinary point, with cap 8 as a smaller matched control, while preserving
the cumulative one-target charge. If a complete S3 model appears,
independently replay actual curve points, subgroup membership, factor-base
membership, and the four-point sum before using it in a relation-yield or
rank measurement. At N83, shift effort to a method that changes the
near-tied final-link throughput or reaches a natural relation.

## Reproduction

After regenerating Q1430's frozen CNF/maps and Q1432's target files:

```sh
sh experiments/compact-s3-m4-20261003/q20261011_api_budget_stop/build.sh /private/tmp/q1443_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_api_budget_stop/run.py --binary /private/tmp/q1443_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_api_budget_stop/validate.py --binary /private/tmp/q1443_insearch
```
