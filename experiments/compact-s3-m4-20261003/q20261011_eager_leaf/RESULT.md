# Q1435: symmetric target-root search and saturated-leaf timing screen

Q1435 lets either S3 middle coordinate trigger exact target-coset support
for the other coordinate, and adds two decision policies that explore the
second leaf pair first. On the frozen N53 ordinary target, `pair1spread`
reached two distinct first-middle states by the 5,000-conflict cap, compared
with one under `allpos`. On N83, `pair1spread` reached its 100-state
target-support cap during a 10-second run, compared with one state for
`allpos`; its remaining 493 unique middle states were recorded as skipped
by that explicit cap. Every ordinary row has status `BOUNDED_UNKNOWN`.

The second hyperparameter was the time to check leaf rationality. An
`eager` check may run as soon as a leaf reaches its exact positive-weight
bound, before every negative bit is assigned. It fired **zero** times
before full assignment in all nine frozen runs: the formula's cardinality
encoding already propagated the remaining bits. At N53, `allpos sat` and
`allpos eager` reached the same 5,000-conflict bound with identical exact
search counters. This rejects eager timing as an improvement for these
inputs while preserving the effective short guard of Q1434.

## Exact method

Q1433 constrained middle row 5 after row 4 was fixed. Q1435 applies the
same S3 symmetry in either direction: when exactly one of middle rows 4
and 5 is assigned, compute every other-middle root against the complete
raw target x-coordinate set and add the same guarded selector support.
When both rows are assigned, Q1432's exact final-link check applies.
`pair1pos` makes leaf rows 2 and 3 the first decision pair;
`pair1spread` also offsets and strides their normal-basis bit order. Each
direction has its own memo key and a common explicit early-query limit.

At most w positive bits are permitted on each leaf. Once w are true,
their x value is fixed under that at-most-w constraint, so the eager test
is algebraically valid even with unassigned negative variables. The
short clause negating those w positives is valid throughout backtracking.
If the leaf has fewer than w positives, the callback waits for a full
assignment and uses the full guard. The measured zero eager checks show
that this earlier hook adds no pruning on the frozen Q1410/Q1408 encodings.

## Frozen ordinary grid

All rows use the exact Q1410 N53 and Q1408 N83 ordinary CNF, public
points, target cosets, and factor bases; `satpivot` pair-root encoding;
Q1433 `selector` target support; a 5,000-conflict cap; and a 10-second wall
cap. The N53 curve is `EC1N53Ckb1hf77aab617904`, B=24,062 usable base
points and K=227 folded columns. The N83 curve is
`EC1N83Ckb1h876c2921cb64`, B=30,977,592 and K=186,612. Both use
`isogeny: "none"`. `E` counts unique exact early-target states,
`E_rev` counts those initiated from middle row 5, `R` counts pair-root
queries, and `X` counts nonrational leaves rejected. All statuses are
`BOUNDED_UNKNOWN`.

| Field | Branch | Leaf mode | Conflicts | E | E_rev | R | X | Cap |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| N53 | allpos | sat | 5,000 | 1 | 0 | 5,001 | 5,411 | conflict |
| N53 | allpos | eager | 5,000 | 1 | 0 | 5,001 | 5,411 | conflict |
| N53 | pair1pos | eager | 5,000 | 1 | 1 | 5,001 | 5,411 | conflict |
| N53 | pair1spread | eager | 5,000 | 2 | 2 | 4,940 | 5,321 | conflict |
| N83 | allpos | sat | 2,077 | 1 | 0 | 2,078 | 2,030 | wall |
| N83 | allpos | eager | 2,114 | 1 | 0 | 2,115 | 2,076 | wall |
| N83 | pair1pos | eager | 2,170 | 1 | 1 | 2,171 | 2,125 | wall |
| N83 | pair1spread | eager | 62 | 100 | 0 | 298 | 312 | wall |
| N83 | allspread | eager | 2,867 | 2 | 0 | 2,815 | 2,868 | wall |

The `pair1spread` N83 row also has 493 early states skipped after its
100-state limit and 985 final-link rejections. Its
ordinary early queries happened from row 4 even though the decision policy
selected the second leaf pair first; the exact callback direction is
recorded rather than inferred from the policy name. CPU wall ratios on the
unisolated host are exploratory, and raw conflict/root-query counts have
different boundaries. These rows measure search diversity, not solve
time.

The N83 `pair1spread` row reached its target-support limit, so a second
six-cell screen varied that limit while holding the same binary, public
point, base, branch policy, conflict cap, and 10-second wall cap. `Skip`
counts unique first-middle states left to the original CNF and final-link
check after the limit; all six rows remain `BOUNDED_UNKNOWN`.

| Early limit | Exact early states | Skip | External clauses | Final-link rejections | Pair-root queries |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 94 | 10,605 | 326 | 83 |
| 10 | 10 | 163 | 17,859 | 324 | 88 |
| 25 | 25 | 182 | 29,963 | 363 | 105 |
| 50 | 50 | 160 | 46,667 | 319 | 106 |
| 500 | 335 | 0 | 243,734 | 0 | 169 |
| 2,000 | 457 | 0 | 332,388 | 0 | 230 |

The high limits used the interval to add many support clauses and did not
reach a fully assigned final-link pair. The low limits left more paths for
the final check. No cell completed a decomposition, so this screen cannot
select an optimal limit by solve cost.

## Validation and matched pair-table comparison

`validate.py` tests the reverse support directly in degree 11. With middle
row 5 fixed and row 4 free, a two-root case produces a directly verified
S3 model; blocking both roots makes it UNSAT. Rootless and zero-input
cases exercise the exact conflict and inverse branches. Both locked
N53/N83 controls still produce independently replayed S3 models. A
separate field-trace calculation confirms all 120 archived nonrational
leaf samples across the grid and limit sweep. The validation status is
`PASS`.

`attach_pair_references.py` binds the existing comparators on the **same**
curve, workload, actual B, folded K, and enumerated-set digest:

| Field | Matched pair-table status | Charged pair descriptors | Charged target pair queries | Q1435 ordinary status |
| --- | --- | ---: | ---: | --- |
| N53 | one verified four-point relation | 500,000 | 171,218 | BOUNDED_UNKNOWN |
| N83 | no exact hit at cap | 2,000,000 | 2,719,744 | BOUNDED_UNKNOWN |

The N53 pair-table relation is a demonstrated relation on the same public
point and base. The N83 pair-table cap covers only its declared search
rectangle. Neither comparator supplies a complete one-target IC cost or
an N131 solver projection.

## Work estimate and next gate

The exact N131 W<=6 uniform-query supply bound leaves less than
\(2^{33.36}\) work units per ordinary query under an abstract \(2^{61}\)
total cap with all other costs set to zero. Q1435 measured no completed
ordinary decomposition, so its field operations per successful query,
natural yield, novel rank, fully charged N131 \(2^x\) projection, and
challenge gap remain null in `measurements.json`.

The next experiment should count **all** S3-root calls, including target
support and final-link checks, plus leaf-rationality field operations and
conversion overhead under a fixed accounting boundary. Then vary the
first-pair search with a query-level restart or seed, rather than spending
another long cap within one first-middle state. The method gate remains a
verified ordinary N53 decomposition from this solver, followed by an
ordinary N83 decomposition and measured useful-row/rank rates. Keep the
matched pair-table as an alternative search mechanism, with its own
charged costs.

## Reproduction

From the repository root, first regenerate the Q1430 CNF/maps and Q1432
target files as documented in their directories. Then run:

```sh
sh experiments/compact-s3-m4-20261003/q20261011_eager_leaf/build.sh /private/tmp/q1435_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_eager_leaf/run_grid.py --binary /private/tmp/q1435_insearch --wall 10 --conflicts 5000
python3 experiments/compact-s3-m4-20261003/q20261011_eager_leaf/run_limit_sweep.py --binary /private/tmp/q1435_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_eager_leaf/attach_pair_references.py
python3 experiments/compact-s3-m4-20261003/q20261011_eager_leaf/validate.py --binary /private/tmp/q1435_insearch
```

`measurements.json` records source/executable hashes, exact input and log
hashes, caps, status, and comparator receipt hashes. `candidate_id` and
`run_id` remain null for the Q1435 PDP-stage proposal until a complete
IC pipeline and frozen one-target run exist.
